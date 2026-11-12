"""Atomic Redis sliding-window limits, applied synchronously before API work."""
import hashlib
import hmac
import re
import secrets
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from backend.app.core.config import settings
from backend.app.services.geoip import get_client_ip

# One atomic operation checks ALL buckets before consuming any allowance.
# Redis TIME prevents API-worker clock skew from changing the window.
WINDOW_SCRIPT = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local retry = 0
for _, key in ipairs(KEYS) do
  redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
  if redis.call('ZCARD', key) >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    retry = math.max(retry, tonumber(oldest[2]) + window - now)
  end
end
if retry > 0 then return {0, math.max(1, math.ceil(retry / 1000)), 0} end
local remaining = limit
for _, key in ipairs(KEYS) do
  redis.call('ZADD', key, now, ARGV[3])
  redis.call('PEXPIRE', key, window)
  remaining = math.min(remaining, limit - redis.call('ZCARD', key))
end
return {1, 0, remaining}
"""


def rate_key(scope):
    return 'promptally:rate:' + hashlib.sha256(scope.encode()).hexdigest()


def consume_sync(scopes, limit, seconds):
    if not settings.RATE_LIMIT_ENABLED:
        return
    if not settings.REDIS_URL:
        raise HTTPException(503, 'Request protection is temporarily unavailable')
    try:
        with Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1) as client:
            result = client.eval(WINDOW_SCRIPT, len(scopes), *[rate_key(s) for s in scopes],
                                 int(seconds * 1000), limit, secrets.token_hex(16))
    except Exception:
        raise HTTPException(503, 'Request protection is temporarily unavailable') from None
    if not result[0]:
        raise HTTPException(429, 'Too many requests. Please try again later.',
                            headers={'Retry-After': str(result[1])})


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests=10, window_seconds=60, max_read_requests=60):
        super().__init__(app)
        self.max_requests, self.window_seconds = max_requests, window_seconds
        self.max_read_requests = max_read_requests

    async def dispatch(self, request, call_next):
        path = request.url.path
        # Signed payment callbacks have their own authentication/idempotency policy.
        if (not settings.RATE_LIMIT_ENABLED or request.method == 'OPTIONS'
                or path.startswith(('/uploads/', '/api/v1/webhooks/'))
                or path == '/api/v1/health'):
            return await call_next(request)
        # Server-side page renders authenticate with a shared secret, never a User-Agent.
        token = settings.INTERNAL_RENDER_TOKEN
        if (token and request.method in ('GET', 'HEAD') and hmac.compare_digest(
                request.headers.get('X-Internal-Render', '').encode(), token.encode())):
            return await call_next(request)
        # OAuth callbacks mutate seller connections despite using GET. The read-only MCP
        # endpoint is a POST by protocol, so it uses the read budget.
        is_read = ((request.method in ('GET', 'HEAD') and not path.endswith('/oauth/callback'))
                   or path == '/api/v1/mcp')
        traffic_class = 'read' if is_read else 'sensitive'
        limit = self.max_read_requests if is_read else self.max_requests
        scopes = [f'api:{traffic_class}:ip:' + get_client_ip(request)]
        fingerprint = request.headers.get('X-Device-Fingerprint', '')
        if fingerprint:
            if not re.fullmatch(r'[A-Za-z0-9_.:-]{6,128}', fingerprint):
                return JSONResponse({'detail': 'Invalid device fingerprint'}, status_code=400)
            scopes.append(f'api:{traffic_class}:device:' + fingerprint)
        if not settings.REDIS_URL:
            return JSONResponse({'detail': 'Request protection is temporarily unavailable'}, status_code=503)
        try:
            async with AsyncRedis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1) as client:
                result = await client.eval(WINDOW_SCRIPT, len(scopes), *[rate_key(s) for s in scopes],
                    int(self.window_seconds * 1000), limit, secrets.token_hex(16))
        except Exception:
            return JSONResponse({'detail': 'Request protection is temporarily unavailable'}, status_code=503)
        headers = {'X-RateLimit-Limit': str(limit), 'X-RateLimit-Remaining': str(result[2])}
        if not result[0]:
            headers['Retry-After'] = str(result[1])
            return JSONResponse({'detail': 'Rate limit exceeded. Please try again later.',
                                 'retry_after_seconds': result[1]}, status_code=429, headers=headers)
        response = await call_next(request)
        response.headers.update(headers)
        return response
