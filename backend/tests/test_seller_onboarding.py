"""Automated connections and payment reconciliation use isolated, mocked providers."""
import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, parse_qs
import pytest
from fastapi import HTTPException
from backend.app.core.config import settings
from backend.app.models import SellerGatewayConfig, SellerOAuthState, PendingCheckout, AssetPurchase
from backend.app.models.enums import CheckoutStatus, UserTier
from backend.app.services.crypto import decrypt_secret
from backend.app.services.seller_onboarding import oauth_access_token
from backend.tests.test_payments import auth, signed, connect


def dodo_responses(provider, seller):
    url = f"{settings.SITE_URL.rstrip('/')}/api/v1/webhooks/dodo/{seller.id}"
    provider[1].update({
        ('GET', 'dodo', '/webhooks?limit=100'): {'data': [], 'done': True},
        ('POST', 'dodo', '/webhooks'): {'id': 'whk_1', 'url': url},
        ('GET', 'dodo', '/webhooks/whk_1/secret'): {'secret': 'whsec_' + base64.b64encode(b'auto-signing-key').decode()},
        ('PATCH', 'dodo', '/webhooks/whk_1'): {'id': 'whk_1'},
    })
    return url


def test_dodo_key_only_setup_reuses_endpoint_and_hides_secrets(client, users, provider, db):
    url = dodo_responses(provider, users[0])
    payload = {'gateway_type': 'dodo', 'api_key': 'legacy-valid-key', 'environment': 'test'}
    for attempt in range(2):
        result = client.post('/api/v1/sellers/connect', headers=auth(users[0]), json=payload)
        assert result.status_code == 200, result.text
        assert result.json()['dodo_connected'] and result.json()['dodo_webhook_managed']
        assert 'legacy-valid-key' not in result.text and 'whsec_' not in result.text
        provider[1][('GET', 'dodo', '/webhooks?limit=100')] = {
            'data': [{'id': 'whk_1', 'url': url, 'filter_types': ['payment.succeeded']}], 'done': True}
    config = db.get(SellerGatewayConfig, users[0].id)
    assert decrypt_secret(config.dodo_api_key_enc) == 'legacy-valid-key'
    assert decrypt_secret(config.dodo_webhook_secret_enc).startswith('whsec_')
    assert len([c for c in provider[0] if c[:3] == ('POST', 'dodo', '/webhooks')]) == 1
    assert config.dodo_webhook_url == url


def test_dodo_partial_failure_recovers_without_duplicate_endpoint(client, users, provider, db, monkeypatch):
    url = dodo_responses(provider, users[0])
    from backend.app.api.v1.endpoints import marketplace
    original = marketplace.gateway_request
    fail = [True]
    def request(method, gateway, path, **kwargs):
        if path.endswith('/secret') and fail[0]:
            raise HTTPException(502, 'Provider temporarily unavailable')
        return original(method, gateway, path, **kwargs)
    monkeypatch.setattr(marketplace, 'gateway_request', request)
    payload = {'gateway_type': 'dodo', 'api_key': 'legacy-key', 'environment': 'test'}
    assert client.post('/api/v1/sellers/connect', headers=auth(users[0]), json=payload).status_code == 502
    assert db.get(SellerGatewayConfig, users[0].id) is None
    fail[0] = False
    provider[1][('GET', 'dodo', '/webhooks?limit=100')] = {
        'data': [{'id': 'whk_1', 'url': url, 'disabled': True}], 'done': True}
    assert client.post('/api/v1/sellers/connect', headers=auth(users[0]), json=payload).status_code == 200
    assert len([c for c in provider[0] if c[:3] == ('POST', 'dodo', '/webhooks')]) == 1


def test_dodo_existing_manual_endpoint_is_adopted(client, users, provider, db):
    connect(client, users[0], 'dodo')
    url = dodo_responses(provider, users[0])
    provider[1][('GET', 'dodo', '/webhooks?limit=100')] = {
        'data': [{'id': 'whk_1', 'url': url}], 'done': True}
    result = client.post('/api/v1/sellers/connect', headers=auth(users[0]), json={
        'gateway_type': 'dodo', 'api_key': 'seller-dodo-key', 'environment': 'test'})
    assert result.status_code == 200
    assert not any(c[:3] == ('POST', 'dodo', '/webhooks') for c in provider[0])


def test_dodo_mode_mismatch_rejected_before_provider_calls(client, users, provider):
    result = client.post('/api/v1/sellers/connect', headers=auth(users[0]), json={
        'gateway_type': 'dodo', 'api_key': 'dodo_test_example', 'environment': 'live'})
    assert result.status_code == 400
    assert not provider[0]


def test_dodo_paginated_lookup_adopts_existing_endpoint(client, users, provider):
    url = dodo_responses(provider, users[0])
    provider[1][('GET', 'dodo', '/webhooks?limit=100')] = {'data': [], 'done': False, 'iterator': 'next-cursor'}
    provider[1][('GET', 'dodo', '/webhooks?limit=100&iterator=next-cursor')] = {
        'data': [{'id': 'whk_1', 'url': url}], 'done': True}
    result = client.post('/api/v1/sellers/connect', headers=auth(users[0]), json={
        'gateway_type': 'dodo', 'api_key': 'legacy-key', 'environment': 'test'})
    assert result.status_code == 200
    assert not any(c[:3] == ('POST', 'dodo', '/webhooks') for c in provider[0])


@pytest.fixture
def oauth(monkeypatch):
    from backend.app.api.v1.endpoints import marketplace
    from backend.app.services import seller_onboarding
    monkeypatch.setattr(settings, 'SITE_URL', 'https://testserver')
    monkeypatch.setattr(settings, 'RAZORPAY_PARTNER_CLIENT_ID', 'partner-client')
    monkeypatch.setattr(settings, 'RAZORPAY_PARTNER_CLIENT_SECRET', 'partner-secret')
    monkeypatch.setattr(settings, 'RAZORPAY_PARTNER_WEBHOOK_SECRET', 'partner-webhook')
    tokens = {'access_token': 'oauth-access', 'refresh_token': 'oauth-refresh',
              'public_token': 'rzp_test_oauth_public', 'razorpay_account_id': 'acc_seller', 'expires_in': 3600}
    calls = []
    def exchange(payload):
        calls.append(payload)
        return tokens.copy()
    monkeypatch.setattr(marketplace, 'exchange_token', exchange)
    monkeypatch.setattr(seller_onboarding, 'exchange_token', exchange)
    return calls, tokens


def start_oauth(client, user):
    result = client.post('https://testserver/api/v1/sellers/razorpay/oauth/start', headers=auth(user))
    assert result.status_code == 200, result.text
    query = parse_qs(urlsplit(result.json()['authorization_url']).query)
    assert query['scope'] == ['read_write']
    return query['state'][0]


def finish_oauth(client, user, state):
    return client.get('https://testserver/api/v1/sellers/razorpay/oauth/callback',
                      params={'code': 'one-use-code', 'state': state}, headers=auth(user), follow_redirects=False)


def test_oauth_state_binding_and_replay(client, users, provider, oauth, db):
    state = start_oauth(client, users[0])
    assert state != users[0].id
    saved = db.get(SellerOAuthState, hashlib.sha256(state.encode()).hexdigest())
    assert saved and saved.used_at is None
    response = finish_oauth(client, users[0], state)
    assert response.status_code == 303 and 'razorpay=connected' in response.headers['location']
    config = db.get(SellerGatewayConfig, users[0].id)
    assert config.has_razorpay and config.razorpay_key_secret_enc is None
    assert decrypt_secret(config.razorpay_access_token_enc) == 'oauth-access'
    assert provider[0][-1][3]['oauth'] is True
    assert finish_oauth(client, users[0], state).status_code == 400
    assert len(oauth[0]) == 1


@pytest.mark.parametrize('reason', ['expired', 'different-user', 'missing-cookie'])
def test_oauth_rejects_wrong_browser_user_or_expiry(client, users, provider, oauth, db, reason):
    state = start_oauth(client, users[0])
    user = users[0]
    if reason == 'expired':
        db.get(SellerOAuthState, hashlib.sha256(state.encode()).hexdigest()).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif reason == 'different-user':
        users[1].tier = UserTier.ADMIN
        user = users[1]
    else:
        client.cookies.clear()
    db.commit()
    assert finish_oauth(client, user, state).status_code == 400
    assert not oauth[0]
    assert db.query(SellerGatewayConfig).count() == 0


def test_oauth_disabled_without_partner_config_and_requires_pro(client, users):
    assert client.post('/api/v1/sellers/razorpay/oauth/start', headers=auth(users[0])).status_code == 503
    assert client.post('/api/v1/sellers/razorpay/oauth/start', headers=auth(users[1])).status_code == 403


def test_oauth_refresh_and_revocation(client, users, provider, oauth, db):
    state = start_oauth(client, users[0])
    assert finish_oauth(client, users[0], state).status_code == 303
    config = db.get(SellerGatewayConfig, users[0].id)
    config.razorpay_token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    oauth[1].update(access_token='rotated-access', refresh_token='rotated-refresh')
    assert oauth_access_token(config) == 'rotated-access'
    assert oauth[0][-1]['grant_type'] == 'refresh_token'
    # Rotation persists even if the surrounding checkout later rolls back.
    db.rollback()
    assert decrypt_secret(db.get(SellerGatewayConfig, users[0].id).razorpay_refresh_token_enc) == 'rotated-refresh'
    body, headers = signed({'event': 'account.app.authorization_revoked', 'account_id': 'acc_seller'}, 'razorpay', 'partner-webhook')
    assert client.post('/api/v1/webhooks/razorpay/partner', content=body, headers=headers).status_code == 200
    assert not db.get(SellerGatewayConfig, users[0].id).has_razorpay
    with pytest.raises(HTTPException):
        oauth_access_token(db.get(SellerGatewayConfig, users[0].id))


def test_oauth_checkout_uses_bearer_and_public_token(client, users, asset, provider, oauth, db):
    state = start_oauth(client, users[0])
    assert finish_oauth(client, users[0], state).status_code == 303
    result = client.post(f'/api/v1/assets/{asset.slug}/buy', headers={**auth(users[1]), 'CF-IPCountry': 'IN'})
    assert result.status_code == 200
    assert result.json()['key_id'] == 'rzp_test_oauth_public'
    assert 'oauth-access' not in result.text and 'oauth-refresh' not in result.text
    assert provider[0][-1][3]['key'] == 'oauth-access' and provider[0][-1][3]['oauth'] is True
    provider[1][('GET', 'razorpay', '/payments/pay_1')] = {
        'order_id': 'order_1', 'status': 'captured', 'captured': True, 'amount': 42625, 'currency': 'INR'}
    signature = hmac.new(b'partner-secret', b'order_1|pay_1', hashlib.sha256).hexdigest()
    verify = client.post(f'/api/v1/assets/{asset.slug}/verify-payment', headers=auth(users[1]), json={
        'payment_reference': result.json()['payment_reference'], 'payment_id': 'pay_1', 'signature': signature})
    assert verify.status_code == 200 and verify.json()['unlocked']
    event = {'event': 'order.paid', 'account_id': 'acc_seller',
             'payload': {'payment': {'entity': {'id': 'pay_1', 'order_id': 'order_1'}}}}
    body, headers = signed(event, 'razorpay', 'partner-webhook')
    assert client.post('/api/v1/webhooks/razorpay/partner', content=body, headers=headers).status_code == 200
    assert db.query(AssetPurchase).count() == 1


def test_partner_webhook_ignores_unrelated_merchant_orders(client, users, provider, oauth, db):
    state = start_oauth(client, users[0])
    assert finish_oauth(client, users[0], state).status_code == 303
    calls_before = len(provider[0])
    for account in ['acc_unrelated', 'acc_seller']:
        event = {'event': 'order.paid', 'account_id': account,
                 'payload': {'payment': {'entity': {'id': 'pay_unknown', 'order_id': 'order_unknown'}}}}
        body, headers = signed(event, 'razorpay', 'partner-webhook', event_id=account)
        assert client.post('/api/v1/webhooks/razorpay/partner', content=body, headers=headers).status_code == 200
    assert len(provider[0]) == calls_before
    assert db.query(AssetPurchase).count() == 0


def buy(client, users, asset, provider, gateway='razorpay'):
    connect(client, users[0], gateway)
    result = client.post(f'/api/v1/assets/{asset.slug}/buy', headers={**auth(users[1]), 'CF-IPCountry': 'IN' if gateway == 'razorpay' else 'US'})
    assert result.status_code == 200, result.text
    provider[1][('GET', gateway, '/payments/pay_1')] = {
        'id': 'pay_1', 'order_id': 'order_1', 'status': 'captured', 'captured': True,
        'amount': 42625, 'currency': 'INR',
    }
    provider[1][('GET', gateway, '/orders/order_1/payments')] = {'items': [{'id': 'pay_1', 'status': 'captured'}]}
    return result.json()['payment_reference']


def test_verify_checkout_signature_and_webhook_are_idempotent(client, users, asset, provider, db):
    reference = buy(client, users, asset, provider)
    signature = hmac.new(b'seller-secret', b'order_1|pay_1', hashlib.sha256).hexdigest()
    path = f'/api/v1/assets/{asset.slug}/verify-payment'
    payload = {'payment_reference': reference, 'payment_id': 'pay_1', 'signature': '0' * 64}
    assert client.post(path, headers=auth(users[1]), json=payload).status_code == 401
    assert db.query(AssetPurchase).count() == 0
    payload['signature'] = signature
    assert client.post(path, headers=auth(users[1]), json=payload).json()['unlocked']
    assert client.post(path, headers=auth(users[1]), json=payload).json()['unlocked']
    event = {'event': 'order.paid', 'payload': {'payment': {'entity': {'id': 'pay_1', 'order_id': 'order_1'}}}}
    body, headers = signed(event, 'razorpay', 'seller-hook')
    assert client.post('/api/v1/webhooks/razorpay/seller', content=body, headers=headers).status_code == 200
    assert db.query(AssetPurchase).count() == 1
    assert db.get(PendingCheckout, reference).status == CheckoutStatus.PAID


@pytest.mark.parametrize('scenario', ['buyer', 'asset', 'currency', 'amount', 'authorized'])
def test_verify_rejects_unrelated_or_unpaid_checkouts(client, users, asset, provider, db, scenario):
    reference = buy(client, users, asset, provider)
    user, slug = users[1], asset.slug
    if scenario == 'buyer': user = users[0]
    elif scenario == 'asset': slug = 'another-prompt'
    elif scenario == 'currency': provider[1][('GET', 'razorpay', '/payments/pay_1')]['currency'] = 'USD'
    elif scenario == 'amount': provider[1][('GET', 'razorpay', '/payments/pay_1')]['amount'] = 1
    else: provider[1][('GET', 'razorpay', '/payments/pay_1')]['status'] = 'authorized'
    result = client.post(f'/api/v1/assets/{slug}/verify-payment', headers=auth(user), json={'payment_reference': reference})
    assert result.status_code in {400, 404}
    assert db.query(AssetPurchase).count() == 0


def test_dodo_verify_reads_provider_session_and_product(client, users, asset, provider, db):
    reference = buy(client, users, asset, provider, 'dodo')
    provider[1][('GET', 'dodo', '/checkouts/checkout_1')] = {'payment_status': 'succeeded', 'payment_id': 'pay_1'}
    provider[1][('GET', 'dodo', '/payments/pay_1')] = {
        'payment_id': 'pay_1', 'status': 'succeeded', 'checkout_session_id': 'checkout_1',
        'total_amount': 500, 'currency': 'USD', 'product_cart': [{'product_id': 'seller-product', 'quantity': 1}]}
    result = client.post(f'/api/v1/assets/{asset.slug}/verify-payment', headers=auth(users[1]), json={'payment_reference': reference})
    assert result.status_code == 200 and result.json()['unlocked']
    assert db.query(AssetPurchase).count() == 1


def test_pending_order_does_not_grant_access(client, users, asset, provider, db):
    reference = buy(client, users, asset, provider)
    provider[1][('GET', 'razorpay', '/orders/order_1')] = {'status': 'attempted'}
    result = client.post(f'/api/v1/assets/{asset.slug}/verify-payment', headers=auth(users[1]), json={'payment_reference': reference})
    assert result.status_code == 202 and not result.json()['unlocked']
    assert db.query(AssetPurchase).count() == 0
