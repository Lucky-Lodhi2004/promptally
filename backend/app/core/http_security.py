"""Enforce request bounds before parsing and protect direct API/static responses."""
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException
from backend.app.core.config import settings


class BodyTooLarge(HTTPException):
    def __init__(self):
        super().__init__(413, 'Request body is too large')


class HttpSecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        maximum = settings.MAX_REQUEST_BODY_BYTES
        if scope['path'].startswith('/api/v1/oauth/'):
            maximum = min(maximum, 16384)
        size, started = 0, False

        async def secured_send(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
                values = list(message.get('headers', []))
                if not any(name.lower() == b'referrer-policy' for name, _ in values):
                    values.append((b'referrer-policy', b'strict-origin-when-cross-origin'))
                values.extend([
                    (b'x-content-type-options', b'nosniff'),
                    (b'x-frame-options', b'DENY'),
                    (b'content-security-policy', b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"),
                ])
                if settings.secure_cookies:
                    values.append((b'strict-transport-security', b'max-age=31536000'))
                message = {**message, 'headers': values}
            await send(message)

        async def limited_receive():
            nonlocal size
            message = await receive()
            if message['type'] == 'http.request':
                size += len(message.get('body', b''))
                if size > maximum:
                    raise BodyTooLarge()
            return message

        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'detail': 'Invalid Content-Length'}, status_code=400)(scope, receive, secured_send)
        if length < 0 or length > maximum:
            return await JSONResponse({'detail': 'Request body is too large'}, status_code=413)(scope, receive, secured_send)
        # Cookie authentication also needs CSRF protection, including sibling
        # subdomains (SameSite alone does not isolate the landing page).
        if scope['method'] not in {'GET', 'HEAD', 'OPTIONS'} and not scope['path'].startswith('/api/v1/webhooks/'):
            origin = headers.get(b'origin', b'').decode('latin1')
            allowed = {settings.SITE_URL.rstrip('/'), *settings.BACKEND_CORS_ORIGINS}
            if origin and origin not in allowed:
                return await JSONResponse({'detail': 'Cross-origin request rejected'}, status_code=403)(scope, receive, secured_send)
            if not origin and headers.get(b'sec-fetch-site') in {b'cross-site', b'same-site'}:
                return await JSONResponse({'detail': 'Cross-origin request rejected'}, status_code=403)(scope, receive, secured_send)
        try:
            await self.app(scope, limited_receive, secured_send)
        except BodyTooLarge:
            if not started:
                await JSONResponse({'detail': 'Request body is too large'}, status_code=413)(scope, receive, secured_send)

