"""Small provider adapter. No customer entitlement is changed by these calls."""
import base64
import hashlib
import hmac
import json
import time
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import httpx
from fastapi import HTTPException, Request
from backend.app.core.config import settings

_fx_cache = (0.0, Decimal(0))


def gateway_request(method, gateway, path, *, key, secret=None, environment="live", payload=None, oauth=False):
    if not key or (gateway == "razorpay" and not secret and not oauth):
        raise HTTPException(503, "Payment gateway credentials are not configured")
    if gateway == "razorpay":
        base = "https://api.razorpay.com/v1"
        kwargs = {"headers": {"Authorization": f"Bearer {key}"}} if oauth else {"auth": (key, secret)}
    else:
        if environment not in {"test", "live"}:
            raise HTTPException(503, "Invalid Dodo environment")
        base = f"https://{environment}.dodopayments.com"
        kwargs = {"headers": {"Authorization": f"Bearer {key}"}}
    if method.upper() in {"POST", "PATCH", "DELETE"}:
        from backend.app.services.idempotency import provider_mutation_started
        provider_mutation_started()
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.request(method, base + path, json=payload, **kwargs)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError):
        # Never expose provider bodies: they can contain customer data or secrets.
        raise HTTPException(502, "Payment provider request failed") from None


def platform_request(method, gateway, path, payload=None):
    if method.upper() in {"POST", "PATCH", "DELETE"}:
        from backend.app.services.idempotency import provider_mutation_started
        provider_mutation_started()
    if gateway == "razorpay":
        return gateway_request(method, gateway, path, key=settings.RAZORPAY_KEY_ID,
                               secret=settings.RAZORPAY_KEY_SECRET, payload=payload)
    return gateway_request(method, gateway, path, key=settings.DODO_API_KEY,
                           environment=settings.DODO_ENVIRONMENT, payload=payload)


def inr_paise(usd_cents=100):
    global _fx_cache
    try:
        if settings.USD_TO_INR_RATE:
            rate = Decimal(settings.USD_TO_INR_RATE)
        elif _fx_cache[0] > time.time():
            rate = _fx_cache[1]
        else:
            with httpx.Client(timeout=10) as client:
                res = client.get("https://api.frankfurter.dev/v1/latest", params={"base": "USD", "symbols": "INR"})
                res.raise_for_status()
                rate = Decimal(str(res.json()["rates"]["INR"]))
            _fx_cache = (time.time() + settings.FX_CACHE_SECONDS, rate)
        if not rate.is_finite() or rate <= 0:
            raise ValueError()
        return int((Decimal(usd_cents) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidOperation):
        raise HTTPException(503, "USD/INR exchange rate is unavailable") from None


def verify_webhook(request: Request, body: bytes, gateway: str, secret: str) -> str:
    if not secret:
        raise HTTPException(503, "Webhook secret is not configured")
    if gateway == "razorpay":
        signature = request.headers.get("x-razorpay-signature", "")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature):
            raise HTTPException(401, "Invalid webhook signature")
        # Body digest fallback is stable across retries when the event-id is absent.
        return request.headers.get("x-razorpay-event-id") or hashlib.sha256(body).hexdigest()
    event_id = request.headers.get("webhook-id", "")
    stamp = request.headers.get("webhook-timestamp", "")
    try:
        if not event_id or abs(time.time() - int(stamp)) > 300:
            raise ValueError()
        encoded_key = secret.removeprefix("whsec_")
        signing_key = base64.b64decode(encoded_key, validate=True)
        signed = event_id.encode() + b"." + stamp.encode() + b"." + body
        expected = base64.b64encode(hmac.new(signing_key, signed, hashlib.sha256).digest()).decode()
        signatures = request.headers.get("webhook-signature", "").split()
        if not any(hmac.compare_digest(s, "v1," + expected) for s in signatures):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(401, "Invalid webhook signature or timestamp") from None
    return event_id


def webhook_json(body):
    try:
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid webhook JSON") from None
