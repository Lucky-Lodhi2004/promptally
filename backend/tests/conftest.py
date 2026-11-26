"""All tests use a fresh isolated DB; never the developer's configured database."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.session import Base, get_db
from backend.app.core.config import settings
from backend.app.models import User, Section, Category, Asset, Subscription
from backend.app.models.enums import UserTier, SubscriptionStatus, SubscriptionGateway
from datetime import datetime, timedelta, timezone


@pytest.fixture(autouse=True)
def disable_posthog_in_tests(monkeypatch):
    """Never transmit analytics events during automated tests."""
    monkeypatch.setattr(settings, 'POSTHOG_API_KEY', '')
    from backend.app.services.analytics import shutdown_analytics
    shutdown_analytics()


@pytest.fixture
def mcp_access(client, users, db):
    from backend.tests.test_mcp_oauth import authorization_code, exchange
    cid, code, _ = authorization_code(client, users, db)
    response = exchange(client, cid, code)
    assert response.status_code == 200, response.text
    access = response.json()['access_token']
    client.headers['Authorization'] = 'Bearer ' + access
    return access


@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'RATE_LIMIT_ENABLED', False)
    monkeypatch.setattr(settings, 'REDIS_URL', '')
    monkeypatch.setattr(settings, 'SITE_URL', 'https://testserver')
    from backend.app.services import email_verification
    monkeypatch.setattr(email_verification, 'kick_delivery', lambda *a: None)
    from backend.app.api.v1.endpoints import auth
    monkeypatch.setattr(auth, 'kick_delivery', lambda *a: None)
    monkeypatch.setattr(settings, 'CREDENTIALS_ENCRYPTION_KEY', Fernet.generate_key().decode())
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_CIDRS', ['127.0.0.1/32'])
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_TOKEN', 'test-ingress-secret')
    monkeypatch.setattr(settings, 'USD_TO_INR_RATE', '85.25')
    monkeypatch.setattr(settings, 'RAZORPAY_KEY_ID', 'platform-key')
    monkeypatch.setattr(settings, 'RAZORPAY_KEY_SECRET', 'platform-secret')
    monkeypatch.setattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'platform-hook')
    monkeypatch.setattr(settings, 'RAZORPAY_PLAN_ID', '')
    monkeypatch.setattr(settings, 'DODO_PRODUCT_ID', 'platform-product')
    monkeypatch.setattr(settings, 'DODO_API_KEY', 'platform-dodo-key')
    monkeypatch.setattr(settings, 'RAZORPAY_PARTNER_CLIENT_ID', '')
    monkeypatch.setattr(settings, 'RAZORPAY_PARTNER_CLIENT_SECRET', '')
    monkeypatch.setattr(settings, 'RAZORPAY_PARTNER_WEBHOOK_SECRET', '')
    monkeypatch.setattr(settings, 'RAZORPAY_PARTNER_REDIRECT_URI', '')
    monkeypatch.setattr(settings, 'RAZORPAY_PARTNER_ENVIRONMENT', 'test')
    import base64
    monkeypatch.setattr(settings, 'DODO_WEBHOOK_SECRET', 'whsec_' + base64.b64encode(b'platform-dodo-hook').decode())
    from backend.app.services import storage
    for name in ('MEDIA_DIR', 'ARCHIVES_DIR', 'COLLECTIONS_DIR', 'AVATARS_DIR'):
        directory = tmp_path / name
        directory.mkdir()
        monkeypatch.setattr(storage, name, directory)
    from backend.app.services import indexnow
    async def no_index(*args): return True
    # Prevent an actual indexing call from background tasks during upload tests.
    from backend.app.api.v1.endpoints import assets_actions, admin
    monkeypatch.setattr(assets_actions, 'submit_urls_to_indexnow', no_index)
    monkeypatch.setattr(admin, 'submit_urls_to_indexnow', no_index)
    def isolated_db():
        try:
            yield db
        finally:
            db.rollback()
            db.expire_all()
    app.dependency_overrides[get_db] = isolated_db
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == 'RateLimitMiddleware':
            middleware.kwargs['max_requests'] = 100000
    app.middleware_stack = None
    with TestClient(app, base_url='https://testserver', client=('127.0.0.1', 12345), headers={'X-Proxy-Token': 'test-ingress-secret'}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def users(db):
    from backend.app.core.security import get_password_hash
    seller = User(id='seller', email='seller@example.com', username='seller', name='Seller',
                  email_verification_required=False, tier=UserTier.PRO, password_hash=get_password_hash('password123'))
    buyer = User(id='buyer', email='buyer@example.com', username='buyer', name='Buyer', tier=UserTier.FREE, email_verification_required=False)
    db.add_all([seller, buyer]); db.flush()
    db.add(Subscription(user_id=seller.id, gateway=SubscriptionGateway.RAZORPAY,
        gateway_subscription_id='sub_existing', status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=25)))
    db.commit()
    return seller, buyer


@pytest.fixture
def asset(db, users):
    section = Section(id='section', slug='prompts', name='Prompts')
    category = Category(id='category', section_id='section', slug='system-base-contexts', name='System')
    asset = Asset(id='asset', slug='paid-prompt', seo_title='Paid prompt', short_description='Public teaser',
        section_id='section', category_id='category', asset_type='PROMPT', raw_content='SECRET PAYLOAD',
        file_name='prompt.md', file_extension='.md', author_id=users[0].id,
        is_paid=True, price_cents=500, price_inr_paise=42625)
    db.add_all([section, category, asset]); db.commit()
    return asset


@pytest.fixture
def provider(monkeypatch):
    from backend.app.services import payments
    from backend.app.api.v1.endpoints import marketplace
    calls, responses, orders = [], {}, {}
    def fake(method, gateway, path, **kwargs):
        calls.append((method, gateway, path, kwargs))
        if (method, gateway, path) in responses:
            return responses[(method, gateway, path)]
        if path.startswith('/orders?') or path.startswith('/products?'): return {'items': []}
        if path == '/plans':
            return {'id': 'plan_1', **kwargs['payload']}
        if path == '/subscriptions': return {'id': 'sub_1', 'short_url': 'https://rzp.io/checkout'}
        if path == '/products/platform-product':
            return {'price': {'type':'recurring_price', 'price':100, 'currency':'USD',
                'payment_frequency_count':1, 'payment_frequency_interval':'Month', 'tax_inclusive': True}}
        if path == '/checkouts': return {'session_id': 'checkout_1', 'checkout_url': 'https://checkout.dodopayments.com/session'}
        if path == '/products': return {'product_id': 'seller-product'}
        if path == '/orders':
            order = {'id': 'order_1', 'amount':kwargs['payload']['amount'], 'currency':'INR'}
            orders['order_1'] = {**order, 'status': 'paid', 'amount_paid': order['amount']}
            return order
        if path.startswith('/orders/') and path.split('/')[-1] in orders:
            return orders[path.split('/')[-1]]
        raise AssertionError(f'Unexpected provider call: {method} {gateway} {path}')
    monkeypatch.setattr(payments, 'gateway_request', fake)
    monkeypatch.setattr(marketplace, 'gateway_request', fake)
    return calls, responses


@pytest.fixture(scope='session')
def redis_url(tmp_path_factory):
    """Private Redis for rate-limit tests; never flush the application's Redis."""
    import socket, subprocess, time
    from redis import Redis
    directory = tmp_path_factory.mktemp('redis')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    proc = subprocess.Popen(['redis-server', '--bind', '127.0.0.1', '--port', str(port),
        '--save', '', '--appendonly', 'no', '--dir', str(directory)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'redis://127.0.0.1:{port}/0'
    client = Redis.from_url(url)
    try:
        for _ in range(100):
            try:
                if client.ping(): break
            except Exception: time.sleep(.02)
        else: raise RuntimeError('Test Redis failed to start')
        yield url
    finally:
        client.close(); proc.terminate(); proc.wait(timeout=5)


@pytest.fixture
def google_signin(client, monkeypatch, redis_url):
    """Fake Google identity provider; real browser binding and private Redis nonce."""
    import time, uuid
    from types import SimpleNamespace
    from backend.app.api.v1.endpoints import auth
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_ID', 'test-client')
    monkeypatch.setattr(settings, 'REDIS_URL', redis_url)
    monkeypatch.setattr(auth, 'HAS_GOOGLE_AUTH', True)
    monkeypatch.setattr(auth, 'google_certificate_request', lambda: None)
    credentials = {}
    def verify(credential, *args):
        if credential not in credentials: raise ValueError('Invalid credential')
        return dict(credentials[credential])
    monkeypatch.setattr(auth, 'id_token', SimpleNamespace(verify_oauth2_token=verify))
    def start(info, device='google-device', headers=None):
        headers = headers or {}
        result = client.post('/api/v1/auth/google/start', json={'device_fingerprint': device}, headers=headers)
        assert result.status_code == 200, result.text
        challenge = result.json()
        credential = str(uuid.uuid4())
        credentials[credential] = {'iss': 'https://accounts.google.com', 'aud': 'test-client',
            'exp': time.time() + 3600, 'nonce': challenge['nonce'], **info}
        return {'credential': credential, 'csrf_token': challenge['csrf_token'], 'device_fingerprint': device}
    def login(info, device='google-device', headers=None):
        return client.post('/api/v1/auth/google', json=start(info, device, headers), headers=headers or {})
    return SimpleNamespace(start=start, login=login, credentials=credentials)
