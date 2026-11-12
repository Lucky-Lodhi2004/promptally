from datetime import datetime, timedelta, timezone
import pytest
from backend.app.models import User
from backend.app.models.registration import EmailChallenge, EmailOutbox, SignupQuota
from backend.app.services.crypto import decrypt_secret
from backend.app.services import email_verification
from backend.app.worker import deliver_outbox
from backend.app.core.security import create_access_token


def signup(client, email='new@example.com', device='test-device', ip=None):
    return client.post('/api/v1/auth/signup', json={'email': email, 'password': 'password123',
        'device_fingerprint': device}, headers={'X-Real-IP': ip} if ip else {})


def test_signup_requires_verification_and_token_is_single_use(client, db):
    response = signup(client)
    assert response.status_code == 201, response.text
    assert response.json()['user']['email_verified'] is False
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    assert client.get('/api/v1/users/me', headers=headers).status_code == 200
    assert client.get('/api/v1/billing/subscription', headers=headers).status_code == 403
    row = db.query(EmailOutbox).one()
    token = decrypt_secret(row.token_enc)
    assert token not in response.text
    assert db.query(EmailChallenge).one().token_hash != token
    verified = client.post('/api/v1/auth/verify-email', json={'token': token})
    assert verified.status_code == 200
    assert client.post('/api/v1/auth/verify-email', json={'token': token}).status_code == 400
    assert client.get('/api/v1/billing/subscription', headers=headers).status_code == 200
    assert client.get('/api/v1/users/me', headers=headers).json()['email_verified']


def test_expired_link_and_resend_invalidate_previous_link(client, db):
    result = signup(client)
    headers = {'Authorization': 'Bearer ' + result.json()['access_token']}
    row = db.query(EmailOutbox).one(); old_token = decrypt_secret(row.token_enc)
    assert client.post('/api/v1/auth/resend-verification', headers=headers).status_code == 429
    challenge = db.query(EmailChallenge).one()
    challenge.created_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    challenge.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert client.post('/api/v1/auth/verify-email', json={'token': old_token}).status_code == 400
    assert client.post('/api/v1/auth/resend-verification', headers=headers).status_code == 200
    assert client.post('/api/v1/auth/verify-email', json={'token': old_token}).status_code == 400
    fresh = db.query(EmailOutbox).filter_by(status='pending').one()
    assert client.post('/api/v1/auth/verify-email', json={'token': decrypt_secret(fresh.token_enc)}).status_code == 200


def test_ip_and_device_quotas_are_independent_and_durable(client, db):
    assert signup(client, 'a@example.com', 'device-a', '192.0.2.1').status_code == 201
    assert signup(client, 'b@example.com', 'device-b', '192.0.2.1').status_code == 201
    assert signup(client, 'c@example.com', 'device-c', '192.0.2.1').status_code == 403
    assert signup(client, 'd@example.com', 'device-a', '192.0.2.2').status_code == 201
    assert signup(client, 'e@example.com', 'device-a', '192.0.2.3').status_code == 403
    # Account deletion must not reset successful registration counters.
    db.query(EmailOutbox).delete(); db.query(EmailChallenge).delete(); db.query(User).delete(); db.commit()
    assert signup(client, 'f@example.com', 'device-new', '192.0.2.1').status_code == 403
    assert signup(client, 'g@example.com', 'device-a', '192.0.2.9').status_code == 403
    assert max(row.used for row in db.query(SignupQuota)) == 2


def test_missing_fingerprint_does_not_bypass_signup(client, db):
    response = client.post('/api/v1/auth/signup', json={'email': 'no-device@example.com', 'password': 'password123'})
    assert response.status_code == 400
    assert db.query(User).count() == 0
    assert db.query(SignupQuota).count() == 0


def test_delivery_retry_uses_same_link_and_deduplicates_sent_task(client, db, monkeypatch):
    from backend.app import worker
    signup(client)
    row = db.query(EmailOutbox).one()
    token = decrypt_secret(row.token_enc)
    sent = []
    def fail(recipient, value):
        sent.append(value)
        raise RuntimeError('SMTP unavailable')
    monkeypatch.setattr(worker, 'smtp_send', fail)
    deliver_outbox(db, row.id)
    db.refresh(row)
    assert row.status == 'pending' and row.attempts == 1
    assert decrypt_secret(row.token_enc) == token
    row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
    monkeypatch.setattr(worker, 'smtp_send', lambda recipient, value: sent.append(value))
    deliver_outbox(db, row.id)
    assert row.status == 'sent' and not row.token_enc
    deliver_outbox(db, row.id)
    assert sent == [token, token]


def test_old_worker_task_does_not_send_invalidated_email(client, db, monkeypatch):
    from backend.app import worker
    response = signup(client)
    old = db.query(EmailOutbox).one(); old_id = old.id
    challenge = db.query(EmailChallenge).one()
    challenge.created_at = datetime.now(timezone.utc) - timedelta(minutes=2); db.commit()
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    assert client.post('/api/v1/auth/resend-verification', headers=headers).status_code == 200
    sent = []
    monkeypatch.setattr(worker, 'smtp_send', lambda *args: sent.append(args))
    deliver_outbox(db, old_id)
    assert not sent


def test_broker_outage_preserves_user_challenge_and_outbox(client, db, monkeypatch):
    from backend.app.api.v1.endpoints import auth
    from backend.app.worker import send_verification_email
    monkeypatch.setattr(auth, 'kick_delivery', email_verification.kick_delivery)
    def unavailable(*args, **kwargs): raise ConnectionError('broker unavailable')
    monkeypatch.setattr(send_verification_email, 'apply_async', unavailable)
    assert signup(client).status_code == 201
    assert db.query(User).count() == db.query(EmailChallenge).count() == db.query(EmailOutbox).count() == 1
    assert db.query(EmailOutbox).one().status == 'pending'


def test_google_verified_signup_shares_quotas_without_email_task(client, db, google_signin):
    identity = {'email': 'google@gmail.com', 'email_verified': True, 'sub': 'google-sub', 'name': 'Google user'}
    result = google_signin.login(identity)
    assert result.status_code == 200, result.text
    assert result.json()['user']['email_verified']
    assert db.query(EmailOutbox).count() == 0
    assert signup(client, 'email@example.com', 'other-device').status_code == 201
    identity.update(email='another-google@gmail.com', sub='other-google-sub')
    assert google_signin.login(identity, 'third-device').status_code == 403


def test_smtp_uses_tls_and_does_not_put_raw_token_in_queue_arguments(client, db, monkeypatch):
    from backend.app import worker
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, 'SMTP_HOST', 'smtp.example.test')
    monkeypatch.setattr(settings, 'SMTP_PASSWORD', 'test-only-password')
    calls = []
    class FakeSMTP:
        def __init__(self, host, port, **kwargs): calls.append('connect')
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def ehlo(self): calls.append('ehlo')
        def starttls(self, **kwargs):
            assert kwargs['context'].check_hostname
            calls.append('tls')
        def login(self, username, password):
            assert 'tls' in calls
            assert username == 'contact@promptally.dev'
            calls.append('login')
        def send_message(self, message):
            assert message['From'] == 'contact@promptally.dev'
            assert '/verify-email#token=' in message.get_content()
            calls.append('send')
    monkeypatch.setattr(worker.smtplib, 'SMTP', FakeSMTP)
    assert signup(client).status_code == 201
    deliver_outbox(db, db.query(EmailOutbox).one().id)
    assert calls == ['connect', 'ehlo', 'tls', 'ehlo', 'login', 'send']


def test_redis_token_cache_is_optional_and_never_authoritative(client, db, redis_url, monkeypatch):
    from backend.app.core.config import settings
    from redis import Redis
    from backend.app.services.email_verification import cache_challenge
    result = signup(client)
    token = decrypt_secret(db.query(EmailOutbox).one().token_enc)
    challenge = db.query(EmailChallenge).one()
    monkeypatch.setattr(settings, 'REDIS_URL', redis_url)
    cache_challenge(challenge)
    client_redis = Redis.from_url(redis_url)
    key = 'promptally:verify:' + challenge.token_hash
    assert client_redis.ttl(key) > 0
    # Cached identity cannot override a replaced/expired database challenge.
    old_hash = challenge.token_hash
    challenge.token_hash = 'f' * 64; db.commit()
    assert client.post('/api/v1/auth/verify-email', json={'token': token}).status_code == 400
    challenge.token_hash = old_hash; db.commit()
    client_redis.delete(key)  # Simulate cache loss, preserving the durable valid token.
    assert client.post('/api/v1/auth/verify-email', json={'token': token}).status_code == 200
    client_redis.close()


def test_google_cannot_bless_unverified_pre_registered_password(client, db, google_signin):
    assert signup(client, 'owner@gmail.com').status_code == 201
    result = google_signin.login({'email': 'owner@gmail.com', 'email_verified': True, 'sub': 'real-owner-google'})
    assert result.status_code == 409
    assert db.query(User).one().email_verified_at is None
