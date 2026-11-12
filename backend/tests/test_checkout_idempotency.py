"""Retry behavior through the public API, with isolated DB and fake providers."""
import pytest
from fastapi import HTTPException
from backend.app.core.config import settings
from backend.app.models.marketplace import CheckoutAttempt, PendingCheckout, WebhookEvent
from backend.app.models import User
from backend.app.services import idempotency, payments
from test_payments import auth, connect


@pytest.mark.parametrize('country', ['IN', 'US'])
def test_subscription_replays_same_and_different_keys(client, users, provider, db, country):
    headers = {**auth(users[1]), 'CF-IPCountry': country, 'Idempotency-Key': 'subscription-key-1'}
    first = client.post('/api/v1/billing/subscribe', headers=headers)
    assert first.status_code == 200, first.text
    for key in ['subscription-key-1', 'another-tab-key', 'another-tab-key']:
        again = client.post('/api/v1/billing/subscribe', headers={**headers, 'Idempotency-Key': key})
        assert again.status_code == 200, again.text
        assert again.json() == first.json()
    path = '/subscriptions' if country == 'IN' else '/checkouts'
    assert len([call for call in provider[0] if call[0] == 'POST' and call[2] == path]) == 1
    assert db.query(CheckoutAttempt).filter_by(status='succeeded').count() == 2


@pytest.mark.parametrize('gateway,country', [('razorpay', 'IN'), ('dodo', 'US')])
def test_purchase_retry_reuses_checkout(client, users, asset, provider, db, gateway, country):
    connect(client, users[0], gateway)
    headers = {**auth(users[1]), 'CF-IPCountry': country, 'Idempotency-Key': 'purchase-attempt-1'}
    path = '/api/v1/assets/' + asset.slug + '/buy'
    first = client.post(path, headers=headers)
    assert first.status_code == 200, first.text
    for key in ['purchase-attempt-1', 'purchase-other-tab']:
        response = client.post(path, headers={**headers, 'Idempotency-Key': key})
        assert response.status_code == 200, response.text
        assert response.json() == first.json()
    assert db.query(PendingCheckout).count() == 1
    assert len([call for call in provider[0] if call[0] == 'POST' and call[2] in ['/orders', '/checkouts']]) == 1


def test_same_key_different_region_or_resource_rejected(client, users, asset, provider):
    connect(client, users[0], 'razorpay')
    headers = {**auth(users[1]), 'CF-IPCountry': 'IN', 'Idempotency-Key': 'one-purchase-key'}
    assert client.post(f'/api/v1/assets/{asset.slug}/buy', headers=headers).status_code == 200
    assert client.post('/api/v1/assets/other-asset/buy', headers=headers).status_code == 409
    assert client.post(f'/api/v1/assets/{asset.slug}/buy', headers={**headers, 'CF-IPCountry': 'US'}).status_code == 409


def test_provider_timeout_persists_unknown_and_blocks_new_keys(client, users, asset, provider, db, monkeypatch):
    connect(client, users[0], 'razorpay')
    original = payments.gateway_request
    seen = []
    def timeout(method, gateway, path, **kwargs):
        if path == '/orders' and method == 'POST':
            seen.append(kwargs['payload']['receipt'])
            # Simulate acceptance at the provider followed by a lost response.
            assert db.query(CheckoutAttempt).filter_by(status='processing').count() == 1
            raise HTTPException(502, 'Payment provider request failed')
        return original(method, gateway, path, **kwargs)
    from backend.app.api.v1.endpoints import marketplace
    monkeypatch.setattr(marketplace, 'gateway_request', timeout)
    headers = {**auth(users[1]), 'CF-IPCountry': 'IN', 'Idempotency-Key': 'lost-response-key'}
    path = f'/api/v1/assets/{asset.slug}/buy'
    assert client.post(path, headers=headers).status_code == 502
    attempt = db.query(CheckoutAttempt).one()
    assert attempt.status == 'unknown'
    assert attempt.id == seen[0]
    assert attempt.request_data['amount'] == 42625
    for key in ['lost-response-key', 'new-key-after-timeout']:
        result = client.post(path, headers={**headers, 'Idempotency-Key': key})
        assert result.status_code == 409
        assert result.headers['x-checkout-attempt'] == attempt.id
    assert len(seen) == 1
    status_path = '/api/v1/billing/checkout-attempts/' + attempt.id
    assert client.get(status_path, headers=auth(users[1])).json()['status'] == 'unknown'
    assert client.get(status_path, headers=auth(users[0])).status_code == 404


def test_crashed_processing_claim_does_not_expire_into_second_payment(client, users, asset, provider, db):
    db.add(CheckoutAttempt(user_id=users[1].id, operation='purchase', resource=asset.id,
        idempotency_key='crashed-worker-key', request_hash='0' * 64, status='processing'))
    db.commit()
    result = client.post(f'/api/v1/assets/{asset.slug}/buy',
        headers={**auth(users[1]), 'CF-IPCountry': 'IN', 'Idempotency-Key': 'new-worker-key'})
    assert result.status_code == 409
    assert not provider[0]


def test_validation_failure_can_retry_same_key(client, users, asset, provider):
    headers = {**auth(users[1]), 'CF-IPCountry': 'IN', 'Idempotency-Key': 'not-connected-yet'}
    path = f'/api/v1/assets/{asset.slug}/buy'
    assert client.post(path, headers=headers).status_code == 409
    connect(client, users[0], 'razorpay')
    assert client.post(path, headers=headers).status_code == 200


def test_key_is_scoped_to_user(client, users, provider, db):
    third = User(id='third', email='third@example.com', username='third', name='Third', email_verification_required=False)
    db.add(third); db.commit()
    # Separate users can legitimately use the same key; provider fake reuses IDs,
    # so test claim isolation with validation failures rather than remote IDs.
    for user in [users[1], third]:
        response = client.post('/api/v1/assets/missing/buy', headers={**auth(user),
            'CF-IPCountry': 'IN', 'Idempotency-Key': 'shared-client-key'})
        assert response.status_code == 404
    assert db.query(CheckoutAttempt).filter_by(idempotency_key='shared-client-key').count() == 2


def test_invalid_key_rejected_before_provider(client, users, provider):
    result = client.post('/api/v1/billing/subscribe', headers={**auth(users[1]),
        'CF-IPCountry': 'IN', 'Idempotency-Key': 'short'})
    assert result.status_code == 400
    assert not provider[0]


def test_webhook_claim_rolls_back_on_failure_and_is_scoped(db):
    assert idempotency.claim_webhook(db, 'platform:razorpay', 'retry-event')
    db.rollback()
    assert idempotency.claim_webhook(db, 'platform:razorpay', 'retry-event')
    db.commit()
    assert not idempotency.claim_webhook(db, 'platform:razorpay', 'retry-event')
    assert idempotency.claim_webhook(db, 'seller:razorpay:other', 'retry-event')
    db.commit()
    assert db.query(WebhookEvent).count() == 2


def test_redis_expired_owner_cannot_delete_new_owner(monkeypatch):
    import redis
    class FakeRedis:
        value = None
        def set(self, key, token, **kwargs):
            self.value = token
            return True
        def eval(self, script, count, key, token):
            assert token != self.value
            assert "redis.call('get'" in script
            if self.value == token:
                self.value = None
        def close(self): pass
    client = FakeRedis()
    monkeypatch.setattr(settings, 'REDIS_URL', 'redis://unused')
    monkeypatch.setattr(redis.Redis, 'from_url', lambda *a, **kw: client)
    with idempotency.redis_lock('buyer:purchase:asset'):
        client.value = 'new-owner-after-expiry'
    assert client.value == 'new-owner-after-expiry'


def test_redis_outage_falls_back_to_durable_guard(client, users, provider, monkeypatch):
    import redis
    monkeypatch.setattr(settings, 'REDIS_URL', 'redis://unused')
    def unavailable(*args, **kwargs): raise redis.ConnectionError('offline')
    monkeypatch.setattr(redis.Redis, 'from_url', unavailable)
    headers = {**auth(users[1]), 'CF-IPCountry': 'IN', 'Idempotency-Key': 'redis-offline-key'}
    one = client.post('/api/v1/billing/subscribe', headers=headers)
    two = client.post('/api/v1/billing/subscribe', headers=headers)
    assert one.status_code == two.status_code == 200
    assert one.json() == two.json()
    assert len([c for c in provider[0] if c[2] == '/subscriptions']) == 1


@pytest.mark.parametrize('subscription', [True, False])
def test_pre_migration_pending_checkout_is_reused(client, users, asset, provider, db, subscription):
    if not subscription:
        connect(client, users[0], 'razorpay')
    path = '/api/v1/billing/subscribe' if subscription else f'/api/v1/assets/{asset.slug}/buy'
    headers = {**auth(users[1]), 'CF-IPCountry': 'IN', 'Idempotency-Key': 'old-before-migration'}
    first = client.post(path, headers=headers)
    assert first.status_code == 200
    # Only the isolated test DB: simulate pre-migration records with no attempt ledger.
    db.query(CheckoutAttempt).delete(); db.commit()
    second = client.post(path, headers={**headers, 'Idempotency-Key': 'new-after-migration'})
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    post_path = '/subscriptions' if subscription else '/orders'
    assert len([c for c in provider[0] if c[0] == 'POST' and c[2] == post_path]) == 1


def test_subscription_gateway_timeout_blocks_recreation(client, users, provider, db, monkeypatch):
    from backend.app.api.v1.endpoints import billing
    original = billing.platform_request
    seen = []
    def lost_response(method, gateway, path, payload=None):
        if path == '/subscriptions' and method == 'POST':
            idempotency.provider_mutation_started()
            seen.append(payload['notes']['promptally_checkout_reference'])
            raise HTTPException(502, 'Payment provider request failed')
        return original(method, gateway, path, payload)
    monkeypatch.setattr(billing, 'platform_request', lost_response)
    headers = {**auth(users[1]), 'CF-IPCountry': 'IN', 'Idempotency-Key': 'subscription-lost-response'}
    assert client.post('/api/v1/billing/subscribe', headers=headers).status_code == 502
    attempt = db.query(CheckoutAttempt).one()
    assert attempt.status == 'unknown'
    assert attempt.id == seen[0]
    assert client.post('/api/v1/billing/subscribe', headers={**headers, 'Idempotency-Key': 'fresh-subscription-key'}).status_code == 409
    assert len(seen) == 1


def test_webhook_unrelated_integrity_error_is_not_acknowledged(db, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    assert idempotency.claim_webhook(db, 'platform:razorpay', 'first-event')
    db.commit()
    row_id = db.query(WebhookEvent).one().id
    monkeypatch.setattr(idempotency.uuid, 'uuid4', lambda: row_id)
    with pytest.raises(IntegrityError):
        idempotency.claim_webhook(db, 'platform:razorpay', 'different-event')
    db.rollback()


def test_renamed_prompt_preserves_same_attempt_identity(client, users, asset, provider, db):
    connect(client, users[0], 'razorpay')
    headers = {**auth(users[1]), 'CF-IPCountry': 'IN', 'Idempotency-Key': 'rename-safe-checkout'}
    first = client.post(f'/api/v1/assets/{asset.slug}/buy', headers=headers)
    assert first.status_code == 200
    asset.slug = 'renamed-prompt'; db.commit()
    replay = client.post('/api/v1/assets/renamed-prompt/buy', headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    assert len([c for c in provider[0] if c[0] == 'POST' and c[2] == '/orders']) == 1
