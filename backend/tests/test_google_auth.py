import json
import time
import pytest
from jose import jwt
from backend.app.core.config import settings
from backend.app.models import User
from backend.app.models.registration import EmailOutbox, SignupQuota
from backend.app.models.enums import OAuthProvider
from datetime import datetime, timezone

IDENTITY = {'email': 'user@gmail.com', 'email_verified': True, 'sub': 'google-stable-sub', 'name': 'Google user'}


def test_google_start_never_exposes_secret(client, google_signin, monkeypatch):
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_SECRET', 'private-secret')
    result = client.post('/api/v1/auth/google/start', json={'device_fingerprint': 'google-device'})
    assert result.status_code == 200
    assert set(result.json()) == {'client_id', 'nonce', 'csrf_token', 'expires_in'}
    assert 'private-secret' not in result.text
    assert 'HttpOnly' in result.headers['set-cookie']


def test_signup_and_returning_google_login_do_not_spend_more_quota(client, google_signin, db):
    first = google_signin.login(IDENTITY)
    assert first.status_code == 200, first.text
    assert first.json()['user']['email_verified'] is True
    assert client.get('/api/v1/users/me').status_code == 200
    user_id = first.json()['user']['id']
    assert google_signin.login(IDENTITY).json()['user']['id'] == user_id
    assert db.query(User).count() == 1
    assert all(q.used == 1 for q in db.query(SignupQuota))
    assert db.query(EmailOutbox).count() == 0


def test_same_subject_with_changed_google_email_keeps_account(client, google_signin, db):
    first = google_signin.login(IDENTITY).json()['user']
    second = google_signin.login({**IDENTITY, 'email': 'new@gmail.com'}).json()['user']
    assert first['id'] == second['id']
    assert second['email'] == first['email']
    assert db.query(User).count() == 1


def test_nonce_replay_rejected(client, google_signin, db):
    payload = google_signin.start(IDENTITY)
    csrf = payload['csrf_token']
    assert client.post('/api/v1/auth/google', json=payload).status_code == 200
    # Even restoring the old browser cookie cannot resurrect the consumed nonce.
    client.cookies.set('promptally_google_csrf', csrf, path='/api/v1/auth/google')
    assert client.post('/api/v1/auth/google', json=payload).status_code == 400
    assert db.query(User).count() == 1


@pytest.mark.parametrize('change', ['missing-cookie', 'csrf', 'nonce', 'device', 'origin'])
def test_browser_binding_rejects_forged_or_expired_sessions(client, google_signin, db, change):
    payload = google_signin.start(IDENTITY)
    headers = {}
    if change == 'missing-cookie': client.cookies.clear()
    if change == 'csrf': payload['csrf_token'] = 'different-csrf'
    if change == 'nonce': google_signin.credentials[payload['credential']]['nonce'] = 'x' * 43
    if change == 'device': payload['device_fingerprint'] = 'forged-device'
    if change == 'origin': headers['Origin'] = 'https://evil.example'
    result = client.post('/api/v1/auth/google', json=payload, headers=headers)
    assert result.status_code in {400, 403}
    assert db.query(User).count() == 0


@pytest.mark.parametrize('overrides', [
    {'email_verified': False}, {'email_verified': 'false'}, {'email': None}, {'sub': ''},
    {'iss': 'https://evil.example'}, {'aud': 'other-client'}, {'exp': 1},
])
def test_invalid_identity_claims_rejected(client, google_signin, db, overrides):
    result = google_signin.login({**IDENTITY, **overrides})
    assert result.status_code == 400, result.text
    assert db.query(User).count() == 0


def test_third_party_google_address_requires_mail_verification(client, google_signin, db):
    result = google_signin.login({**IDENTITY, 'email': 'external@example.com'})
    assert result.status_code == 200
    assert result.json()['user']['email_verified'] is False
    assert db.query(EmailOutbox).count() == 1
    assert client.get('/api/v1/billing/subscription').status_code == 403


def test_verified_workspace_can_reuse_verified_email_account(client, google_signin, db):
    existing = User(email='person@example.com', username='existing', name='Existing',
        password_hash='existing-password-hash', email_verified_at=datetime.now(timezone.utc),
        email_verification_required=True, oauth_provider=OAuthProvider.EMAIL)
    db.add(existing); db.commit()
    result = google_signin.login({**IDENTITY, 'email': existing.email, 'hd': 'example.com'})
    assert result.status_code == 200, result.text
    assert result.json()['user']['id'] == existing.id
    db.refresh(existing)
    assert existing.google_sub == IDENTITY['sub']
    assert existing.password_hash == 'existing-password-hash'
    assert db.query(SignupQuota).count() == 0


def test_non_authoritative_email_does_not_link_existing_account(client, google_signin, db):
    existing = User(email='external@example.com', username='existing', name='Existing',
                    email_verified_at=datetime.now(timezone.utc), email_verification_required=True)
    db.add(existing); db.commit()
    assert google_signin.login({**IDENTITY, 'email': existing.email}).status_code == 409
    assert existing.google_sub is None


def test_redis_outage_fails_closed(client, google_signin, monkeypatch):
    monkeypatch.setattr(settings, 'REDIS_URL', '')
    result = client.post('/api/v1/auth/google/start', json={'device_fingerprint': 'google-device'})
    assert result.status_code == 503


@pytest.fixture(scope='module')
def rsa_keys():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, public


@pytest.mark.parametrize('fault', [None, 'signature', 'audience', 'issuer', 'expiry'])
def test_actual_google_library_verifies_signed_tokens(client, redis_url, monkeypatch, rsa_keys, fault):
    from backend.app.api.v1.endpoints import auth
    from google.oauth2 import id_token as actual_id_token
    from types import SimpleNamespace
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_ID', 'test-client')
    monkeypatch.setattr(settings, 'REDIS_URL', redis_url)
    monkeypatch.setattr(auth, 'HAS_GOOGLE_AUTH', True)
    monkeypatch.setattr(auth, 'id_token', actual_id_token)
    public = rsa_keys[1].decode()
    def certs(*args, **kwargs):
        return SimpleNamespace(status=200, data=json.dumps({'test-kid': public}).encode())
    monkeypatch.setattr(auth, 'google_certificate_request', lambda: certs)
    start = client.post('/api/v1/auth/google/start', json={'device_fingerprint': 'google-device'}).json()
    now = int(time.time())
    claims = {**IDENTITY, 'iss': 'https://accounts.google.com', 'aud': 'test-client',
        'iat': now, 'exp': now+3600, 'nonce': start['nonce']}
    if fault == 'audience': claims['aud'] = 'wrong-client'
    if fault == 'issuer': claims['iss'] = 'https://evil.example'
    if fault == 'expiry': claims.update(iat=now-7200, exp=now-3600)
    token = jwt.encode(claims, rsa_keys[0], algorithm='RS256', headers={'kid': 'test-kid'})
    if fault == 'signature':
        parts = token.split('.')
        parts[2] = ('A' if parts[2][0] != 'A' else 'B') + parts[2][1:]
        token = '.'.join(parts)
    result = client.post('/api/v1/auth/google', json={'credential': token,
        'csrf_token': start['csrf_token'], 'device_fingerprint': 'google-device'})
    assert result.status_code == (200 if fault is None else 400), result.text
