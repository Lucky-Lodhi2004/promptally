"""OAuth integration tests use isolated DBs and the existing Google verifier seam."""
import base64
import hashlib
from datetime import timedelta
from urllib.parse import urlsplit, parse_qs

import pytest
from backend.app.core.security import create_access_token
from backend.app.api.v1.endpoints.mcp_oauth import (
    digest, resource_url, now, MCPAuthorization, MCPGrant, MCPToken,
)

CALLBACK = 'http://127.0.0.1:8765/callback'
VERIFIER = 'v' * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b'=').decode()


def register(client, **overrides):
    return client.post('/api/v1/oauth/register', json={
        'client_name': 'Test editor', 'redirect_uris': [CALLBACK], **overrides})


def start(client, client_id, **overrides):
    return client.get('/api/v1/oauth/authorize', params={
        'client_id': client_id, 'redirect_uri': CALLBACK, 'response_type': 'code',
        'code_challenge': CHALLENGE, 'code_challenge_method': 'S256',
        'resource': resource_url(), 'scope': 'mcp:read', 'state': 'client-state', **overrides},
        follow_redirects=False)


def browser_login(client, user, db):
    user.google_sub = 'google-' + user.id
    db.commit()
    client.cookies.set('access_token', create_access_token(user.id, token_version=user.token_version))


def authorization_code(client, users, db, **overrides):
    cid = register(client).json()['client_id']
    response = start(client, cid, **overrides)
    assert response.status_code == 303
    handle = parse_qs(urlsplit(response.headers['location']).query)['request'][0]
    browser_login(client, users[1], db)
    response = client.post('/api/v1/oauth/requests/' + handle, json={'approved': True})
    assert response.status_code == 200, response.text
    query = parse_qs(urlsplit(response.json()['redirect_url']).query)
    assert query['state'] == ['client-state']
    return cid, query['code'][0], handle


def exchange(client, cid, code, **overrides):
    return client.post('/api/v1/oauth/token', data={
        'grant_type': 'authorization_code', 'client_id': cid, 'code': code,
        'redirect_uri': CALLBACK, 'code_verifier': VERIFIER, 'resource': resource_url(), **overrides})


def refresh(client, cid, token, **overrides):
    return client.post('/api/v1/oauth/token', data={
        'grant_type': 'refresh_token', 'client_id': cid, 'refresh_token': token,
        'resource': resource_url(), **overrides})


def call(client, token=None, **kw):
    return client.post('/api/v1/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                       headers={'Authorization': 'Bearer ' + token} if token else {}, **kw)


def test_discovery_and_all_mcp_shapes_require_token(client, users, db):
    metadata = client.get('/.well-known/oauth-protected-resource').json()
    assert metadata['resource'] == resource_url()
    assert metadata['authorization_servers'] == ['https://testserver']
    assert client.get('/.well-known/oauth-protected-resource/api/v1/mcp').json() == metadata
    server = client.get('/.well-known/oauth-authorization-server').json()
    assert server['code_challenge_methods_supported'] == ['S256']
    assert server['registration_endpoint'].endswith('/api/v1/oauth/register')
    for body in ({'method': 'tools/list'}, [], {'jsonrpc': '2.0', 'method': 'notifications/initialized'}):
        response = client.post('/api/v1/mcp', json=body)
        assert response.status_code == 401
        assert 'resource_metadata=' in response.headers['www-authenticate']
    browser_login(client, users[1], db)
    assert call(client).status_code == 401  # Website cookie cannot authenticate MCP.
    assert call(client, create_access_token(users[1].id)).status_code == 401
    assert call(client, 'a-google-id-token').status_code == 401


def test_full_authorization_rotation_and_replay(client, users, db):
    cid, code, handle = authorization_code(client, users, db)
    result = exchange(client, cid, code)
    assert result.status_code == 200
    assert result.headers['cache-control'] == 'private, no-store'
    tokens = result.json()
    assert tokens['scope'] == 'mcp:read' and tokens['expires_in'] <= 3600
    assert call(client, tokens['access_token']).status_code == 200
    assert client.post('/api/v1/oauth/requests/' + handle, json={'approved': True}).status_code == 400
    assert exchange(client, cid, code).json()['error'] == 'invalid_grant'
    assert db.get(MCPToken, digest(tokens['access_token'])) is not None
    assert db.query(MCPToken).first().refresh_hash != tokens['refresh_token']
    renewed = refresh(client, cid, tokens['refresh_token'])
    assert renewed.status_code == 200
    assert renewed.json()['refresh_token'] != tokens['refresh_token']
    assert call(client, renewed.json()['access_token']).status_code == 200
    assert refresh(client, cid, tokens['refresh_token']).json()['error'] == 'invalid_grant'
    assert call(client, renewed.json()['access_token']).status_code == 401


@pytest.mark.parametrize('overrides', [
    {'redirect_uri': 'https://attacker.example/callback'}, {'code_challenge_method': 'plain'},
    {'code_challenge': 'short'}, {'scope': 'admin'}, {'resource': 'https://other.example/mcp'},
    {'response_type': 'token'},
])
def test_bad_authorization_requests_never_redirect(client, overrides):
    cid = register(client).json()['client_id']
    response = start(client, cid, **overrides)
    assert response.status_code == 400 and 'location' not in response.headers


@pytest.mark.parametrize('uri', ['http://example.com/callback', 'javascript:alert(1)',
    'https://user:pass@example.com/callback', 'https://example.com/callback#fragment',
    'http://127.0.0.1.evil.example/callback', 'https://example.com:broken/callback'])
def test_registration_rejects_unsafe_redirects(client, uri):
    assert register(client, redirect_uris=[uri]).json()['error'] == 'invalid_redirect_uri'


def test_code_binding_and_expiry(client, users, db):
    cid, code, _ = authorization_code(client, users, db)
    other = register(client).json()['client_id']
    for changes in ({'code_verifier': 'wrong' * 12}, {'redirect_uri': 'https://evil.example/'},
                    {'client_id': other}, {'resource': 'https://evil.example/mcp'}):
        assert exchange(client, cid, code, **changes).status_code == 400
    row = db.query(MCPAuthorization).filter_by(code_hash=digest(code)).one()
    row.code_expires_at = now() - timedelta(seconds=1)
    db.commit()
    assert exchange(client, cid, code).json()['error'] == 'invalid_grant'


def test_browser_binding_google_requirement_and_denial(client, users, db):
    cid = register(client).json()['client_id']
    response = start(client, cid)
    handle = parse_qs(urlsplit(response.headers['location']).query)['request'][0]
    path = '/api/v1/oauth/requests/' + handle
    assert client.get(path).json()['client_name'] == 'Test editor'
    assert client.post(path, json={'approved': True}).status_code == 403
    client.cookies.set('access_token', create_access_token(users[1].id))
    assert client.post(path, json={'approved': True}).status_code == 403
    response = client.post(path, json={'approved': False})
    query = parse_qs(urlsplit(response.json()['redirect_url']).query)
    assert query == {'error': ['access_denied'], 'state': ['client-state']}
    response = start(client, cid)
    handle = parse_qs(urlsplit(response.headers['location']).query)['request'][0]
    client.cookies.clear()
    assert client.get('/api/v1/oauth/requests/' + handle).status_code == 400


def test_revocation_logout_and_expiry(client, users, db):
    cid, code, _ = authorization_code(client, users, db)
    tokens = exchange(client, cid, code).json()
    record = db.get(MCPToken, digest(tokens['access_token']))
    record.access_expires_at = now() - timedelta(seconds=1)
    db.commit()
    assert call(client, tokens['access_token']).status_code == 401
    renewed = refresh(client, cid, tokens['refresh_token']).json()
    assert call(client, renewed['access_token']).status_code == 200
    assert client.post('/api/v1/oauth/revoke', data={'client_id': cid, 'token': renewed['refresh_token']}).status_code == 200
    assert call(client, renewed['access_token']).status_code == 401
    assert refresh(client, cid, renewed['refresh_token']).status_code == 400
    cid, code, _ = authorization_code(client, users, db)
    tokens = exchange(client, cid, code).json()
    users[1].token_version += 1
    db.commit()
    assert call(client, tokens['access_token']).status_code == 401
    assert refresh(client, cid, tokens['refresh_token']).status_code == 400


def test_missing_resource_duplicate_parameters_and_csrf(client, users, db):
    cid, code, _ = authorization_code(client, users, db)
    assert exchange(client, cid, code, resource='').json()['error'] == 'invalid_target'
    response = client.post('/api/v1/oauth/token', content='grant_type=authorization_code&grant_type=refresh_token',
                           headers={'Content-Type': 'application/x-www-form-urlencoded'})
    assert response.json()['error'] == 'invalid_request'
    assert client.post('/api/v1/oauth/requests/anything', json={'approved': True},
                       headers={'Origin': 'https://evil.example'}).status_code == 403
