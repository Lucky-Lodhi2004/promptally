"""Short-lived browser-bound challenges for Google Identity Services sign-in."""
import hashlib
import hmac
import secrets
from urllib.parse import urlsplit
from fastapi import HTTPException
from redis import Redis
from backend.app.core.config import settings
from backend.app.services.registration import registration_identity

COOKIE = 'promptally_google_csrf'
COOKIE_PATH = '/api/v1/auth/google'
TTL = 300
_CONSUME = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  redis.call('del', KEYS[1])
  return 1
end
return 0
"""


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _redis():
    if not settings.REDIS_URL:
        raise HTTPException(503, 'Google sign-in is temporarily unavailable')
    return Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def check_origin(request):
    # JSON + custom fingerprint header already prevent simple cross-origin forms.
    # Explicit Origin checking additionally rejects cross-origin script login CSRF.
    origin = request.headers.get('origin')
    if origin:
        allowed = set(settings.BACKEND_CORS_ORIGINS)
        site = urlsplit(settings.SITE_URL)
        allowed.add(f'{site.scheme}://{site.netloc}')
        if origin not in allowed:
            raise HTTPException(403, 'Google sign-in must start from Promptally')


def new_challenge(request, response, fingerprint):
    check_origin(request)
    _, fingerprint = registration_identity(request, fingerprint)
    nonce, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    try:
        with _redis() as client:
            client.set('promptally:google:nonce:' + digest(nonce),
                       digest(csrf) + ':' + digest(fingerprint), nx=True, ex=TTL)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Google sign-in is temporarily unavailable') from None
    response.set_cookie(COOKIE, csrf, max_age=TTL, httponly=True, samesite='strict',
                        secure=settings.secure_cookies, path=COOKIE_PATH)
    return {'client_id': settings.GOOGLE_CLIENT_ID, 'nonce': nonce, 'csrf_token': csrf, 'expires_in': TTL}


def check_browser(request, csrf_token, fingerprint):
    check_origin(request)
    cookie = request.cookies.get(COOKIE, '')
    if not csrf_token or not cookie or not hmac.compare_digest(cookie, csrf_token):
        raise HTTPException(403, 'Google sign-in session is invalid. Please try again.')
    _, fingerprint = registration_identity(request, fingerprint)
    return digest(csrf_token) + ':' + digest(fingerprint)


def consume_challenge(nonce, binding):
    if not isinstance(nonce, str) or not 32 <= len(nonce) <= 128:
        raise HTTPException(400, 'Google sign-in session is invalid or expired. Please try again.')
    try:
        with _redis() as client:
            consumed = client.eval(_CONSUME, 1, 'promptally:google:nonce:' + digest(nonce), binding)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Google sign-in is temporarily unavailable') from None
    if not consumed:
        raise HTTPException(400, 'Google sign-in session is invalid or expired. Please try again.')
