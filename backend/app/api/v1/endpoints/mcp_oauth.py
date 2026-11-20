"""Public-client OAuth authorization code + S256 PKCE for the MCP resource.

Google authenticates the browser through the existing GIS sign-in. This service
issues only opaque Promptally MCP tokens; neither Google tokens nor website JWTs
are accepted by the MCP transport. No client-provided URLs are fetched.
"""
import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.app.core.config import settings
from backend.app.core.security import get_optional_current_user
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.mcp_oauth import MCPClient, MCPAuthorization, MCPGrant, MCPToken
from backend.app.services.membership import utc

router = APIRouter()
SCOPE = 'mcp:read'
COOKIE = 'promptally_mcp_browser'
COOKIE_PATH = '/api/v1/oauth'
ACCESS_SECONDS = 3600
GRANT_DAYS = 30


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def origin():
    return settings.SITE_URL.rstrip('/')


def resource_url():
    return origin() + settings.API_V1_STR + '/mcp'


def endpoint(part):
    return origin() + settings.API_V1_STR + '/oauth/' + part


def oauth_error(error, description, status=400):
    # OAuth errors are top-level, not FastAPI's usual {detail: ...} envelope.
    return JSONResponse({'error': error, 'error_description': description}, status_code=status,
                        headers={'Cache-Control': 'no-store', 'Pragma': 'no-cache'})


def protected_resource_metadata():
    return {'resource': resource_url(), 'authorization_servers': [origin()],
            'scopes_supported': [SCOPE], 'bearer_methods_supported': ['header'],
            'resource_name': 'Promptally MCP'}


def authorization_server_metadata():
    return {'issuer': origin(), 'authorization_endpoint': endpoint('authorize'),
            'token_endpoint': endpoint('token'), 'registration_endpoint': endpoint('register'),
            'revocation_endpoint': endpoint('revoke'), 'scopes_supported': [SCOPE],
            'response_types_supported': ['code'],
            'grant_types_supported': ['authorization_code', 'refresh_token'],
            'token_endpoint_auth_methods_supported': ['none'],
            'revocation_endpoint_auth_methods_supported': ['none'],
            'code_challenge_methods_supported': ['S256'],
            'client_id_metadata_document_supported': False}


def valid_redirect(value):
    try:
        parts = urlsplit(value)
        _ = parts.port
        return (len(value) <= 2048 and not any(c.isspace() or ord(c) < 32 for c in value)
                and not parts.fragment and not parts.username and not parts.password
                and bool(parts.hostname) and parts.path.startswith('/')
                and (parts.scheme == 'https' or (parts.scheme == 'http'
                     and parts.hostname in {'127.0.0.1', '::1', 'localhost'})))
    except ValueError:
        return False


class ClientRegistration(BaseModel):
    model_config = ConfigDict(extra='ignore')
    client_name: str = Field(default='MCP client', min_length=1, max_length=120)
    redirect_uris: list[str] = Field(min_length=1, max_length=10)
    token_endpoint_auth_method: str = 'none'
    grant_types: list[str] = Field(default_factory=lambda: ['authorization_code', 'refresh_token'])
    response_types: list[str] = Field(default_factory=lambda: ['code'])


@router.post('/oauth/register', status_code=201)
def register(req: ClientRegistration, response: Response, db: Session = Depends(get_db)):
    if not all(valid_redirect(uri) for uri in req.redirect_uris):
        return oauth_error('invalid_redirect_uri', 'Use an HTTPS callback or an HTTP loopback callback.')
    if (req.token_endpoint_auth_method != 'none' or req.response_types != ['code']
            or 'authorization_code' not in req.grant_types
            or set(req.grant_types) - {'authorization_code', 'refresh_token'}):
        return oauth_error('invalid_client_metadata', 'Only public clients with authorization code and PKCE are supported.')
    client = MCPClient(id=secrets.token_urlsafe(32), name=req.client_name,
                       redirect_uris=list(dict.fromkeys(req.redirect_uris)), created_at=now())
    db.add(client)
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'client_id': client.id, 'client_id_issued_at': int(utc(client.created_at).timestamp()),
            'client_name': client.name, 'redirect_uris': client.redirect_uris,
            'token_endpoint_auth_method': 'none', 'grant_types': req.grant_types,
            'response_types': ['code']}


@router.get('/oauth/authorize')
def authorize(request: Request, db: Session = Depends(get_db)):
    params = request.query_params
    if any(len(params.getlist(k)) != 1 for k in params):
        return oauth_error('invalid_request', 'Duplicate authorization parameters.')
    client = db.get(MCPClient, params.get('client_id', ''))
    redirect = params.get('redirect_uri', '')
    # Never redirect errors to an unvalidated callback.
    if not client or redirect not in client.redirect_uris:
        return oauth_error('invalid_request', 'Unknown client or unregistered redirect URI.')
    if params.get('response_type') != 'code':
        return oauth_error('unsupported_response_type', 'Use response_type=code.')
    challenge = params.get('code_challenge', '')
    if params.get('code_challenge_method') != 'S256' or not re.fullmatch(r'[A-Za-z0-9_-]{43}', challenge):
        return oauth_error('invalid_request', 'S256 PKCE is required.')
    if params.get('resource') != resource_url():
        return oauth_error('invalid_target', 'The resource must identify the Promptally MCP endpoint.')
    scope = params.get('scope', SCOPE)
    if scope != SCOPE:
        return oauth_error('invalid_scope', 'Only mcp:read is supported.')
    state = params.get('state')
    if state is not None and len(state) > 2048:
        return oauth_error('invalid_request', 'State is too long.')
    browser = request.cookies.get(COOKIE, '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', browser):
        browser = secrets.token_urlsafe(32)
    handle = secrets.token_urlsafe(32)
    db.add(MCPAuthorization(id=digest(handle), client_id=client.id, browser_hash=digest(browser),
        redirect_uri=redirect, state=state, challenge=challenge, resource=resource_url(),
        scope=scope, expires_at=now() + timedelta(minutes=10)))
    db.commit()
    response = RedirectResponse(origin() + '/mcp/authorize?' + urlencode({'request': handle}), status_code=303)
    response.set_cookie(COOKIE, browser, max_age=3600, httponly=True, secure=settings.secure_cookies,
                        samesite='lax', path=COOKIE_PATH)
    response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
    return response


def browser_authorization(db, request, handle):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', handle):
        raise HTTPException(400, 'Invalid authorization request')
    row = db.get(MCPAuthorization, digest(handle))
    browser = request.cookies.get(COOKIE, '')
    if (not row or row.decided_at or utc(row.expires_at) <= now()
            or not hmac.compare_digest(row.browser_hash, digest(browser))):
        raise HTTPException(400, 'Authorization request expired or belongs to another browser. Reconnect your client.')
    return row


@router.get('/oauth/requests/{handle}')
def consent_details(handle: str, request: Request, response: Response, db: Session = Depends(get_db)):
    row = browser_authorization(db, request, handle)
    client = db.get(MCPClient, row.client_id)
    response.headers['Cache-Control'] = 'no-store'
    return {'client_name': client.name, 'redirect_uri': row.redirect_uri, 'scope': row.scope,
            'resource': row.resource}


class Consent(BaseModel):
    approved: bool


@router.post('/oauth/requests/{handle}')
def consent(handle: str, req: Consent, request: Request, response: Response,
            db: Session = Depends(get_db), user: User = Depends(get_optional_current_user)):
    # Origin protection in HttpSecurityMiddleware plus browser-bound request handle
    # prevents login/consent CSRF. Google identity is linked by existing auth code.
    if req.approved and (not user or not user.google_sub):
        raise HTTPException(403, 'Continue with Google before authorizing this connection.')
    if req.approved and user.email_verification_required and not user.email_verified_at:
        raise HTTPException(403, 'Verify your email address before authorizing this connection.')
    row = browser_authorization(db, request, handle)
    code = secrets.token_urlsafe(32)
    changed = db.query(MCPAuthorization).filter_by(id=row.id, decided_at=None).update({
        'decided_at': now(), 'user_id': user.id if user else None, 'token_version': user.token_version if user else None,
        'code_hash': digest(code) if req.approved else None,
        'code_expires_at': now() + timedelta(seconds=60) if req.approved else None}, synchronize_session=False)
    if changed != 1:
        db.rollback()
        raise HTTPException(400, 'Authorization request has already been used.')
    db.commit()
    parts = urlsplit(row.redirect_uri)
    values = parse_qsl(parts.query, keep_blank_values=True)
    values.append(('code', code) if req.approved else ('error', 'access_denied'))
    if row.state is not None:
        values.append(('state', row.state))
    response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
    return {'redirect_url': urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(values), ''))}


def valid_grant(db, grant):
    if not grant or grant.revoked_at or utc(grant.expires_at) <= now() or grant.resource != resource_url():
        return None
    user = db.get(User, grant.user_id)
    if (not user or user.token_version != grant.token_version or not user.google_sub
            or (user.email_verification_required and not user.email_verified_at)):
        return None
    return user


def issue_tokens(db, grant):
    access, refresh = 'pmcp_' + secrets.token_urlsafe(32), 'pmcpr_' + secrets.token_urlsafe(32)
    seconds = min(ACCESS_SECONDS, max(1, int((utc(grant.expires_at) - now()).total_seconds())))
    db.add(MCPToken(access_hash=digest(access), refresh_hash=digest(refresh), grant_id=grant.id,
                    access_expires_at=now() + timedelta(seconds=seconds)))
    return {'access_token': access, 'token_type': 'Bearer', 'expires_in': seconds,
            'refresh_token': refresh, 'scope': grant.scope}


async def form_params(request):
    if request.headers.get('content-type', '').split(';')[0].strip() != 'application/x-www-form-urlencoded':
        return None
    if len(await request.body()) > 16384:
        return None
    form = await request.form()
    if any(len(form.getlist(k)) != 1 for k in form):
        return None
    return dict(form)


@router.post('/oauth/token')
async def token(request: Request, db: Session = Depends(get_db)):
    data = await form_params(request)
    if data is None:
        return oauth_error('invalid_request', 'Send URL-encoded parameters without duplicates.')
    # SQLAlchemy is synchronous. Lock contention must never block the ASGI loop
    # that completes other requests and releases their database transactions.
    return await run_in_threadpool(exchange_token, data, request.headers.get('authorization'), db)


def exchange_token(data, authorization, db):
    if authorization or data.get('client_secret'):
        return oauth_error('invalid_client', 'This endpoint accepts registered public clients only.', 401)
    client = db.get(MCPClient, data.get('client_id', ''))
    if not client:
        return oauth_error('invalid_client', 'Unknown client.', 401)
    if data.get('resource') != resource_url():
        return oauth_error('invalid_target', 'Incorrect or missing MCP resource.')
    if data.get('grant_type') == 'authorization_code':
        row = db.query(MCPAuthorization).filter_by(code_hash=digest(data.get('code', ''))).with_for_update().first()
        verifier = data.get('code_verifier', '')
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        if (not row or row.used_at or not row.code_expires_at or utc(row.code_expires_at) <= now()
                or row.client_id != client.id or row.redirect_uri != data.get('redirect_uri')
                or row.resource != data['resource'] or not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', verifier)
                or not hmac.compare_digest(row.challenge, challenge)):
            return oauth_error('invalid_grant', 'Invalid, expired, or already used authorization code.')
        user = db.get(User, row.user_id)
        if (not user or user.token_version != row.token_version or not user.google_sub
                or (user.email_verification_required and not user.email_verified_at)):
            return oauth_error('invalid_grant', 'Sign in and authorize again.')
        changed = db.query(MCPAuthorization).filter_by(id=row.id, used_at=None).update(
            {'used_at': now()}, synchronize_session=False)
        if changed != 1:
            db.rollback()
            return oauth_error('invalid_grant', 'Authorization code already used.')
        grant = MCPGrant(id=secrets.token_urlsafe(32), client_id=client.id, user_id=user.id,
            token_version=user.token_version, resource=row.resource, scope=row.scope,
            expires_at=now() + timedelta(days=GRANT_DAYS))
        db.add(grant)
        db.flush()
    elif data.get('grant_type') == 'refresh_token':
        previous = db.query(MCPToken).filter_by(refresh_hash=digest(data.get('refresh_token', ''))).first()
        grant = (db.query(MCPGrant).filter_by(id=previous.grant_id).with_for_update().first()) if previous else None
        if not valid_grant(db, grant) or grant.client_id != client.id:
            return oauth_error('invalid_grant', 'Invalid or expired refresh token.')
        if data.get('scope', grant.scope) != grant.scope:
            return oauth_error('invalid_scope', 'The scope cannot be changed.')
        changed = db.query(MCPToken).filter_by(access_hash=previous.access_hash, refresh_used_at=None).update(
            {'refresh_used_at': now()}, synchronize_session=False)
        if changed != 1:
            # Reuse of a rotated refresh token revokes its whole token family.
            grant.revoked_at = now()
            db.commit()
            return oauth_error('invalid_grant', 'Refresh token reuse detected. Reconnect your client.')
    else:
        return oauth_error('unsupported_grant_type', 'Use authorization_code or refresh_token.')
    result = issue_tokens(db, grant)
    db.commit()
    return JSONResponse(result, headers={'Cache-Control': 'no-store', 'Pragma': 'no-cache'})


@router.post('/oauth/revoke')
async def revoke(request: Request, db: Session = Depends(get_db)):
    data = await form_params(request)
    if data is None:
        return oauth_error('invalid_request', 'Send URL-encoded parameters.')
    return await run_in_threadpool(revoke_token, data, db)


def revoke_token(data, db):
    hashed = digest(data.get('token', ''))
    record = db.query(MCPToken).filter((MCPToken.access_hash == hashed) | (MCPToken.refresh_hash == hashed)).first()
    if record:
        grant = db.query(MCPGrant).filter_by(id=record.grant_id).with_for_update().first()
        if grant and grant.client_id == data.get('client_id'):
            grant.revoked_at = now()
            db.commit()
    return Response(status_code=200, headers={'Cache-Control': 'no-store'})


def require_mcp_user(request: Request, db: Session = Depends(get_db)):
    # Intentionally never accept website cookies, website JWTs or Google ID tokens.
    header = request.headers.get('authorization', '')
    scheme, _, credential = header.partition(' ')
    record = None
    if scheme.lower() == 'bearer' and re.fullmatch(r'pmcp_[A-Za-z0-9_-]{43}', credential):
        record = db.get(MCPToken, digest(credential))
    grant = db.get(MCPGrant, record.grant_id) if record else None
    user = valid_grant(db, grant)
    if not record or utc(record.access_expires_at) <= now() or not user:
        challenge = f'Bearer resource_metadata="{origin()}/.well-known/oauth-protected-resource", scope="{SCOPE}"'
        if header:
            challenge += ', error="invalid_token"'
        raise HTTPException(401, 'Authorize this MCP connection with Google.',
                            headers={'WWW-Authenticate': challenge, 'Cache-Control': 'no-store'})
    if grant.scope != SCOPE:
        raise HTTPException(403, 'Insufficient scope', headers={
            'WWW-Authenticate': f'Bearer error="insufficient_scope", scope="{SCOPE}"'})
    return user
