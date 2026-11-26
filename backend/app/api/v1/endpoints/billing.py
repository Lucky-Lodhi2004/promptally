"""Platform-owned $1/month subscriptions. Seller checkouts live in marketplace.py."""
import uuid
import re
from urllib.parse import urlencode
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.purchase import Subscription
from backend.app.models.marketplace import CheckoutAttempt
from backend.app.models.enums import SubscriptionGateway, SubscriptionStatus
from backend.app.schemas.billing import SubscribeResponse, CancelSubscriptionResponse
from backend.app.core.config import settings
from backend.app.core.security import get_current_user
from backend.app.services.geoip import checkout_country
from backend.app.services.membership import is_pro, refresh_tier, utc
from backend.app.services.payments import platform_request, inr_paise, verify_webhook, webhook_json

from backend.app.services.idempotency import idempotent_checkout, checkout_reference, claim_webhook, record_checkout_intent
from backend.app.services.analytics import capture_event

router = APIRouter()


def parse_time(value):
    try:
        if isinstance(value, (float, int)):
            return datetime.fromtimestamp(value, timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Provider billing period is missing or invalid") from None


@router.get("/billing/quote")
def subscription_quote(request: Request):
    country, india = checkout_country(request)
    return {"country_code": country, "gateway": "razorpay" if india else "dodo",
            "currency": "INR" if india else "USD", "amount": inr_paise() if india else 100,
            "interval": "month", "amount_unit": "minor"}


@router.post("/billing/subscribe", response_model=SubscribeResponse)
@idempotent_checkout("subscription")
def create_subscription(request: Request, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    country, india = checkout_country(request)
    # Lock a row that exists even for first-time subscribers, serializing concurrent starts.
    db.query(User).filter_by(id=current_user.id).with_for_update().one()
    sub = db.query(Subscription).filter_by(user_id=current_user.id).with_for_update().first()
    if is_pro(current_user):
        raise HTTPException(409, "An active subscription already exists")
    # A failed initial Dodo payment consumes its checkout session. Confirm both
    # provider states before replacing it; an on-hold renewal or an uncertain
    # payment must never create a second billable subscription.
    if (sub and sub.status == SubscriptionStatus.PAST_DUE
            and sub.gateway == SubscriptionGateway.DODO
            and sub.checkout_session_id and sub.gateway_subscription_id):
        checkout = platform_request("GET", "dodo", f"/checkouts/{sub.checkout_session_id}")
        remote = platform_request("GET", "dodo", f"/subscriptions/{sub.gateway_subscription_id}")
        metadata = remote.get("metadata") or {}
        if (checkout.get("payment_status") == "failed"
                and remote.get("status") == "failed"
                and remote.get("product_id") == sub.gateway_plan_id
                and metadata.get("promptally_subscription_id") == sub.id
                and metadata.get("promptally_checkout_reference") == sub.checkout_reference):
            sub.status = SubscriptionStatus.CANCELED
    if sub and sub.status == SubscriptionStatus.PENDING and (sub.gateway_subscription_id or sub.checkout_session_id):
        gateway = sub.gateway.value.lower()
        if gateway != ('razorpay' if india else 'dodo'):
            raise HTTPException(409, "Resume the existing checkout before changing payment region")
        return SubscribeResponse(gateway=gateway, currency=sub.currency, amount=sub.expected_amount_minor,
            country_code=country, subscription_id=sub.gateway_subscription_id,
            checkout_url=sub.checkout_url, checkout_session_id=sub.checkout_session_id,
            key_id=settings.RAZORPAY_KEY_ID if india else None)
    if sub and sub.status in (SubscriptionStatus.PENDING, SubscriptionStatus.PAST_DUE, SubscriptionStatus.ACTIVE):
        raise HTTPException(409, "Resume or cancel your existing subscription before starting another")
    gateway = "razorpay" if india else "dodo"
    amount = inr_paise() if india else 100
    reference = checkout_reference()
    subscription_id = sub.id if sub else str(uuid.uuid4())
    record_checkout_intent(db, gateway=gateway, subscription_id=subscription_id,
                           amount=amount, currency="INR" if india else "USD")
    if sub is None:
        sub = Subscription(id=subscription_id, user_id=current_user.id)
        db.add(sub)
    sub.gateway = SubscriptionGateway(gateway.upper())
    sub.status = SubscriptionStatus.PENDING
    sub.currency = "INR" if india else "USD"
    sub.expected_amount_minor = amount
    sub.current_period_end = datetime.now(timezone.utc)
    sub.cancel_at_period_end = False
    sub.last_event_at = None
    sub.checkout_reference = reference
    sub.gateway_subscription_id = None
    sub.checkout_session_id = None
    metadata = {"promptally_subscription_id": sub.id, "promptally_checkout_reference": reference,
                "promptally_user_id": current_user.id}
    if india:
        if settings.RAZORPAY_PLAN_ID:
            plan = platform_request("GET", gateway, f"/plans/{settings.RAZORPAY_PLAN_ID}")
        else:
            plan = platform_request("POST", gateway, "/plans", {
                "period": "monthly", "interval": 1,
                "item": {"name": "Promptally Pro ($1 equivalent)", "amount": amount, "currency": "INR"}})
        if (plan.get("period") != "monthly" or plan.get("interval") != 1
                or plan.get("item", {}).get("amount") != amount
                or plan.get("item", {}).get("currency") != "INR"):
            raise HTTPException(503, "Razorpay plan must match the quoted monthly INR price")
        remote = platform_request("POST", gateway, "/subscriptions", {
            "plan_id": plan["id"], "total_count": 120, "quantity": 1,
            "customer_notify": 1, "notes": metadata})
        sub.gateway_plan_id = plan["id"]
        sub.gateway_subscription_id = remote["id"]
        sub.checkout_url = remote.get("short_url")
    else:
        if not settings.DODO_PRODUCT_ID:
            raise HTTPException(503, "Dodo monthly subscription product is not configured")
        product = platform_request("GET", gateway, f"/products/{settings.DODO_PRODUCT_ID}")
        price = product.get("price", {})
        if (price.get("type") != "recurring_price" or price.get("price") != 100
                or price.get("currency") != "USD" or price.get("payment_frequency_count") != 1
                or price.get("payment_frequency_interval") != "Month"
                or price.get("trial_period_days", 0) or price.get("discount", 0)
                or price.get("discount_bps", 0) or price.get("purchasing_power_parity", False)):
            raise HTTPException(503, "Dodo product must be a $1 USD monthly plan without trials or discounts")
        remote = platform_request("POST", gateway, "/checkouts", {
            "product_cart": [{"product_id": settings.DODO_PRODUCT_ID, "quantity": 1}],
            "customer": {"email": current_user.email, "name": current_user.name},
            "billing_currency": "USD", "metadata": metadata,
            "return_url": settings.SITE_URL + "/dashboard?subscription=pending"})
        sub.gateway_plan_id = settings.DODO_PRODUCT_ID
        sub.checkout_session_id = remote["session_id"]
        sub.checkout_url = remote["checkout_url"]
    return SubscribeResponse(gateway=gateway, currency=sub.currency, amount=amount, country_code=country,
                             subscription_id=sub.gateway_subscription_id, checkout_url=sub.checkout_url,
                             checkout_session_id=sub.checkout_session_id,
                             key_id=settings.RAZORPAY_KEY_ID if india else None)


@router.get("/billing/checkout-attempts/{attempt_id}")
def checkout_attempt_status(attempt_id: str, db: Session = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    attempt = db.query(CheckoutAttempt).filter_by(id=attempt_id, user_id=current_user.id).first()
    if not attempt:
        raise HTTPException(404, "Checkout attempt not found")
    return {"id": attempt.id, "status": attempt.status, "operation": attempt.operation,
            "checkout": attempt.response if attempt.status == 'succeeded' else None}


@router.get("/billing/subscription")
def get_subscription(current_user: User = Depends(get_current_user)):
    sub = current_user.subscription
    return {"is_pro": is_pro(current_user), "subscription": None if sub is None else {
        "status": sub.status.value, "gateway": sub.gateway.value.lower(),
        "current_period_end": sub.current_period_end, "cancel_at_period_end": sub.cancel_at_period_end,
        "checkout_url": sub.checkout_url if sub.status == SubscriptionStatus.PENDING else None,
        "currency": sub.currency, "amount": sub.expected_amount_minor,
        "subscription_id": sub.gateway_subscription_id,
        "key_id": settings.RAZORPAY_KEY_ID if sub.gateway == SubscriptionGateway.RAZORPAY else None}}


def reconcile_razorpay_subscription(db, sub, remote=None):
    """Recover a missed charge only from the current cycle's paid invoice and capture."""
    if sub.gateway != SubscriptionGateway.RAZORPAY or not sub.gateway_subscription_id:
        return False
    if remote is None:
        remote = platform_request('GET', 'razorpay', f'/subscriptions/{sub.gateway_subscription_id}')
    notes = remote.get('notes') or {}
    start, end = remote.get('current_start'), remote.get('current_end')
    if (remote.get('id') != sub.gateway_subscription_id or remote.get('status') != 'active'
            or remote.get('plan_id') != sub.gateway_plan_id
            or not isinstance(notes, dict)
            or notes.get('promptally_subscription_id') != sub.id
            or notes.get('promptally_checkout_reference') != sub.checkout_reference
            or not isinstance(start, (int, float)) or not isinstance(end, (int, float))
            or end <= start or end <= datetime.now(timezone.utc).timestamp()):
        return False
    # Older invoices must not grant a newer billing period. Fetch pagination
    # explicitly; a subscription may have more than one page of history.
    for skip in range(0, 1000, 100):
        query = urlencode({'subscription_id': sub.gateway_subscription_id, 'count': 100, 'skip': skip})
        result = platform_request('GET', 'razorpay', '/invoices?' + query)
        invoices = result.get('items') or []
        for invoice in invoices:
            invoice_id, payment_id = invoice.get('id'), invoice.get('payment_id')
            if (invoice.get('subscription_id') != sub.gateway_subscription_id or invoice.get('status') != 'paid'
                    or invoice.get('amount') != sub.expected_amount_minor
                    or invoice.get('amount_paid') != sub.expected_amount_minor
                    or invoice.get('currency') != sub.currency
                    or invoice.get('billing_start') != start or invoice.get('billing_end') != end
                    or not isinstance(invoice_id, str) or not re.fullmatch(r'inv_[A-Za-z0-9]+', invoice_id)
                    or not isinstance(payment_id, str) or not re.fullmatch(r'pay_[A-Za-z0-9]+', payment_id)):
                continue
            payment = platform_request('GET', 'razorpay', f'/payments/{payment_id}')
            if (payment.get('id') != payment_id or payment.get('invoice_id') != invoice_id
                    or payment.get('status') != 'captured' or payment.get('captured') is not True
                    or payment.get('amount') != sub.expected_amount_minor
                    or payment.get('currency') != sub.currency or payment.get('amount_refunded', 0)):
                continue
            sub.status = SubscriptionStatus.ACTIVE
            sub.current_period_end = parse_time(end)
            sub.provider_customer_id = remote.get('customer_id')
            sub.last_event_at = datetime.now(timezone.utc)
            refresh_tier(sub.user)
            return True
        if len(invoices) < 100:
            break
    return False


@router.post('/billing/verify')
def verify_subscription(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Subscription).filter_by(user_id=current_user.id).with_for_update().first()
    if sub and sub.gateway == SubscriptionGateway.RAZORPAY and not is_pro(current_user):
        activated = reconcile_razorpay_subscription(db, sub)
        db.commit()
        if activated:
            capture_event(current_user.id, "pro_subscription_activated", {
                "gateway": "razorpay",
                "currency": sub.currency,
                "amount_minor": sub.expected_amount_minor,
                "via": "verify",
            })
    return get_subscription(current_user)


@router.post("/billing/cancel", response_model=CancelSubscriptionResponse)
def cancel_subscription(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Subscription).filter_by(user_id=current_user.id).with_for_update().first()
    if not sub:
        raise HTTPException(400, "No subscription to cancel")
    if sub.status == SubscriptionStatus.CANCELED:
        return CancelSubscriptionResponse(status="success", message="Subscription is already cancelled.")
    if sub.cancel_at_period_end and is_pro(current_user):
        return CancelSubscriptionResponse(status="success", message="Cancellation already scheduled; Pro access lasts through the paid billing period.")
    if not sub.gateway_subscription_id:
        # Keep this pending checkout bound until the provider confirms its state;
        # otherwise a late payment could create a second billable subscription.
        raise HTTPException(409, "Finish the existing checkout before cancelling, or let it expire")
    gateway = sub.gateway.value.lower()
    if gateway not in {"razorpay", "dodo"}:
        raise HTTPException(409, "Legacy subscription requires billing support")
    paid_access = is_pro(current_user)
    if gateway == "razorpay":
        remote = platform_request("POST", gateway, f"/subscriptions/{sub.gateway_subscription_id}/cancel",
                                  {"cancel_at_cycle_end": 1 if paid_access else 0})
    else:
        payload = {"cancel_at_next_billing_date": True} if paid_access else {"status": "cancelled"}
        remote = platform_request("PATCH", gateway, f"/subscriptions/{sub.gateway_subscription_id}", payload)
    identity_key = "id" if gateway == "razorpay" else "subscription_id"
    if not isinstance(remote, dict) or remote.get(identity_key) != sub.gateway_subscription_id:
        raise HTTPException(502, "Payment provider returned an unexpected subscription; check cancellation status before retrying")
    state = remote.get("status")
    if state in {"cancelled", "canceled", "completed", "expired"}:
        sub.status = SubscriptionStatus.CANCELED
        sub.cancel_at_period_end = False
        refresh_tier(current_user)
        message = "Subscription cancelled. No further renewals are scheduled."
    elif (paid_access and state == "active"
          and (gateway == "razorpay" or remote.get("cancel_at_next_billing_date") is True)):
        # Razorpay acknowledges a cycle-end cancellation with an active entity;
        # it has no equivalent to Dodo's cancel_at_next_billing_date response flag.
        sub.cancel_at_period_end = True
        message = "Cancellation scheduled; Pro access lasts through the paid billing period."
    else:
        raise HTTPException(502, "Payment provider did not confirm cancellation; check cancellation status before retrying")
    db.commit()
    capture_event(current_user.id, "pro_subscription_canceled", {
        "gateway": gateway,
        "cancel_at_period_end": sub.cancel_at_period_end,
    })
    return CancelSubscriptionResponse(status="success", message=message)


def apply_subscription_event(db, gateway, event):
    """Fetch current provider state to prevent out-of-order webhooks regressing access."""
    event_type = event.get("event") if gateway == "razorpay" else event.get("type")
    if not isinstance(event_type, str) or not event_type.startswith("subscription."):
        return
    if gateway == "razorpay":
        entity = event.get("payload", {}).get("subscription", {}).get("entity", {})
        remote_id = entity.get("id")
        sub = db.query(Subscription).filter_by(gateway=SubscriptionGateway.RAZORPAY,
                    gateway_subscription_id=remote_id).with_for_update().first() if remote_id else None
    else:
        entity = event.get("data", {})
        remote_id = entity.get("subscription_id")
        metadata = entity.get("metadata") or {}
        sub = db.query(Subscription).filter_by(gateway=SubscriptionGateway.DODO,
                    gateway_subscription_id=remote_id).with_for_update().first() if remote_id else None
        if sub is None and remote_id:
            sub = db.query(Subscription).filter_by(id=metadata.get("promptally_subscription_id"),
                    gateway=SubscriptionGateway.DODO,
                    checkout_reference=metadata.get("promptally_checkout_reference")).with_for_update().first()
    if not sub:
        raise HTTPException(409, "Subscription checkout has not been recorded; retry webhook")
    remote = platform_request("GET", gateway, f"/subscriptions/{remote_id}")
    if gateway == "razorpay":
        if remote.get("plan_id") != sub.gateway_plan_id:
            raise HTTPException(400, "Subscription plan mismatch")
        state = remote.get("status")
        end = remote.get("current_end")
        # Only a captured recurring charge can initially grant Pro.
        paid = event.get("payload", {}).get("payment", {}).get("entity", {})
        valid_charge = (event_type == "subscription.charged" and paid.get("status") == "captured"
                        and paid.get("amount") == sub.expected_amount_minor and paid.get("currency") == sub.currency)
        if not valid_charge and state == "active" and utc(sub.current_period_end) <= datetime.now(timezone.utc):
            # Some initial activation events have no captured payment entity.
            # Confirm the actual invoice/capture instead of ignoring a paid user.
            if reconcile_razorpay_subscription(db, sub, remote):
                return (sub.user_id, "pro_subscription_activated", {
                    "gateway": gateway, "currency": sub.currency,
                    "amount_minor": sub.expected_amount_minor, "via": "webhook",
                })
            return None
    else:
        metadata = remote.get("metadata") or {}
        if (remote.get("product_id") != sub.gateway_plan_id
                or metadata.get("promptally_checkout_reference") != sub.checkout_reference
                or remote.get("currency") != "USD" or remote.get("recurring_pre_tax_amount") != 100):
            raise HTTPException(400, "Subscription checkout or price mismatch")
        state = remote.get("status")
        end = remote.get("next_billing_date")
        sub.gateway_subscription_id = remote_id
        sub.provider_customer_id = (remote.get("customer") or {}).get("customer_id")
        sub.cancel_at_period_end = remote.get("cancel_at_next_billing_date", False)
    previous_status = sub.status
    analytics_event = None
    if state == "active":
        sub.current_period_end = parse_time(end)
        sub.status = SubscriptionStatus.ACTIVE
        if previous_status != SubscriptionStatus.ACTIVE:
            analytics_event = (sub.user_id, "pro_subscription_activated", {
                "gateway": gateway, "currency": sub.currency,
                "amount_minor": sub.expected_amount_minor, "via": "webhook",
            })
    elif state in {"cancelled", "canceled", "completed", "expired"}:
        sub.status = SubscriptionStatus.CANCELED
        sub.cancel_at_period_end = False
        if previous_status != SubscriptionStatus.CANCELED:
            analytics_event = (sub.user_id, "pro_subscription_canceled", {
                "gateway": gateway, "cancel_at_period_end": False, "via": "webhook",
            })
    elif state in {"pending", "halted", "on_hold", "failed", "paused", "past_due"}:
        sub.status = SubscriptionStatus.PAST_DUE
    sub.last_event_at = datetime.now(timezone.utc)
    refresh_tier(sub.user)
    return analytics_event


async def platform_webhook(request, db, gateway):
    body = await request.body()
    secret = settings.RAZORPAY_WEBHOOK_SECRET if gateway == "razorpay" else settings.DODO_WEBHOOK_SECRET
    event_id = verify_webhook(request, body, gateway, secret)
    scope = "platform:" + gateway
    if not claim_webhook(db, scope, event_id):
        return {"status": "ok"}
    analytics_event = apply_subscription_event(db, gateway, webhook_json(body))
    db.commit()
    if analytics_event:
        capture_event(*analytics_event)
    return {"status": "ok"}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    return await platform_webhook(request, db, "razorpay")


@router.post("/webhooks/dodo")
async def dodo_webhook(request: Request, db: Session = Depends(get_db)):
    return await platform_webhook(request, db, "dodo")
