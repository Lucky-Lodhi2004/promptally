"""Provider onboarding helpers. Secrets never leave server-side storage."""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session, object_session
from sqlalchemy.orm.attributes import set_committed_value
from backend.app.core.config import settings
from backend.app.models.marketplace import SellerGatewayConfig
from backend.app.services.crypto import encrypt_secret, decrypt_secret, cipher
from backend.app.services.membership import utc


def oauth_ready():
    return bool(settings.RAZORPAY_PARTNER_CLIENT_ID and settings.RAZORPAY_PARTNER_CLIENT_SECRET
                and settings.RAZORPAY_PARTNER_WEBHOOK_SECRET
                and settings.RAZORPAY_PARTNER_ENVIRONMENT in {"test", "live"})


def oauth_redirect_uri():
    return settings.RAZORPAY_PARTNER_REDIRECT_URI or (
        settings.SITE_URL.rstrip('/') + settings.API_V1_STR + '/sellers/razorpay/oauth/callback')


def exchange_token(payload):
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.post('https://auth.razorpay.com/token', json={
                'client_id': settings.RAZORPAY_PARTNER_CLIENT_ID,
                'client_secret': settings.RAZORPAY_PARTNER_CLIENT_SECRET, **payload})
            response.raise_for_status()
            result = response.json()
        if (not all(isinstance(result.get(k), str) and result[k] for k in
                    ('access_token', 'refresh_token', 'public_token'))
                or not 60 < int(result.get('expires_in', 0)) <= 366 * 86400):
            raise ValueError()
        return result
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(502, 'Razorpay authorization failed. Please connect again.') from None


def save_tokens(config, tokens):
    config.razorpay_access_token_enc = encrypt_secret(tokens['access_token'])
    config.razorpay_refresh_token_enc = encrypt_secret(tokens['refresh_token'])
    config.razorpay_key_id = tokens['public_token']
    config.razorpay_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens['expires_in']))


def oauth_access_token(config):
    if config.razorpay_revoked_at:
        raise HTTPException(409, 'Seller must reconnect Razorpay')
    if not oauth_ready() or config.razorpay_oauth_environment != settings.RAZORPAY_PARTNER_ENVIRONMENT:
        raise HTTPException(503, 'Seller Razorpay OAuth configuration is unavailable')
    now = datetime.now(timezone.utc)
    if config.razorpay_token_expires_at and utc(config.razorpay_token_expires_at) > now + timedelta(minutes=2):
        return decrypt_secret(config.razorpay_access_token_enc)
    # Persist rotating refresh tokens independently of a checkout/webhook's
    # transaction. A later failed payment request must not roll back rotation.
    bind = object_session(config).get_bind()
    with Session(bind=bind, expire_on_commit=False) as token_db:
        locked = token_db.query(SellerGatewayConfig).filter_by(seller_id=config.seller_id).with_for_update().one()
        if locked.razorpay_revoked_at:
            raise HTTPException(409, 'Seller must reconnect Razorpay')
        if not locked.razorpay_token_expires_at or utc(locked.razorpay_token_expires_at) <= now + timedelta(minutes=2):
            tokens = exchange_token({'grant_type': 'refresh_token',
                                     'refresh_token': decrypt_secret(locked.razorpay_refresh_token_enc)})
            save_tokens(locked, tokens)
            token_db.commit()
        token = decrypt_secret(locked.razorpay_access_token_enc)
        for name in ('razorpay_access_token_enc', 'razorpay_refresh_token_enc',
                     'razorpay_key_id', 'razorpay_token_expires_at'):
            set_committed_value(config, name, getattr(locked, name))
        return token


def setup_dodo_webhook(config, api_key, environment, request):
    """Reuse an existing matching endpoint; deterministic creation survives retries."""
    cipher()  # Fail before creating any remote resource if encryption is missing.
    site = urlsplit(settings.SITE_URL)
    if site.scheme != 'https' or not site.hostname or site.username or site.password or site.query or site.fragment:
        raise HTTPException(503, 'Configure SITE_URL as the public HTTPS website URL')
    if (api_key.startswith('dodo_test_') and environment != 'test'
            or api_key.startswith('dodo_live_') and environment != 'live'):
        raise HTTPException(400, 'Dodo API key does not match the selected environment')
    url = f"{settings.SITE_URL.rstrip('/')}{settings.API_V1_STR}/webhooks/dodo/{config.seller_id}"
    def call(method, path, payload=None):
        return request(method, 'dodo', path, key=api_key, environment=environment, payload=payload)

    endpoint = None
    iterator = None
    for _ in range(100):
        query = urlencode({'limit': 100, **({'iterator': iterator} if iterator else {})})
        page = call('GET', '/webhooks?' + query)
        if not isinstance(page.get('data'), list):
            raise HTTPException(502, 'Dodo returned invalid webhook configuration')
        matches = [item for item in page['data'] if item.get('url') == url
                   or (config.dodo_webhook_id and item.get('id') == config.dodo_webhook_id)]
        if matches:
            endpoint = next((item for item in matches if item.get('id') == config.dodo_webhook_id), matches[0])
            break
        if page.get('done') is True:
            break
        cursor = page.get('iterator')
        if not cursor or cursor == iterator:
            raise HTTPException(502, 'Could not finish checking Dodo webhooks. Please reconnect.')
        iterator = cursor
    else:
        raise HTTPException(502, 'Too many Dodo endpoints to configure automatically')
    if endpoint is None:
        fingerprint = hashlib.sha256(f'{config.seller_id}:{environment}:{api_key}:{url}'.encode()).hexdigest()
        endpoint = call('POST', '/webhooks', {
            'url': url, 'description': 'Promptally seller payments', 'disabled': True,
            'filter_types': ['payment.succeeded'], 'idempotency_key': fingerprint})
    webhook_id = endpoint.get('id')
    if not isinstance(webhook_id, str) or not webhook_id or '/' in webhook_id:
        raise HTTPException(502, 'Dodo did not return a webhook identifier')
    secret = call('GET', f'/webhooks/{webhook_id}/secret').get('secret')
    try:
        if not isinstance(secret, str) or not base64.b64decode(secret.removeprefix('whsec_'), validate=True):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(502, 'Dodo did not return a valid signing secret') from None
    encrypted_secret = encrypt_secret(secret)
    call('PATCH', f'/webhooks/{webhook_id}', {'url': url, 'disabled': False,
        'filter_types': sorted(set(endpoint.get('filter_types') or []) | {'payment.succeeded'})})
    config.dodo_webhook_id = webhook_id
    config.dodo_webhook_url = url
    config.dodo_webhook_secret_enc = encrypted_secret
