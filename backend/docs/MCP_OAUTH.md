# MCP access through Google sign-in

All calls to `POST /api/v1/mcp`, including initialization, notifications, batches
and the legacy JSON shape, require a Promptally MCP bearer token. Discovery stays
public. Website cookies, website JWTs and Google ID tokens cannot authenticate
the MCP transport. The three existing tools remain read-only; signing in does
not unlock paid payloads or add publishing/account tools.

## Connection flow

1. The client discovers `/.well-known/oauth-protected-resource` from the MCP
   endpoint's HTTP 401 `WWW-Authenticate` header. The resource-specific discovery
   URL `/.well-known/oauth-protected-resource/api/v1/mcp` is also available.
2. `/.well-known/oauth-authorization-server` advertises authorization, token,
   registration, revocation, scope and S256 PKCE support.
3. A public client registers exact callback URLs at `POST /api/v1/oauth/register`.
   Dynamic registration is supported; Client ID Metadata Documents and confidential
   clients are not supported. Registration does not fetch any supplied URL.
4. The client opens `GET /api/v1/oauth/authorize` with `client_id`, `redirect_uri`,
   `response_type=code`, `code_challenge`, `code_challenge_method=S256`, `state`,
   `scope=mcp:read`, and `resource=https://YOUR_DOMAIN/api/v1/mcp`.
5. The browser lands on `/mcp/authorize`. Google's existing Identity Services
   button signs the user into their existing Promptally account. The user sees
   the client-provided name, exact callback URL, and requested read access, then
   explicitly allows or cancels. Existing Google account-linking and email
   verification rules remain in force. The server binds consent to that browser.
6. Allow returns an authorization code to the registered callback with the
   client's original state. Cancel returns `error=access_denied` and state.
7. The client exchanges the code using URL-encoded `grant_type=authorization_code`,
   `client_id`, `code`, `redirect_uri`, `code_verifier`, and the same `resource`
   at `POST /api/v1/oauth/token`.
8. The client sends `Authorization: Bearer <access_token>` on each MCP call.

Google authenticates the human; Promptally issues the MCP credentials. This uses
the existing GIS popup, not a new Google redirect callback or Google API scopes.
An MCP client cannot use a Google access token as a Promptally access token.

## Deploy

Back up the application database, then apply the additive migration:

```bash
backend/venv/bin/alembic -c backend/alembic.ini upgrade head
```

Revision `e25f64d85006` follows `d14e53c74005` and creates four MCP OAuth tables.
It does not modify accounts, purchases, subscriptions or existing website sessions.
Do not deploy the new backend until the migration is applied. Anonymous MCP
clients must reconnect through OAuth after deployment.

Configure the existing backend settings:

```ini
SITE_URL=https://YOUR_DOMAIN
GOOGLE_CLIENT_ID=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com
REDIS_URL=redis://YOUR_REDIS_HOST:6379/0
```

Set frontend `NEXT_PUBLIC_SITE_URL` to the same public origin and configure
`API_INTERNAL_URL` as for the existing website. Use HTTPS in production.
`GOOGLE_CLIENT_SECRET` is not needed for this GIS flow. Add the actual frontend
origin to the Google application's Authorized JavaScript origins, and configure
its audience/test users as appropriate. See [Google setup](GOOGLE_SIGN_IN.md).
New non-Gmail/non-Workspace users may need email verification before consent.
Redis must be available for the existing Google nonce/CSRF and rate-limit checks.

Rebuild the Next.js frontend and restart both services. Next proxies OAuth APIs
under `/api/v1` and the public well-known discovery routes to FastAPI. Serve
`/mcp/authorize` through Next, not directly from FastAPI. Configure log redaction
for authorization codes, request handles and bearer credentials at your ingress.

Clients supporting HTTP MCP and OAuth dynamic registration need only the server
URL. For example, VS Code `.vscode/mcp.json`:

```json
{
  "servers": {
    "promptally": {
      "type": "http",
      "url": "https://YOUR_DOMAIN/api/v1/mcp"
    }
  }
}
```

Client support varies; a client without dynamic registration can use a public
client ID obtained from the registration endpoint. Loopback callbacks may use
HTTP on `localhost`, `127.0.0.1` or `[::1]`; other callbacks require HTTPS. All
callbacks must match registration exactly, including the port. Register the
actual callback selected by the client. Custom URI schemes are not supported.
Browser-based MCP clients must also have their exact origins approved in
`BACKEND_CORS_ORIGINS`; arbitrary cross-origin browser calls remain rejected.

## Token lifecycle

- Authorization requests expire in 10 minutes; codes expire in 60 seconds and
  can be redeemed once. S256 PKCE, client, callback and resource bindings are
  checked before consumption. Consent is explicit for every new authorization.
- MCP tokens are random opaque values. Only SHA-256 digests are stored.
- Access lasts at most one hour. Grants last 30 days. Refresh with URL-encoded
  `grant_type=refresh_token`, `client_id`, `refresh_token` and `resource` at the
  token endpoint. Each refresh replaces its refresh token. Reusing a consumed
  refresh token revokes the whole grant; reconnect to recover. Clients should
  serialize refreshes and retain each newly returned refresh token.
- To disconnect, POST URL-encoded `client_id` and `token` to `/api/v1/oauth/revoke`.
  Either a valid access or refresh token revokes the associated grant. Unknown
  tokens return success without revealing account information.
- Website logout/password-session revocation increments the existing user
  `token_version`, invalidating MCP access and refresh tokens too. Account deletion
  and email-verification restrictions are checked on every authenticated call.
- This change does not add personal access tokens. A config-file connection uses
  OAuth and stores tokens through its MCP client, not the website's session token.
- Expired authorization/client/token rows are not automatically purged. Retain
  consumed refresh records through the grant's lifetime for replay detection;
  plan database retention/cleanup for expired grants and abandoned requests.

## Verify

Tests use an isolated database and do not charge cards or contact Google:

```bash
ENVIRONMENT=development DATABASE_URL=sqlite:// REDIS_URL= \
  backend/venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test
ENVIRONMENT=development DATABASE_URL=sqlite:// REDIS_URL= \
  backend/venv/bin/python backend/scripts/verify_mcp_oauth.py
backend/venv/bin/python frontend/scripts/verify-integration.py
cd frontend && npx tsc --noEmit
```

The PostgreSQL check starts/stops a disposable local cluster to verify migrations
and concurrent exchanges. The full-stack check builds a temporary frontend and
tests the consent page, OAuth discovery and exchanges through Next's API proxy.
It uses a test account with a mock Google subject, not a live Google login.

Before release, connect an actual MCP client on the public HTTPS origin, complete
Google sign-in and consent, search/read a free resource, cancel a second consent,
and disconnect/reconnect. Test with the actual Google project and client callback
URLs. Automated tests do not authenticate a real Google account.

References:
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- https://code.visualstudio.com/docs/agents/reference/mcp-configuration
