# Signup, email verification and request limits

New email/password accounts receive a limited authenticated session. They can
read their own profile, request a verification email, and log out. Protected
features (publishing, collections, purchases, subscriptions, profile/password
changes, seller connections) require email verification. Public browsing stays
available. Google registrations use the server-validated verified-email claim. A new unverified
email/password account must verify its email before a Google login can reuse it;
this avoids blessing a password selected by someone who pre-registered the address.

Existing accounts are grandfathered by the additive migration: they retain
access with `email_verification_required=false`, while `email_verified_at` stays
empty. This does not claim their email was verified. New registrations always
set verification required, and the database default is true.

## Limits

- At most **2 successful account creations per IP**, independently of device.
- At most **2 successful account creations per device fingerprint**, independently
  of IP. Both email and new Google registrations use the same durable counters.
- Unverified registrations count as account creations. The counters are lifetime
  counters, with no automatic expiry or decrement on account deletion. Failed
  transactions roll back their quota reservations.
- **60 normal reads and 10 sensitive actions per rolling 60-second window**,
  independently per IP and per supplied device. GET/HEAD use the read budget;
  writes and OAuth callbacks use the sensitive budget. The two budgets are
  separate; either exhausted IP or device bucket produces 429 for that class.
- Verification resends require authentication, have a 60-second cooldown, and
  have additional limits of 5/hour per IP and per account/email identity.
- Payment webhook paths, static uploads, health checks, and CORS preflights are
  outside the browser request budget. Payment callbacks still require their
  existing signatures and idempotency checks. User-Agent strings do not bypass
  limits. Redis failure returns 503 rather than permitting unprotected requests.

PostgreSQL quota rows are inserted atomically, locked in a deterministic order,
and incremented in the transaction that creates the user and email outbox.
Existing users' IP/device counts are backfilled during migration. Deleting users
or clearing Redis does not free registration capacity. Take care when testing:
multiple people behind one NAT share an IP. The local nginx configuration
currently simulates all requests as `127.0.0.1`, so its accounts share that cap.
Do not delete production quota rows to work around the policy.

The browser sends `X-Device-Fingerprint` with each API request. Signup requires a
valid fingerprint, and inconsistent header/body values are rejected. The existing
canvas/browser signal is computed once per page. This signal is spoofable and
can change across browsers/devices; it is not proof of hardware identity. Missing
fingerprints never bypass IP limits. Only trusted ingress peers may provide the
client IP: ingress must overwrite forwarding headers. Configure the true client
IP correctly in production, including any server-rendered frontend API calls.

## Verification and reliable delivery

`POST /api/v1/auth/verify-email` accepts `{"token": "..."}`. It does not sign the
browser in. `POST /api/v1/auth/resend-verification` uses the current session.
Verification links expire in 15 minutes, can be consumed once, and are invalidated
by resend. PostgreSQL consumes the token hash and sets `email_verified_at` in one
transaction. Redis caches only hashes with matching TTL; PostgreSQL remains the
verification authority so cache loss cannot resurrect a token or lose verified
account state.

Account creation, the token hash, and an encrypted mail outbox record commit
together. Celery receives only the outbox ID, never the raw token. The worker
sends through SMTP with certificate-validated TLS and clears the encrypted token
after success. SMTP failures retry through the outbox with backoff. Celery beat
re-enqueues pending rows every 30 seconds, recovering lost broker messages.
Expired/superseded email tasks are canceled. Retries use the same link. SMTP can
accept a message just before a worker crashes, so duplicate delivery is possible;
the verification action itself remains single-use.

The frontend link uses `/verify-email#token=...`: fragments stay out of server
access logs and Referer headers. The page clears the fragment from history and
requires a confirmation click so email link scanners do not consume the token.
The verification banner provides resend and refresh actions. Payment polling now
uses 20-second intervals and respects 429 backoff.

## Local setup

From the repository root:

```bash
backend/venv/bin/pip install -r backend/requirements.txt
docker compose up -d postgres redis
backend/venv/bin/alembic -c backend/alembic.ini upgrade head
```

Configure `backend/.env` (the example file is not loaded by FastAPI):

```ini
REDIS_URL=redis://127.0.0.1:6388/0
CELERY_BROKER_URL=redis://127.0.0.1:6388/1
RATE_LIMIT_ENABLED=true
RATE_LIMIT_READ_PER_MINUTE=60
RATE_LIMIT_PER_MINUTE=10
MAX_ACCOUNTS_PER_IP=2
MAX_ACCOUNTS_PER_DEVICE=2

SMTP_HOST=YOUR_EXACT_ZOHO_INDIA_SMTP_HOST
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=contact@promptally.dev
SMTP_PASSWORD=YOUR_NEW_PRIVATE_APP_PASSWORD
EMAIL_FROM=contact@promptally.dev
EMAIL_TOKEN_TTL_SECONDS=900
EMAIL_RESEND_COOLDOWN_SECONDS=60
```

Use the exact SMTP hostname listed in Zoho Mail's account settings for your plan
and India data center; do not infer it from the login domain. For implicit TLS,
use `SMTP_PORT=465` and `SMTP_SECURITY=ssl`. Plaintext SMTP is not supported.
Do not commit the app password or reuse a password exposed in chat. Keep
`CREDENTIALS_ENCRYPTION_KEY` stable: it also encrypts queued email tokens.
`SITE_URL` must match the current public frontend/tunnel so verification links
reach the correct app.
After changing the tunnel or `SITE_URL`, restart the Celery worker as well as
FastAPI. Each process loads `.env` at startup; restarting FastAPI alone leaves
the mail worker sending links with its previous URL. Already delivered emails
keep their old link, so use Resend verification after restarting the worker.

Start these in separate terminals, and restart both after changing SMTP settings:

```bash
backend/venv/bin/celery -A backend.app.worker:celery_app worker --loglevel=WARNING --concurrency=2
backend/venv/bin/celery -A backend.app.worker:celery_app beat --loglevel=WARNING --schedule=/tmp/promptally-celerybeat-schedule
```

Restart FastAPI and rebuild/restart the frontend as well. Both the worker and beat
must stay running. Missing SMTP configuration leaves emails pending for retries;
it never marks accounts verified or exposes verification links in API responses.
After 15 minutes an unsent challenge expires and the user must request another.

Run `backend/venv/bin/python backend/scripts/check_email_setup.py` to inspect
configuration without printing credentials or sending email. The check also
reports whether the local proxy IP has already reached its signup quota.

## Tests

```bash
backend/venv/bin/python -m pytest backend/tests -q
backend/venv/bin/python backend/scripts/verify_registration_protection.py
backend/venv/bin/python backend/scripts/verify_payment_migration.py
npm --prefix frontend test
```

Tests use isolated databases, private Redis processes, and fake SMTP delivery.
The PostgreSQL concurrency script verifies independent IP/device quotas, counter
persistence after deletion, concurrent single-use verification, and duplicate
worker delivery. Tests do not send email or create payment-provider transactions.
