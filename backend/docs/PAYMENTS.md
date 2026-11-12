# Subscriptions and direct seller payments

## What is implemented

The platform sells a $1 USD/month Pro membership. Indian IPs use the platform's
Razorpay account, in INR at the USD/INR reference rate quoted at signup. Other
verified countries use the platform's Dodo account, in USD. The Indian recurring
amount is fixed for that subscription's lifetime; it is not repriced every month.
New INR quotes use the cached ECB reference rate via Frankfurter, or an explicit
operator-supplied USD_TO_INR_RATE. This is a reference conversion, not a guarantee
about a bank's conversion rate. Rates must be available to start an INR checkout.

Pro permits collections and paid publishing; Pro does not unlock others' paid
assets. A verified one-time purchase unlocks its own asset independently of both
parties' future membership. When a seller's membership expires, existing listings
and buyer rights remain, but new purchases and paid publishing are blocked.
Existing collections remain readable with their original visibility. No grace
period or free trial is granted. Refund policy is not automated by these endpoints;
revoke an entitlement through a reviewed refund reconciliation process.

Seller checkout always uses the seller's own API credentials. No seller sale uses
a platform account, and the platform commission is zero (provider fees still apply).
The listing INR price is snapshotted at publishing; its USD price is in cents.
A seller may connect one or both gateways. An Indian buyer requires that seller's
Razorpay account; a foreign buyer requires that seller's Dodo account. There is no
silent cross-region fallback. Missing gateways produce a clear checkout error.

## Setup

Install backend/requirements.txt and configure backend/.env from .env.example.
Generate a Fernet encryption key once and back it up separately from the database.
Do not reuse the JWT secret or replace the encryption key without re-encrypting
existing seller credentials. Provider responses and secrets are not returned to
clients. The connection API validates API access, but cannot prove that a seller
copied the matching webhook secret until a correctly signed event arrives.

Configure platform Razorpay keys and webhook secret. Leave RAZORPAY_PLAN_ID empty
to create a monthly plan at the quoted INR equivalent, or configure a monthly INR
plan whose amount matches the current quote. The integration creates a 120-cycle
monthly subscription, subject to provider/account recurring-payment availability.

Configure platform Dodo keys, environment, webhook secret, and a recurring product
with USD price 100, monthly payment frequency count 1, no trial or discounts, and
no purchasing-power discount. Use a long subscription period for recurring renewal.
Set tax-inclusive pricing if the total should be exactly $1 including taxes.
Disable adaptive currency changes and checkout discounts in the merchant settings
for fixed-USD sales. Amount/currency mismatches fail closed at webhook processing.

Register platform webhooks:

- /api/v1/webhooks/razorpay: subscription.charged, subscription.cancelled,
  subscription.completed, subscription.halted, subscription.pending,
  subscription.activated, subscription.paused, subscription.resumed.
- /api/v1/webhooks/dodo: subscription.active, subscription.renewed,
  subscription.updated, subscription.cancelled, subscription.expired,
  subscription.failed, subscription.on_hold.

Only charged/captured Razorpay subscription events initially grant Pro. Signed
Dodo subscription events are cross-checked against current provider subscription
state, product, price and the server-issued checkout reference. Current provider
state is fetched for lifecycle events to handle delivery order. Pro checks also
check current_period_end on every privileged operation, so missed cancellation
webhooks cannot extend access beyond the recorded paid period.

### Verified IP country

Choose one of these deployment arrangements:

1. Put the API behind a controlled ingress (e.g. Cloudflare), configure its actual
   socket peer CIDRs in TRUSTED_PROXY_CIDRS, and have it overwrite CF-IPCountry and
   CF-Connecting-IP. Restrict origin access to that ingress. Never trust forwarding
   headers copied from a browser. If your reverse proxy forwards Cloudflare
   headers, it must first verify that its own upstream is Cloudflare.
2. Set GEOIP_DATABASE_PATH to an updated local GeoLite2-Country.mmdb file. Install
   geoip2 and supply the actual public client IP on the socket, or forward
   CF-Connecting-IP/X-Real-IP through a configured trusted proxy.

Run Uvicorn with --no-proxy-headers so the application can verify the actual peer:

    backend/venv/bin/uvicorn backend.app.main:app --no-proxy-headers

Untrusted CF-IPCountry, X-Country-Code, X-Dev-Country and X-Forwarded-For values
cannot select the payment gateway. Private/local IPs are not assumed Indian.
Unknown countries return 503 for checkout; ordinary browsing/signup still work.
IP geolocation identifies network location, not nationality, and VPNs can change it.

## Client API contract

All `amount` fields are integer minor units (INR paise or USD cents).

- GET /api/v1/billing/quote: verified country, gateway, currency, $1-equivalent price.
- POST /api/v1/billing/subscribe: creates a pending checkout. For Razorpay, open
  Razorpay Checkout with key_id + subscription_id. For Dodo, navigate to checkout_url.
- GET /api/v1/billing/subscription: read confirmed membership and resume checkout URL.
  Starting a second checkout while one is pending/active is blocked.
- POST /api/v1/billing/verify: reconcile the signed-in user's pending Razorpay
  membership with provider records. Activation requires a matching current-cycle
  paid invoice and captured, non-refunded payment at the expected price/currency.
  The dashboard uses this alongside normal status polling to recover missed
  subscription.charged events. Keep subscription.charged selected on the platform
  webhook; payment.captured or order.paid alone do not identify Pro activation.
- POST /api/v1/billing/cancel: calls the provider to cancel at period end. A Dodo
  checkout without an actual subscription cannot yet be cancelled through this API.
  Paid active subscriptions retain access until the stored period end; subscriptions
  without paid access request immediate cancellation. Provider responses must identify
  the expected subscription and confirm the resulting state (including Dodo's scheduled
  cancellation flag). Repeating a confirmed scheduled or completed cancellation succeeds
  without another provider mutation. The dashboard shows the access end date and disables
  cancellation while a request is pending or cancellation is already scheduled.
- GET /api/v1/sellers/gateways: connection status only, no credentials.
- POST /api/v1/sellers/connect (Pro required):

    {"gateway_type":"razorpay", "key_id":"...", "key_secret":"...", "webhook_secret":"..."}
    {"gateway_type":"dodo", "api_key":"...", "environment":"test"}

  Dodo webhook setup and signing-key retrieval are automatic. For manual Razorpay,
  register the returned seller URL for order.paid. Razorpay OAuth instead uses one
  platform-managed application webhook. See [seller onboarding](SELLER_ONBOARDING.md).
  Seller account replacement is
  blocked while that account has paid listings or pending checkouts.
- POST /api/v1/assets (multipart): paid listings require Pro, a connected gateway,
  positive price_usd, image and payload. A Dodo product is created automatically
  in the seller's own account when their Dodo connection exists.
- POST /api/v1/assets/{slug}/buy: creates a pending seller checkout. Razorpay returns
  seller key_id, order_id, amount and currency; Dodo returns checkout_url. The
  payment_reference is a local checkout ID, not proof of a successful payment.

After redirect, re-fetch the asset/subscription status; redirects never grant access.
Webhooks verify raw-body signatures, replay windows for Dodo, provider checkout
references, state, amount, currency and seller ownership before persisting access.
Webhook event deduplication and the entitlement insert commit together. Unknown
checkout IDs return 409 so providers retry if a webhook races checkout persistence.
Subscription and seller webhook endpoints have separate secrets and idempotency scopes.

Paid source files are stored in private_uploads/archives. Public media, avatars
and collection covers remain under uploads. Legacy uploads/archives is no longer
publicly mounted. All file delivery must pass the download access check. JSON and
Markdown asset details have private/no-store caching to prevent entitlement leaks.

## Database upgrade and validation

Back up the database before applying migrations:

    backend/venv/bin/alembic -c backend/alembic.ini upgrade head

The existing migration chain assumes a pre-existing core schema. For a completely
empty database, initialize Base.metadata.create_all(engine) and stamp head; do not
run the destructive seed script against a database with user data. Revision
f4b91c2d7001 adds checkout state and invalidates locally fabricated legacy
subscriptions/purchases while preserving those rows for audit. This is necessary:
the old code marked checkout starts as paid, with no provider confirmation.
Historical migration e3f2f2494e54 now backfills new non-null columns safely.
Database migrations are validated against a disposable PostgreSQL cluster.
Apply them to each application database during deployment.
Paddle is retained only as a legacy database enum; it is never used for new checkout.

    backend/venv/bin/python -m pytest backend/tests -q
    backend/venv/bin/python backend/scripts/verify_payment_migration.py

Tests use isolated databases and mock provider APIs; they do not charge cards,
contact live payment accounts, or mutate the configured application database.
Complete merchant sandbox testing with real keys and a configured ingress before
production activation. The frontend includes subscription and seller checkout UI.

## Provider references

- https://razorpay.com/docs/api/payments/subscriptions/create-subscription/
- https://razorpay.com/docs/webhooks/subscriptions/
- https://docs.dodopayments.com/api-reference/checkout-sessions/create
- https://docs.dodopayments.com/api-reference/products/post-products
- https://docs.dodopayments.com/api-reference/subscriptions/patch-subscriptions
- https://docs.dodopayments.com/developer-resources/webhooks
- https://frankfurter.dev/v1/

## Frontend integration

Browser API requests now use `/api/v1` on the frontend origin. Next proxies that
path and `/uploads` to API_INTERNAL_URL (default http://127.0.0.1:8000/api/v1).
Configure API_INTERNAL_URL in the frontend server environment; it is not a public
browser URL. Restart Next after changing it. Legacy NEXT_PUBLIC_API_URL is accepted
only as a fallback for the internal destination. Production must run Next with its
server/rewrite support; a static-only export cannot proxy the API or render assets.

Set NEXT_PUBLIC_SITE_URL and backend SITE_URL to the same public HTTPS origin.
The proxy forwards authentication cookies; copy/download also include stored bearer
credentials. JSON/Markdown and paid file responses must not be cached publicly.
If another reverse proxy precedes Next, its verified country headers and real-IP
headers must be propagated and the backend must trust only the actual Next/proxy
socket peer. Do not treat Next's ordinary client-supplied country headers as verified.

The frontend serves `/directory` and asset metadata on the server. Discovery routes
(`/llms.txt`, `/sitemap.xml`, `/.well-known/mcp.json`) and `/p/{slug}.md` proxy to the
backend. Collection requests use form encoding and distinguish asset IDs from
collection-item IDs. Membership pages expose Resume checkout for PENDING sessions.
After provider callbacks, status is checked for up to one minute; if confirmation
is delayed, users can check again without creating another subscription.

Check configuration without exposing keys:

    backend/venv/bin/python backend/scripts/check_payment_setup.py

Supply your own merchant keys, signing secrets and monthly Dodo product ID in
backend/.env or the deployment secret store. Configure trusted ingress or a GeoIP
country database, register the printed webhook URLs in each merchant dashboard,
then test signed sandbox events. This configuration cannot be fabricated in code.
Frontend regression tests: `cd frontend && npm test`.

Full-stack smoke test (requires installed frontend dependencies and unused ports 8045/3055):

    backend/venv/bin/python frontend/scripts/verify-integration.py

This builds a temporary frontend copy and starts both services against an isolated
database. It checks SSR metadata, paid-content sanitization, media and API proxying,
discovery routes, and collection create/add/read/remove, then stops its services.

## Checkout and webhook idempotency

Both `POST /api/v1/billing/subscribe` and `POST /api/v1/assets/{slug}/buy` accept
`Idempotency-Key` (8–128 ASCII letters, digits, `.`, `:`, `_`, or `-`). The frontend
creates a UUID and retains it per authenticated buyer/action in local storage.
Network failures and HTTP 409/5xx responses keep the same key. Subscription state
changes clear the browser key so a later subscription can be a new attempt.
Older API clients without a key remain supported; resource-level guards still apply.

PostgreSQL `checkout_attempts` is authoritative:

- Unique `(user_id, operation, idempotency_key)` binds the key to the request.
- A partial unique index permits only one `processing` or `unknown` attempt per
  buyer, operation and resource, including requests using different keys.
- The initial claim commits before any provider mutation. Immutable pricing,
  seller and resource context is saved before creating an order/session.
- `succeeded` stores the checkout response in the same transaction as the local
  checkout/subscription. Replays return that response. Different keys reuse an
  existing pending checkout, including checkouts created before this migration.
- Validation failures before a remote mutation become `failed` and can retry.
  Ambiguous errors after a remote mutation become `unknown`. A worker crash can
  leave `processing`. Neither state expires into permission to create another
  checkout, even after Redis is cleared or restarted.
- Reusing a key for another prompt or country returns HTTP 409.

Optional Redis uses `SET NX EX 60` and a random ownership token, released through
an atomic compare-and-delete Lua script. PostgreSQL guards remain active if Redis
is disabled, unavailable, evicted, or its lock expires. A busy Redis lock returns
HTTP 409 with `Retry-After`; it does not grant access or acknowledge a webhook.
Redis stores locks only, not payment authority or secrets.

Existing signed webhook handlers use `webhook_events` with unique
`(provider_scope, event_id)`. Platform and each seller have separate scopes.
`INSERT ... ON CONFLICT DO NOTHING RETURNING` handles only that duplicate;
unrelated database errors propagate. The event claim and membership/purchase
changes commit together. Failed processing rolls back the claim for redelivery.
Unique purchase/payment constraints still protect distinct events for one payment
and races between direct verification and webhook delivery.

### Local setup

From the repository root:

```bash
backend/venv/bin/pip install -r backend/requirements.txt
docker compose up -d redis
backend/venv/bin/alembic -c backend/alembic.ini upgrade head
```

Set in `backend/.env`, then restart FastAPI:

```ini
REDIS_URL=redis://127.0.0.1:6388/0
```

The Redis service binds only to loopback, uses an AOF volume and `noeviction`.
`REDIS_PORT` can override the Docker host port; update `REDIS_URL` to match.
An empty `REDIS_URL` uses PostgreSQL protection alone. Keep this setting empty in
unit tests; `verify_payment_idempotency.py` starts its own disposable Redis.
Rebuild/restart the frontend to enable persistent browser keys.

### Uncertain provider outcomes

This implementation deliberately does not blindly retry gateway POST requests:
provider idempotency support must be confirmed for each exact API endpoint.
An operator must reconcile `unknown` or abandoned `processing` attempts before
another payment is allowed. The attempt UUID is also the Razorpay receipt and
`promptally_checkout_id` or `promptally_checkout_reference` metadata value.
The saved `request_data` records the expected seller, amount, currency and resource.

HTTP 409 for such an attempt includes `X-Checkout-Attempt`. Its buyer can inspect
`GET /api/v1/billing/checkout-attempts/{attempt_id}`; another buyer receives 404.
A `succeeded` attempt means checkout creation succeeded, not that money was paid.
Access still requires verified provider payment evidence.

For reconciliation, use the correct test/live merchant account to locate that
exact reference, verify the provider object and payment, and restore its local
checkout/subscription and replay response transactionally. A timeout, elapsed
TTL, missing webhook, or one empty list page is not proof of failure. Do not
clear attempt rows or change `unknown` to `failed` merely to enable another try.
Automatic adoption of orphaned provider objects is not implemented; these rare
cases require operator reconciliation.

### Verification

```bash
backend/venv/bin/python -m pytest backend/tests -q
backend/venv/bin/python backend/scripts/verify_payment_idempotency.py
backend/venv/bin/python backend/scripts/verify_payment_migration.py
npm --prefix frontend test
```

The concurrency script uses a disposable PostgreSQL cluster and Redis process,
never configured merchant credentials or the application database. It checks
concurrent webhook commit/rollback, concurrent checkout claims, Redis-independent
PostgreSQL protection, lock ownership after expiry, and durable blocking after
Redis state loss.
