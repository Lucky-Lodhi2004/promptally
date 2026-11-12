# Security fixes before deployment

Migration `d14e53c74005` adds session revocation, durable per-account login lockout,
and a removal timestamp. It changes the asset-purchase foreign key to RESTRICT,
preventing database-level hard deletion of a purchased artifact. Take a database
backup, run `alembic -c backend/alembic.ini upgrade head`, and restart API, worker
and beat. Existing JWTs without a version are rejected; users must sign in again.
Password changes revoke all existing tokens and issue a new cookie to the caller.
Logout revokes every session for that account. The browser no longer stores or
reads JWTs in localStorage; old stored tokens are removed on app startup.

## Ingress and AWS origin access

Trusting loopback alone is insufficient when Next and nginx share the same host.
The API now requires BOTH a trusted socket peer CIDR and `X-Proxy-Token` matching
`TRUSTED_PROXY_TOKEN` before considering IP or country forwarding headers. Empty
tokens disable forwarding trust. Next strips all incoming identity, proxy-token
and internal-render headers. It never injects the proxy token itself.

The local nginx uses a private ignored `dev/local-proxy/proxy-auth.conf` containing
`proxy_set_header X-Proxy-Token "<same random credential>";`. Keep its permissions
at 0600. Generate at least 32 random bytes for each deployment and configure the
matching value in backend environment. Do not expose this credential in Next's
public environment, browser JavaScript, logs, or version control.

Production nginx must overwrite `X-Real-IP` with its verified client address,
clear client-supplied `CF-Connecting-IP`, `CF-IPCountry`, `X-Forwarded-For`,
`X-Country-Code`, `X-Dev-Country`, and `X-Internal-Render`, and inject the private
proxy token. Use the local MaxMind country database with the verified client IP.
Only accept Cloudflare country/IP headers after verifying the upstream really is
Cloudflare and restricting origin access accordingly. Never copy the local fixed
US/IN simulation to production.

On EC2, bind Next and Uvicorn to loopback or private Docker networks, keep
`--no-proxy-headers` on Uvicorn, and expose only the HTTPS ingress in the AWS
security group. Do not publish ports 3000, 8000, PostgreSQL or Redis. Loopback
binding and AWS security groups are deployment requirements; application code
cannot enforce a security group on a server that has not been provisioned.

## Rotate the two Razorpay webhook secrets

`check_security_setup.py` reports weak settings without printing them. Production
startup refuses short/default JWT keys, short Razorpay platform/partner webhook
secrets, missing proxy credentials, disabled limits and non-HTTPS site URLs.

For EACH Razorpay endpoint, generate a distinct random value with at least 32
bytes of entropy (for example `secrets.token_urlsafe(48)`). Update the signing
secret in the Razorpay dashboard AND its corresponding backend environment value:

- Platform subscription webhook: `RAZORPAY_WEBHOOK_SECRET`.
- Technology Partner application webhook: `RAZORPAY_PARTNER_WEBHOOK_SECRET`.

Restart API/worker/beat and send signed test events to verify both endpoints.
Coordinate the cutover and monitor delivery retries; older events can retain the
old signing secret. Do not silently change only `.env`, which breaks valid events.
Length checks cannot measure entropy: use a generator rather than a memorable
32-character phrase. Run the read-only check again before production.

## Content, access and request bounds

- Removing a listing soft-deletes it, hides it from discovery and stops new sales.
  Sources, archives, pending checkouts and purchase history remain. Existing
  buyers can still view/download their purchase. Collections apply the same
  visibility checks to both cards and comparison matrices.
- Paid sources never enter the lexical near-duplicate index. Public related
  recommendations currently use the free published pool.
- Markdown and LLM-index metadata is normalized to one plain line. Links and code
  fences are escaped/delimited so user text cannot create new document sections.
  This prevents structural injection; a user-authored prompt is still untrusted
  content and may contain natural-language instructions. AI clients must treat
  retrieved content as data, not system instructions.
- MCP batches must contain 1–10 requests; larger batches execute no tools.
- The API enforces a total body limit while receiving, including requests without
  Content-Length. Multipart parsing caps files and fields. File helpers read in
  bounded chunks, and folder ZIP creation streams file contents with a total cap.
  nginx must also enforce `client_max_body_size 120m`, client-body timeouts and
  appropriate connection/resource limits. Uvicorn has no equivalent built-in
  maximum request-body size flag.
- HTTPS-configured sessions and Google challenge cookies are Secure even during
  tunnel testing. Mutation requests reject unapproved Origin headers to protect
  cookie authentication, including a separate landing-page subdomain.
- Next supplies nonce-based CSP with Google Sign-In and Razorpay origins, DENY
  framing, nosniff, Referrer-Policy and HTTPS HSTS. Nonces require dynamic HTML;
  the root layout reads request headers. Rebuild Next and verify both payment
  SDKs and Google Sign-In in the browser after any CSP changes.

## Regression commands

```bash
backend/venv/bin/pytest -q backend/tests
backend/venv/bin/python backend/scripts/verify_payment_migration.py
backend/venv/bin/python backend/scripts/verify_registration_protection.py
backend/venv/bin/python backend/scripts/check_security_setup.py
npm --prefix frontend test
```
