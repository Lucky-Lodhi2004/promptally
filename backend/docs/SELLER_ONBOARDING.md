# Seller connections

Platform Pro subscriptions keep using `RAZORPAY_KEY_*` and `DODO_*` in the backend environment.
Seller connections are separate: customers pay the seller's merchant account, with no platform
commission. Payment processor fees and taxes still apply.

## Install and migrate

Run from the repository root with the configured database backed up:

```bash
backend/venv/bin/alembic -c backend/alembic.ini upgrade head
```

Migration `a81d92f41002` adds nullable onboarding fields and an OAuth state table.
It preserves existing merchant credentials, listings, subscriptions and purchases.
Restart FastAPI. Rebuild/restart the frontend if using `next start`:

```bash
cd frontend
npm run build
npm run start -- --hostname 127.0.0.1 --port 3000
```

## Dodo: seller supplies only an API key

In Dashboard → Seller Studio, choose test or live and enter a Dodo API key with write access.
No signing secret is requested. The backend:

1. Validates credentials and the encryption configuration.
2. Searches the merchant's webhooks for the existing seller URL, following pagination.
3. Reuses a matching endpoint, or creates a disabled endpoint using a deterministic idempotency key.
4. Reads its signing key with `GET /webhooks/{id}/secret` and encrypts it.
5. Enables `payment.succeeded`, then saves the completed connection.

Repeated attempts adopt the endpoint left by a partially completed setup. A failed setup does
not mark a new connection as connected or overwrite a working connection's saved secrets.
Existing manually configured endpoints at the same URL can be adopted. If SITE_URL changes,
reconnect with the same key to update a previously managed endpoint. Use a permanent HTTPS
domain before production. Duplicate endpoints previously created by hand need operator cleanup.

`SITE_URL` must be publicly reachable HTTPS for automatic setup. Tagged keys must match the
selected mode; untagged legacy keys remain supported. Products are created on the seller's
account when a paid prompt is published, or lazily before its first Dodo checkout.

The legacy API still accepts an explicitly supplied signing secret for existing clients;
the new UI always requests automatic setup. Never submit a placeholder secret.

## Razorpay: connect through OAuth

First obtain Razorpay Technology Partner access and create an application. This is a platform
operator prerequisite; a seller cannot enable it by supplying ordinary payment API keys.

Configure these backend settings (see `.env.example`):

```dotenv
RAZORPAY_PARTNER_CLIENT_ID="application-client-id"
RAZORPAY_PARTNER_CLIENT_SECRET="application-client-secret"
RAZORPAY_PARTNER_WEBHOOK_SECRET="application-webhook-secret"
RAZORPAY_PARTNER_ENVIRONMENT="test"
RAZORPAY_PARTNER_REDIRECT_URI="https://YOUR_DOMAIN/api/v1/sellers/razorpay/oauth/callback"
```

Whitelist that exact redirect URI on the application. Use the matching development/production
client and mode. Keep platform subscription keys independent. Restart FastAPI after editing
the environment. Connect is disabled until the required partner settings exist.

Configure **one application webhook**, in the Razorpay Partner Dashboard → Applications →
Manage Webhook:

```text
https://YOUR_DOMAIN/api/v1/webhooks/razorpay/partner
```

Subscribe to `order.paid` and `account.app.authorization_revoked`, using
`RAZORPAY_PARTNER_WEBHOOK_SECRET` as its signing secret. This uses Razorpay's documented
application webhook flow; it does not assume that ordinary OAuth grants can create per-merchant
webhooks through partner-only APIs.

The seller then clicks Connect with Razorpay, signs in and authorizes. Promptally uses a random
ten-minute, single-use state stored as a hash and bound to both the seller and an HttpOnly browser
cookie. The callback requires the same logged-in Pro seller. Tokens are encrypted; checkout
receives only the public token. Expiring tokens refresh under a database lock in an independent
transaction, so a failed checkout cannot roll back a refresh-token rotation. Signed revocation
events disable the connection.

Existing manual connections continue to work. An advanced manual form is available while OAuth
is not configured. To prevent charging the wrong merchant, switching account/mode or migrating
a manual Razorpay connection with existing paid listings/pending checkouts is blocked. This
requires a separate audited migration, not automatic credential replacement.

## Regions and publishing

The paid publish form links to the two seller connections. Razorpay enables Indian buyers in
INR, Dodo enables foreign buyers in USD, and both enable both groups. At least one connection
is required; the backend still enforces active Pro membership, price and preview requirements.
Connecting a gateway does not change platform subscription billing or grant purchased access.

Preview sources may be up to 15 MiB. Before an asset row is committed, JPEG, PNG and WebP
previews are decoded, stripped of metadata and re-encoded as WebP at no more than 5 MiB.
Animated GIFs are validated and, when needed, optimized or downscaled to no more than 10 MiB.
Invalid images, excessive dimensions/frame counts, or files that cannot reach the storage cap
are rejected and are not referenced by the asset.

## Payment confirmation

`POST /api/v1/assets/{slug}/verify-payment` accepts a saved `payment_reference`. For the Razorpay
SDK callback, also pass `payment_id` and `signature`. The signature uses the saved order ID and
the manual key secret or OAuth application's client secret. The backend checks the provider's
order/payment under the seller's credentials, including capture, refund state, exact amount and
currency. It binds the saved checkout to the authenticated buyer, seller and asset.

Without callback data, the same endpoint can reconcile a saved checkout directly with the
provider. Dodo reconciliation fetches the session and verifies its payment and product. Neither
frontend success flags nor metadata alone grant access. Direct checks and signed webhooks
share the same entitlement function and serialize completion. A delayed webhook after a direct
check cannot duplicate an entitlement. The UI uses bounded reconciliation and access polling;
it never claims a fixed provider response time.

## Validation

```bash
backend/venv/bin/python -m pytest backend/tests -q
backend/venv/bin/python backend/scripts/verify_payment_migration.py
cd frontend
npm test
npx tsc --noEmit
npm run build
```

Tests mock provider APIs and use isolated databases. Merchant OAuth authorization, API write
permissions and actual signed application events still require sandbox end-to-end testing
with your partner credentials. No production keys are needed for automated tests.

Provider references:
- https://razorpay.com/docs/partners/technology-partners/onboard-businesses/integrate-oauth/integration-steps/
- https://razorpay.com/docs/partners/technology-partners/onboard-businesses/integrate-oauth/subscribe-to-webhooks/
- https://docs.dodopayments.com/api-reference/webhooks/create-webhook
- https://docs.dodopayments.com/api-reference/webhooks/get-webhook-signing-key
