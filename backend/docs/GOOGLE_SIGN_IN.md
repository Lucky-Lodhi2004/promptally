# Sign in with Google

The login/signup modal renders Google's official Identity Services button.
Its popup returns an ID token; FastAPI verifies it and creates the normal
Promptally session. The current page refreshes its authenticated profile.

## Setup

Backend-only settings in `backend/.env`:

```ini
GOOGLE_CLIENT_ID=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=YOUR_PRIVATE_CLIENT_SECRET
REDIS_URL=redis://127.0.0.1:6388/0
SITE_URL=https://YOUR_CURRENT_PUBLIC_ORIGIN
```

The ID-token sign-in flow needs the **client ID**, not the secret. The secret
stays private and is reserved for future authorization-code integrations. The
browser obtains the public ID through `/api/v1/auth/google/start`; no frontend
environment variable or secret is needed.

In Google Cloud → Google Auth Platform → Clients, select a **Web application**.
Add actual frontend origins under **Authorized JavaScript origins**, without paths:

- The current public HTTPS origin matching `SITE_URL`.
- `http://localhost:3000` and/or `http://127.0.0.1:3000` for local testing.
- The proxy origin on port 3001 if used directly; also add it to backend CORS.

A new zrok hostname requires updating Google's origins, `SITE_URL`, and backend
CORS. Configure branding, audience and test users as required by the project's
consent-screen status. This popup uses a JavaScript callback; no custom OAuth
redirect URI, Gmail scopes, API key, service account or refresh token is required.

Install and restart the backend, then build/restart the frontend:

```bash
backend/venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend run build
```

Required verification packages: `google-auth`, `requests`, `cachecontrol`.
Google website sign-in needs no migration: `users.google_sub` already has a unique index.
MCP OAuth reuses this sign-in and adds its own tables and consent flow; see
[MCP OAuth](MCP_OAUTH.md) for its required migration and client setup.

## Security and account behavior

- `POST /api/v1/auth/google/start` accepts a fingerprint and creates a five-minute
  random nonce/CSRF challenge in Redis, bound to that device and an HttpOnly,
  SameSite=Strict browser cookie. Only the public client ID/challenge is returned.
- The official `https://accounts.google.com/gsi/client` button uses that nonce.
  Expired challenges and loading failures offer explicit retry. Automatic account
  selection is off. `Cross-Origin-Opener-Policy: same-origin-allow-popups` supports
  the popup. A deployment CSP must allow Google's documented script/frame hosts.
- `POST /api/v1/auth/google` accepts the credential, CSRF token and fingerprint.
  The backend checks browser origin/cookie binding, signature, issuer, exact
  audience/client ID, expiry, subject and verified-email claim, then atomically
  consumes the nonce. Redis outage fails closed. Public signing certificates are
  cached; certificate fetches have a five-second timeout. Google tokens and the
  client secret are never stored in browser storage or database.
- Returning users are found by Google's stable `sub`, not mutable email. A Google
  email change does not replace the local email, password, purchases or tier.
- New Google accounts use the same durable IP/device signup quotas as password
  accounts. Existing users do not spend another signup allowance.
- Google is authoritative for Gmail and Workspace identities with an `hd` claim.
  Those new accounts are immediately email verified. Third-party Google addresses
  without that claim still receive Promptally's own verification email and have
  restricted access until verified.
- Existing email accounts may be linked only when the local email was actually
  verified, Google is authoritative for it, and no other Google subject is linked.
  Otherwise login returns 409. An unverified pre-registered password must not be
  blessed by another person's Google sign-in. Legacy users retain access and can
  use the verification banner before enabling Google sign-in. Passwords remain.
- Success returns the normal Promptally bearer token and HttpOnly cookie, refreshes
  the profile and closes the modal. Logout clears Promptally session/Google CSRF
  cookies and disables Google's auto-selection, without logging out of Google.

## Verification

```bash
backend/venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test
```

Isolated tests cover nonce/CSRF/replay, device binding, identity changes, quotas,
account linking and actual Google verification using test RSA signing keys.
They do not authenticate a real Google user or send email.

For a real login, open an authorized frontend origin → Sign in/Sign up → Continue
with Google. Confirm the profile appears, persists after reload, and can log out
and back in. New accounts still obey the two-account limit. The local proxy
currently simulates all clients as `127.0.0.1`; a spent quota correctly blocks new
Google registrations. Do not silently clear accounts or disable quotas.

Official references:
- https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid
- https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
