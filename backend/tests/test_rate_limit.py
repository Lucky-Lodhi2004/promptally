import uuid
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from backend.app.core.config import settings
from backend.app.core.rate_limit import RateLimitMiddleware, consume_sync


def limited_app(monkeypatch, redis_url, limit=2, window=60, read_limit=2):
    monkeypatch.setattr(settings, 'RATE_LIMIT_ENABLED', True)
    monkeypatch.setattr(settings, 'REDIS_URL', redis_url)
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_CIDRS', ['127.0.0.1/32'])
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_TOKEN', 'test-ingress-secret')
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, max_requests=limit, window_seconds=window, max_read_requests=read_limit)
    @app.api_route('/status', methods=['GET', 'HEAD', 'POST', 'PATCH', 'DELETE'])
    def status(): return {'ok': True}
    @app.post('/api/v1/webhooks/dodo')
    def webhook(): return {'ok': True}
    return app


def test_separate_60_read_and_10_sensitive_budgets_no_bot_bypass(monkeypatch, redis_url):
    app = limited_app(monkeypatch, redis_url, limit=10, read_limit=60)
    headers = {'X-Real-IP': '192.0.2.41', 'User-Agent': 'Googlebot',
               'X-Device-Fingerprint': 'device-' + uuid.uuid4().hex}
    with TestClient(app, client=('127.0.0.1', 1), headers={'X-Proxy-Token': 'test-ingress-secret'}) as client:
        for _ in range(59):
            response = client.get('/status', headers=headers)
            assert response.status_code == 200
            assert response.headers['X-RateLimit-Limit'] == '60'
        assert client.head('/status', headers=headers).status_code == 200
        blocked = client.get('/status', headers=headers)
        assert blocked.status_code == 429
        assert int(blocked.headers['Retry-After']) > 0
        for method in ['POST'] * 8 + ['PATCH', 'DELETE']:
            response = client.request(method, '/status', headers=headers)
            assert response.status_code == 200
            assert response.headers['X-RateLimit-Limit'] == '10'
        assert client.post('/status', headers=headers).status_code == 429
        assert client.post('/api/v1/webhooks/dodo', headers=headers).status_code == 200


def test_sensitive_exhaustion_leaves_reads_available_and_oauth_is_sensitive(monkeypatch, redis_url):
    app = limited_app(monkeypatch, redis_url)
    @app.get('/sellers/razorpay/oauth/callback')
    def callback(): return {'ok': True}
    headers = {'X-Real-IP': '192.0.2.42'}
    with TestClient(app, client=('127.0.0.1', 1), headers={'X-Proxy-Token': 'test-ingress-secret'}) as client:
        assert client.post('/status', headers=headers).status_code == 200
        assert client.get('/sellers/razorpay/oauth/callback', headers=headers).status_code == 200
        assert client.post('/status', headers=headers).status_code == 429
        assert client.get('/status', headers=headers).status_code == 200


def test_independent_ip_and_device_limits_across_workers(monkeypatch, redis_url):
    # Different middleware instances represent different server workers.
    app1 = limited_app(monkeypatch, redis_url)
    app2 = limited_app(monkeypatch, redis_url)
    device = 'device-' + uuid.uuid4().hex
    prefix = uuid.uuid4().int % 250
    with TestClient(app1, client=('127.0.0.1', 1), headers={'X-Proxy-Token': 'test-ingress-secret'}) as a, TestClient(app2, client=('127.0.0.1', 2), headers={'X-Proxy-Token': 'test-ingress-secret'}) as b:
        headers = {'X-Real-IP': f'198.51.{prefix}.1', 'X-Device-Fingerprint': device}
        assert a.get('/status', headers=headers).status_code == 200
        assert b.get('/status', headers={**headers, 'X-Real-IP': f'198.51.{prefix}.2'}).status_code == 200
        assert a.get('/status', headers={**headers, 'X-Real-IP': f'198.51.{prefix}.3'}).status_code == 429
        # Changing the fingerprint cannot bypass a spent IP budget.
        ip = f'203.0.{prefix}.10'
        assert a.get('/status', headers={'X-Real-IP': ip}).status_code == 200
        assert b.get('/status', headers={'X-Real-IP': ip, 'X-Device-Fingerprint': 'fresh-device'}).status_code == 200
        assert a.get('/status', headers={'X-Real-IP': ip, 'X-Device-Fingerprint': 'another-device'}).status_code == 429


def test_atomic_concurrent_limit(monkeypatch, redis_url):
    monkeypatch.setattr(settings, 'RATE_LIMIT_ENABLED', True)
    monkeypatch.setattr(settings, 'REDIS_URL', redis_url)
    scope = 'concurrency:' + uuid.uuid4().hex
    def attempt(_):
        try: consume_sync([scope], 10, 60); return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False
    with ThreadPoolExecutor(16) as pool:
        assert sum(pool.map(attempt, range(40))) == 10


def test_outage_fails_closed_and_untrusted_proxy_cannot_change_ip(monkeypatch, redis_url):
    app = limited_app(monkeypatch, redis_url)
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_CIDRS', [])
    unique_ip = '10.10.' + str(uuid.uuid4().int % 250) + '.5'
    with TestClient(app, client=(unique_ip, 1)) as client:
        assert client.get('/status', headers={'X-Real-IP': '1.1.1.1'}).status_code == 200
        assert client.get('/status', headers={'X-Real-IP': '2.2.2.2'}).status_code == 200
        assert client.get('/status', headers={'X-Real-IP': '3.3.3.3'}).status_code == 429
        monkeypatch.setattr(settings, 'REDIS_URL', '')
        assert client.get('/status').status_code == 503
