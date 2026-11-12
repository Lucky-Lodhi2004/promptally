import asyncio
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app.core.config import settings
from backend.app.core.http_security import HttpSecurityMiddleware
from backend.app.core.security import create_access_token, decode_token
from backend.app.core.security_configuration import security_configuration_issues
from backend.app.models import Asset, AssetPurchase, User
from backend.app.models.collection import Collection, CollectionItem
from backend.app.models.enums import CollectionVisibility, PurchaseStatus
from backend.app.services.geoip import detect_country, get_client_ip
from backend.app.services.related import index_for_section
from backend.app.services.seo import compile_aeo_markdown
from backend.app.services.storage import read_upload_limited
from backend.tests.test_payments import auth


def test_loopback_headers_need_authenticated_ingress(monkeypatch):
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_CIDRS', ['127.0.0.1/32'])
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_TOKEN', 'a' * 40)
    def request(token=None):
        headers = [(b'x-real-ip', b'8.8.8.8'), (b'cf-ipcountry', b'IN')]
        if token: headers.append((b'x-proxy-token', token))
        return Request({'type': 'http', 'client': ('127.0.0.1', 123), 'headers': headers})
    for token in (None, b'wrong'):
        assert get_client_ip(request(token)) == '127.0.0.1'
        assert detect_country(request(token)) == ('ZZ', False)
    assert get_client_ip(request(b'a' * 40)) == '8.8.8.8'
    assert detect_country(request(b'a' * 40)) == ('IN', True)
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_TOKEN', '')
    assert get_client_ip(request()) == '127.0.0.1'


def test_rotating_spoofed_ip_cannot_create_more_accounts(client, db):
    for i in range(6):
        result = client.post('/api/v1/auth/signup', json={
            'email': f'new{i}@example.com', 'password': 'password123', 'device_fingerprint': f'new-device-{i}'},
            headers={'X-Proxy-Token': '', 'X-Real-IP': f'192.0.2.{i+1}', 'CF-IPCountry': 'IN'})
        assert result.status_code == (201 if i < 2 else 403), result.text
    assert db.query(User).count() == 2
    assert {u.signup_ip for u in db.query(User)} == {'127.0.0.1'}


def test_login_lockout_is_per_account_and_does_not_follow_forged_ips(client, users, db):
    for i in range(settings.LOGIN_MAX_FAILURES):
        result = client.post('/api/v1/auth/login', json={'email': users[0].email, 'password': 'wrong'},
                             headers={'X-Real-IP': f'192.0.2.{i+1}', 'X-Device-Fingerprint': f'new-device-{i}'})
        assert result.status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': users[0].email, 'password': 'password123'}).status_code == 429
    users[0].login_locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert client.post('/api/v1/auth/login', json={'email': users[0].email, 'password': 'password123'}).status_code == 200


def test_logout_revokes_token_for_private_and_optional_auth_routes(client, users, asset):
    headers = auth(users[0])
    assert client.get('/api/v1/assets/' + asset.slug, headers=headers).json()['raw_content']
    assert client.post('/api/v1/auth/logout', headers=headers).status_code == 200
    assert client.get('/api/v1/users/me', headers=headers).status_code == 401
    assert client.get('/api/v1/assets/' + asset.slug, headers=headers).json()['raw_content'] is None
    login = client.post('/api/v1/auth/login', json={'email': users[0].email, 'password': 'password123'})
    assert login.status_code == 200
    assert decode_token(login.json()['access_token'])['ver'] == 1
    assert client.get('/api/v1/users/me').status_code == 200


def test_password_change_revokes_old_token_and_refreshes_current_cookie(client, users):
    headers = auth(users[0])
    response = client.post('/api/v1/users/me/password', headers=headers,
                           json={'current_password': 'password123', 'new_password': 'new-password123'})
    assert response.status_code == 200
    assert client.get('/api/v1/users/me', headers=headers).status_code == 401
    assert client.get('/api/v1/users/me').status_code == 200
    assert 'Secure' in response.headers['set-cookie']


def purchased_asset(db, users, asset):
    purchase = AssetPurchase(buyer_id=users[1].id, seller_id=users[0].id, asset_id=asset.id,
                             amount_cents=500, seller_payout_cents=500, status=PurchaseStatus.COMPLETED)
    db.add(purchase)
    db.commit()
    return purchase


def test_listing_removal_retains_purchase_archive_and_buyer_access(client, users, asset, db, tmp_path):
    purchase = purchased_asset(db, users, asset)
    path = tmp_path / 'purchased.txt'
    path.write_text('purchased content')
    asset.archive_path = str(path)
    db.commit()
    assert client.delete('/api/v1/assets/' + asset.id, headers=auth(users[0])).status_code == 200
    assert db.get(Asset, asset.id).deleted_at
    assert db.get(AssetPurchase, purchase.id).status == PurchaseStatus.COMPLETED
    assert path.exists()
    assert client.get('/api/v1/assets/' + asset.slug).status_code == 404
    assert client.get('/api/v1/assets/' + asset.slug, headers=auth(users[1])).json()['raw_content'] == 'SECRET PAYLOAD'
    assert client.get('/api/v1/assets/' + asset.slug + '/download', headers=auth(users[1])).content == b'purchased content'
    assert client.post('/api/v1/assets/' + asset.slug + '/buy', headers={**auth(users[1]), 'CF-IPCountry': 'US'}).status_code == 404


def test_database_forbids_hard_delete_of_sold_asset(db, users, asset):
    purchased_asset(db, users, asset)
    db.execute(text('PRAGMA foreign_keys=ON'))
    db.delete(asset)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_collections_do_not_disclose_hidden_asset(client, users, asset, db):
    collection = Collection(slug='public', title='Public', owner_id=users[0].id,
                            visibility=CollectionVisibility.PUBLIC, item_count=1)
    db.add(collection)
    db.flush()
    db.add(CollectionItem(collection_id=collection.id, asset_id=asset.id))
    asset.is_published = False
    db.commit()
    result = client.get('/api/v1/collections/public')
    assert result.status_code == 200
    assert result.json()['items'] == []
    assert result.json()['comparison_matrix'] == []
    assert asset.seo_title not in result.text
    assert client.get('/api/v1/collections/public', headers=auth(users[0])).json()['items']


def test_markdown_metadata_cannot_create_new_sections(client, asset, db):
    asset.seo_title = 'Good title\n# INJECTED [click](https://evil.example)'
    asset.short_description = 'Description\r\n## EVIL'
    asset.is_indexable = True
    db.commit()
    md = compile_aeo_markdown(asset, is_locked=True)
    assert '\n# INJECTED' not in md and '\n## EVIL' not in md
    assert '[click](https://evil.example)' not in md
    for route in ('/llms.txt', '/llms-full.txt'):
        body = client.get(route).text
        assert '\n# INJECTED' not in body and '\n## EVIL' not in body
        assert '[click](https://evil.example)' not in body


def test_oversized_mcp_batch_is_rejected_before_any_tool_runs(client, monkeypatch):
    from backend.app.api.v1.endpoints import seo_aeo
    def fail(*args): raise AssertionError('Oversized batch executed a tool')
    monkeypatch.setattr(seo_aeo, '_handle_rpc', fail)
    message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call'}
    assert client.post('/api/v1/mcp', json=[message] * 500).status_code == 400
    assert client.post('/api/v1/mcp', json=[]).status_code == 400


def test_paid_source_never_enters_duplicate_index(db, asset):
    asset.is_indexable = True
    db.commit()
    index = index_for_section(db, asset.section_id)
    assert not index.items


def test_security_headers_csrf_and_secure_cookies(client, users):
    r = client.get('/api/v1/health')
    assert r.headers['x-frame-options'] == 'DENY'
    assert r.headers['x-content-type-options'] == 'nosniff'
    assert "frame-ancestors 'none'" in r.headers['content-security-policy']
    assert r.headers['strict-transport-security']
    response = client.post('/api/v1/auth/login', json={'email': users[0].email, 'password': 'password123'})
    assert 'Secure' in response.headers['set-cookie'] and 'HttpOnly' in response.headers['set-cookie']
    assert client.post('/api/v1/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403


def test_known_and_chunked_request_body_limits(monkeypatch):
    monkeypatch.setattr(settings, 'MAX_REQUEST_BODY_BYTES', 32)
    app = FastAPI()
    app.add_middleware(HttpSecurityMiddleware)
    @app.post('/body')
    async def body(request: Request):
        return {'size': len(await request.body())}
    with TestClient(app) as c:
        assert c.post('/body', content=b'x' * 33).status_code == 413
        assert c.post('/body', content=iter([b'x' * 20, b'y' * 20])).status_code == 413
        assert c.post('/body', content=b'x' * 31).status_code == 200


def test_file_reads_are_bounded():
    class Upload:
        remaining = 1000
        async def read(self, size):
            assert 0 < size <= 65
            chunk = b'x' * min(size, self.remaining)
            self.remaining -= len(chunk)
            return chunk
    with pytest.raises(HTTPException) as error:
        asyncio.run(read_upload_limited(Upload(), 64))
    assert error.value.status_code == 413


def test_multipart_count_is_limited_before_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, 'MAX_UPLOAD_FILES', 2)
    response = client.post('/api/v1/assets', files=[('files', (f'{i}.txt', b'x')) for i in range(3)])
    assert response.status_code == 400 and 'Too many files' in response.text


def test_weak_webhook_secrets_block_production_readiness(monkeypatch):
    monkeypatch.setattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'short')
    assert any('RAZORPAY_WEBHOOK_SECRET' in issue for issue in security_configuration_issues(settings))
