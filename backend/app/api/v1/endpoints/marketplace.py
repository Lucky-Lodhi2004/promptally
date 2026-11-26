"""BYOG: all asset checkout requests use the seller's account, never platform keys."""
import hashlib
import hmac
import secrets
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.asset import Asset
from backend.app.models.user import User
from backend.app.models.purchase import AssetPurchase
from backend.app.models.marketplace import SellerGatewayConfig, PendingCheckout, SellerOAuthState
from backend.app.models.enums import PurchaseStatus, SellerGateway, CheckoutStatus
from backend.app.schemas.billing import SellerConnectRequest, DirectBuyResponse, VerifyPurchaseRequest
from backend.app.core.security import get_current_user, get_current_active_pro_user
from backend.app.services.crypto import encrypt_secret, decrypt_secret
from backend.app.services.geoip import checkout_country
from backend.app.services.membership import is_pro, utc
from backend.app.services.payments import gateway_request, inr_paise, verify_webhook, webhook_json
from backend.app.services.seller_onboarding import (
    oauth_ready, oauth_redirect_uri, exchange_token, save_tokens,
    oauth_access_token, setup_dodo_webhook,
)

from backend.app.services.idempotency import idempotent_checkout, checkout_reference, claim_webhook, provider_mutation_started, record_checkout_intent
from backend.app.services.analytics import capture_event

router = APIRouter()


def seller_request(config, method, gateway, path, payload=None):
    if method.upper() in {"POST", "PATCH", "DELETE"}:
        provider_mutation_started()
    if gateway == "razorpay":
        if config.razorpay_account_id:
            return gateway_request(method, gateway, path, key=oauth_access_token(config), oauth=True, payload=payload)
        return gateway_request(method, gateway, path, key=config.razorpay_key_id,
            secret=decrypt_secret(config.razorpay_key_secret_enc), payload=payload)
    return gateway_request(method, gateway, path, key=decrypt_secret(config.dodo_api_key_enc),
        environment=config.dodo_environment, payload=payload)


def seller_status(config):
    return {"razorpay_connected": bool(config and config.has_razorpay),
            "dodo_connected": bool(config and config.has_dodo),
            "dodo_environment": config.dodo_environment if config and config.has_dodo else None,
            "razorpay_oauth_available": oauth_ready(),
            "razorpay_connection_type": ("oauth" if config.razorpay_account_id else "manual") if config else None,
            "razorpay_environment": config.razorpay_oauth_environment if config else None,
            "dodo_webhook_managed": bool(config and config.dodo_webhook_id)}


@router.get("/sellers/gateways")
def get_seller_gateways(current_user: User = Depends(get_current_user)):
    return seller_status(current_user.gateway_config)


@router.post("/sellers/connect")
def connect_seller_payment(req: SellerConnectRequest, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_active_pro_user)):
    db.query(User).filter_by(id=current_user.id).with_for_update().one()
    config = current_user.gateway_config
    if config is None:
        config = SellerGatewayConfig(seller_id=current_user.id)
        db.add(config)
    now = datetime.now(timezone.utc)
    # Reject account replacement while assets/checkouts reference that account.
    if req.gateway_type == "razorpay":
        if config.razorpay_account_id:
            raise HTTPException(409, "Use Connect Razorpay to update an OAuth connection")
        changed = config.razorpay_key_id and config.razorpay_key_id != req.key_id
    else:
        changed = config.dodo_api_key_enc and (decrypt_secret(config.dodo_api_key_enc) != req.api_key.get_secret_value()
                                              or config.dodo_environment != req.environment)
    if changed and (db.query(Asset).filter_by(author_id=current_user.id, is_paid=True).first()
                    or db.query(PendingCheckout).filter_by(seller_id=current_user.id, status=CheckoutStatus.PENDING).first()):
        raise HTTPException(409, "Cannot replace a gateway account while paid listings or pending checkouts exist")
    # A successful account API call proves the API credentials work. Signing
    # secrets still need a real signed webhook; their last-seen time is exposed separately.
    if req.gateway_type == "razorpay":
        gateway_request("GET", "razorpay", "/orders?count=1", key=req.key_id,
                        secret=req.key_secret.get_secret_value())
        config.razorpay_key_id = req.key_id
        config.razorpay_key_secret_enc = encrypt_secret(req.key_secret.get_secret_value())
        config.razorpay_webhook_secret_enc = encrypt_secret(req.webhook_secret.get_secret_value())
        config.razorpay_verified_at = now
    else:
        key = req.api_key.get_secret_value().strip()
        if (key.startswith('dodo_test_') and req.environment != 'test'
                or key.startswith('dodo_live_') and req.environment != 'live'):
            raise HTTPException(400, 'Dodo API key does not match the selected environment')
        encrypted_key = encrypt_secret(key)
        gateway_request("GET", "dodo", "/products?page_size=1", key=key, environment=req.environment)
        # A supplied secret supports existing API clients. The new UI supplies
        # only the key, and the provider supplies its actual signing secret.
        if req.webhook_secret and req.webhook_secret.get_secret_value():
            if config.dodo_webhook_id:
                raise HTTPException(409, "This Dodo webhook is managed automatically; reconnect with only the API key")
            config.dodo_webhook_secret_enc = encrypt_secret(req.webhook_secret.get_secret_value())
        else:
            setup_dodo_webhook(config, key, req.environment, gateway_request)
        config.dodo_api_key_enc = encrypted_key
        config.dodo_environment = req.environment
        config.dodo_verified_at = now
    current_user.payouts_enabled = True
    current_user.seller_payment_config = seller_status(config)
    db.commit()
    capture_event(current_user.id, "seller_gateway_connected", {
        "gateway": req.gateway_type,
        "connection_type": "manual",
        "environment": req.environment if req.gateway_type == "dodo" else None,
    })
    return {"status": "success", **seller_status(config), "webhook_url":
            f"{settings.SITE_URL}{settings.API_V1_STR}/webhooks/{req.gateway_type}/{current_user.id}"}


@router.post('/sellers/razorpay/oauth/start')
def start_razorpay_oauth(response: Response, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_active_pro_user)):
    if not oauth_ready():
        raise HTTPException(503, 'Razorpay Connect is awaiting platform configuration')
    from backend.app.services.crypto import cipher
    cipher()
    nonce = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.query(SellerOAuthState).filter(SellerOAuthState.expires_at < now).delete()
    db.add(SellerOAuthState(state_hash=hashlib.sha256(nonce.encode()).hexdigest(),
        seller_id=current_user.id, environment=settings.RAZORPAY_PARTNER_ENVIRONMENT,
        expires_at=now + timedelta(minutes=10)))
    db.commit()
    response.set_cookie('razorpay_oauth_state', nonce, max_age=600, httponly=True,
                        secure=settings.SITE_URL.startswith('https://'), samesite='lax',
                        path=settings.API_V1_STR + '/sellers/razorpay/oauth/callback')
    return {'authorization_url': 'https://auth.razorpay.com/authorize?' + urlencode({
        'response_type': 'code', 'client_id': settings.RAZORPAY_PARTNER_CLIENT_ID,
        'redirect_uri': oauth_redirect_uri(), 'scope': 'read_write', 'state': nonce})}


@router.get('/sellers/razorpay/oauth/callback')
def razorpay_oauth_callback(request: Request, state: str = Query(..., min_length=20, max_length=200),
                           code: str = Query('', max_length=4096), error: str = Query('', max_length=200),
                           db: Session = Depends(get_db), current_user: User = Depends(get_current_active_pro_user)):
    if not oauth_ready():
        raise HTTPException(503, 'Razorpay Connect is unavailable')
    cookie = request.cookies.get('razorpay_oauth_state', '')
    nonce = db.query(SellerOAuthState).filter_by(state_hash=hashlib.sha256(state.encode()).hexdigest()).with_for_update().first()
    if (not cookie or not hmac.compare_digest(cookie, state) or not nonce or nonce.used_at
            or nonce.seller_id != current_user.id or utc(nonce.expires_at) <= datetime.now(timezone.utc)
            or nonce.environment != settings.RAZORPAY_PARTNER_ENVIRONMENT):
        raise HTTPException(400, 'Invalid or expired Razorpay connection. Please start again.')
    nonce.used_at = datetime.now(timezone.utc)
    db.commit()  # Consume once, even if a provider request fails.
    destination = settings.SITE_URL.rstrip('/') + '/dashboard?tab=seller-studio'
    if error or not code:
        result = RedirectResponse(destination + '&razorpay=denied', status_code=303)
    else:
        tokens = exchange_token({'grant_type': 'authorization_code', 'code': code,
            'redirect_uri': oauth_redirect_uri(), 'mode': nonce.environment})
        account_id = tokens.get('razorpay_account_id')
        if not isinstance(account_id, str) or not account_id.startswith('acc_') or len(account_id) > 120:
            raise HTTPException(502, 'Razorpay did not return a merchant account')
        if not tokens['public_token'].startswith('rzp_' + nonce.environment + '_oauth_'):
            raise HTTPException(502, 'Razorpay authorization environment mismatch')
        db.query(User).filter_by(id=current_user.id).with_for_update().one()
        config = current_user.gateway_config
        other = db.query(SellerGatewayConfig).filter_by(razorpay_account_id=account_id).first()
        if other and other.seller_id != current_user.id:
            raise HTTPException(409, 'This Razorpay account is already connected to another seller')
        if config is None:
            config = SellerGatewayConfig(seller_id=current_user.id)
            db.add(config)
        changed = config.razorpay_key_id and (config.razorpay_account_id != account_id
                  or config.razorpay_oauth_environment != nonce.environment)
        if changed and (db.query(Asset).filter_by(author_id=current_user.id, is_paid=True).first()
                       or db.query(PendingCheckout).filter_by(seller_id=current_user.id, status=CheckoutStatus.PENDING).first()):
            raise HTTPException(409, 'Cannot replace a Razorpay connection while paid listings or pending checkouts exist')
        gateway_request('GET', 'razorpay', '/orders?count=1', key=tokens['access_token'], oauth=True)
        save_tokens(config, tokens)
        config.razorpay_account_id = account_id
        config.razorpay_oauth_environment = nonce.environment
        config.razorpay_revoked_at = None
        config.razorpay_key_secret_enc = None
        config.razorpay_verified_at = datetime.now(timezone.utc)
        current_user.payouts_enabled = True
        current_user.seller_payment_config = seller_status(config)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Razorpay account is already connected') from None
        capture_event(current_user.id, "seller_gateway_connected", {
            "gateway": "razorpay",
            "connection_type": "oauth",
            "environment": nonce.environment,
        })
        result = RedirectResponse(destination + '&razorpay=connected', status_code=303)
    result.delete_cookie('razorpay_oauth_state', path=settings.API_V1_STR + '/sellers/razorpay/oauth/callback')
    return result


def ensure_dodo_product(asset, config):
    if asset.seller_dodo_product_id:
        return asset.seller_dodo_product_id
    result = seller_request(config, "POST", "dodo", "/products", {
        "name": asset.seo_title, "description": asset.short_description,
        "tax_category": "digital_products", "price": {"type": "one_time_price", "currency": "USD",
        "price": asset.price_cents, "tax_inclusive": True, "pay_what_you_want": False,
        "purchasing_power_parity": False}})
    asset.seller_dodo_product_id = result["product_id"]
    return asset.seller_dodo_product_id


@router.post("/assets/{slug}/buy", response_model=DirectBuyResponse)
@idempotent_checkout("purchase")
def buy_asset_direct(slug: str, request: Request, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    asset = db.query(Asset).filter_by(slug=slug.removesuffix(".md"), is_published=True).first()
    if not asset or not asset.is_paid or not asset.author:
        raise HTTPException(404, "Paid artifact not found")
    if asset.author_id == current_user.id:
        raise HTTPException(400, "You already own this artifact")
    existing = db.query(AssetPurchase).filter_by(buyer_id=current_user.id, asset_id=asset.id,
                                                status=PurchaseStatus.COMPLETED).first()
    if existing:
        return DirectBuyResponse(status="completed", payment_reference=existing.id, checkout_url=f"/p/{asset.slug}",
            seller_username=asset.author.username, amount_usd=asset.price_cents / 100,
            amount=existing.amount_cents, currency=existing.currency)
    if not is_pro(asset.author):
        raise HTTPException(409, "This seller's membership is inactive; new purchases are unavailable")
    _, india = checkout_country(request)
    config = asset.author.gateway_config
    gateway = "razorpay" if india else "dodo"
    if not config or not (config.has_razorpay if india else config.has_dodo):
        raise HTTPException(409, "Seller has no connected payment gateway for your region")
    pending = db.query(PendingCheckout).filter_by(buyer_id=current_user.id, asset_id=asset.id,
        status=CheckoutStatus.PENDING).order_by(PendingCheckout.created_at.desc()).first()
    if pending:
        if pending.gateway != SellerGateway(gateway.upper()):
            raise HTTPException(409, "Resume the existing checkout before changing payment region")
        url = None
        if not india:
            session = seller_request(config, "GET", gateway, f"/checkouts/{pending.provider_order_id}")
            url = session.get('checkout_url')
            if not url:
                raise HTTPException(409, "Existing checkout requires payment confirmation before starting another")
        return DirectBuyResponse(gateway=gateway, payment_reference=pending.id, checkout_url=url,
            seller_username=asset.author.username, amount_usd=asset.price_cents / 100,
            amount=pending.expected_amount_minor, currency=pending.currency,
            key_id=config.razorpay_key_id if india else None,
            order_id=pending.provider_order_id if india else None)
    reference = checkout_reference()
    metadata = {"promptally_checkout_id": reference, "promptally_artifact_id": asset.id,
                "promptally_buyer_id": current_user.id, "promptally_seller_id": asset.author_id}
    currency = "INR" if india else "USD"
    amount = (asset.price_inr_paise or inr_paise(asset.price_cents)) if india else asset.price_cents
    if amount <= 0:
        raise HTTPException(400, "Invalid asset price")
    record_checkout_intent(db, gateway=gateway, asset_id=asset.id, seller_id=asset.author_id,
                           amount=amount, currency=currency)
    if india:
        remote = seller_request(config, "POST", gateway, "/orders", {
            "amount": amount, "currency": currency, "receipt": reference, "notes": metadata})
        remote_id = remote["id"]
        url = None
        if remote.get("amount") != amount or remote.get("currency") != currency:
            raise HTTPException(502, "Provider order price mismatch")
    else:
        product_id = ensure_dodo_product(asset, config)
        remote = seller_request(config, "POST", gateway, "/checkouts", {
            "product_cart": [{"product_id": product_id, "quantity": 1}], "billing_currency": "USD",
            "customer": {"email": current_user.email, "name": current_user.name},
            "return_url": f"{settings.SITE_URL}/p/{asset.slug}?payment=pending&checkout_reference={reference}", "metadata": metadata})
        remote_id, url = remote["session_id"], remote["checkout_url"]
    db.add(PendingCheckout(id=reference, buyer_id=current_user.id, asset_id=asset.id,
        seller_id=asset.author_id, gateway=SellerGateway(gateway.upper()), provider_order_id=remote_id,
        expected_amount_minor=amount, currency=currency))
    return DirectBuyResponse(gateway=gateway, payment_reference=reference, checkout_url=url,
        seller_username=asset.author.username, amount_usd=asset.price_cents / 100, amount=amount, currency=currency,
        key_id=config.razorpay_key_id if india else None, order_id=remote_id if india else None)


def complete_purchase(db, config, gateway, data):
    if gateway == "razorpay":
        if data.get("event") != "order.paid":
            return
        entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id, order_id = entity.get("id"), entity.get("order_id")
    else:
        if data.get("type") != "payment.succeeded":
            return
        entity = data.get("data", {})
        payment_id, order_id = entity.get("payment_id"), entity.get("checkout_session_id")
    if not isinstance(payment_id, str) or not isinstance(order_id, str):
        raise HTTPException(400, "Missing payment or checkout reference")
    checkout = db.query(PendingCheckout).filter_by(provider_order_id=order_id, seller_id=config.seller_id,
                    gateway=SellerGateway(gateway.upper())).with_for_update().first()
    if not checkout:
        raise HTTPException(409, "Checkout has not been recorded; retry webhook")
    if checkout.status == CheckoutStatus.PAID:
        return
    remote = seller_request(config, "GET", gateway, f"/payments/{payment_id}")
    if gateway == "razorpay":
        order = seller_request(config, 'GET', gateway, f'/orders/{order_id}')
        paid = (remote.get("status") == "captured" and remote.get("captured") is True
                and remote.get("order_id") == order_id and not remote.get("amount_refunded", 0)
                and order.get('id') == order_id and order.get('status') == 'paid'
                and order.get('amount') == checkout.expected_amount_minor
                and order.get('amount_paid') == checkout.expected_amount_minor
                and order.get('currency') == checkout.currency)
        amount = remote.get("amount")
    else:
        paid = remote.get("status") == "succeeded" and remote.get("checkout_session_id") == order_id
        amount = remote.get("total_amount")
        cart = remote.get("product_cart") or []
        asset = db.get(Asset, checkout.asset_id)
        paid = paid and len(cart) == 1 and cart[0].get("product_id") == asset.seller_dodo_product_id and cart[0].get("quantity") == 1
    if not paid or amount != checkout.expected_amount_minor or remote.get("currency") != checkout.currency:
        raise HTTPException(400, "Payment state, amount, currency or product mismatch")
    # Serialize distinct successful checkouts for one buyer before creating the
    # unique buyer/asset entitlement. Webhooks and direct checks share this lock.
    db.query(User).filter_by(id=checkout.buyer_id).with_for_update().one()
    purchase = db.query(AssetPurchase).filter_by(buyer_id=checkout.buyer_id, asset_id=checkout.asset_id).first()
    if purchase is None:
        purchase = AssetPurchase(buyer_id=checkout.buyer_id, asset_id=checkout.asset_id, seller_id=checkout.seller_id)
        db.add(purchase)
    # A second successful checkout must not overwrite the entitlement's transaction.
    completed_now = False
    if purchase.status != PurchaseStatus.COMPLETED:
        purchase.amount_cents = amount  # Legacy column name: minor units of purchase.currency.
        purchase.currency = checkout.currency
        purchase.platform_fee_cents = 0
        purchase.seller_payout_cents = amount
        purchase.provider = gateway
        purchase.provider_payment_id = payment_id
        purchase.payment_reference = gateway + ":" + payment_id
        purchase.status = PurchaseStatus.COMPLETED
        completed_now = True
    checkout.status = CheckoutStatus.PAID
    if completed_now:
        return (checkout.buyer_id, "asset_purchased", {
            "asset_id": checkout.asset_id,
            "seller_id": checkout.seller_id,
            "gateway": gateway,
            "currency": checkout.currency,
            "amount_minor": amount,
        })
    return None


@router.post('/assets/{slug}/verify-payment')
def verify_purchase(slug: str, req: VerifyPurchaseRequest, response: Response,
                    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    asset = db.query(Asset).filter_by(slug=slug.removesuffix('.md')).first()
    checkout = db.query(PendingCheckout).filter_by(id=req.payment_reference,
        buyer_id=current_user.id, asset_id=asset.id if asset else '').with_for_update().first()
    if not checkout:
        raise HTTPException(404, 'Checkout not found')
    if checkout.status == CheckoutStatus.PAID:
        return {'status': 'completed', 'unlocked': True}
    config = db.get(SellerGatewayConfig, checkout.seller_id)
    gateway = checkout.gateway.value.lower()
    if not config or not (config.has_razorpay if gateway == 'razorpay' else config.has_dodo):
        raise HTTPException(409, 'Seller payment account requires attention')
    payment_id = req.payment_id
    if gateway == 'razorpay':
        if payment_id:
            secret = (settings.RAZORPAY_PARTNER_CLIENT_SECRET if config.razorpay_account_id
                      else decrypt_secret(config.razorpay_key_secret_enc))
            expected = hmac.new(secret.encode(), f'{checkout.provider_order_id}|{payment_id}'.encode(), hashlib.sha256).hexdigest()
            if not req.signature or not hmac.compare_digest(req.signature, expected):
                raise HTTPException(401, 'Invalid checkout signature')
        order = seller_request(config, 'GET', gateway, f'/orders/{checkout.provider_order_id}')
        if order.get('status') != 'paid':
            response.status_code = 202
            return {'status': 'pending', 'unlocked': False}
        if not payment_id:
            payments = seller_request(config, 'GET', gateway, f'/orders/{checkout.provider_order_id}/payments')
            payment_id = next((p.get('id') for p in payments.get('items', []) if p.get('status') == 'captured'), None)
        if not payment_id:
            response.status_code = 202
            return {'status': 'pending', 'unlocked': False}
        event = {'event': 'order.paid', 'payload': {'payment': {'entity': {
            'id': payment_id, 'order_id': checkout.provider_order_id}}}}
    else:
        session = seller_request(config, 'GET', gateway, f'/checkouts/{checkout.provider_order_id}')
        if session.get('payment_status') in {'failed', 'cancelled', 'expired'}:
            return {'status': 'failed', 'unlocked': False}
        payment_id = session.get('payment_id')
        if session.get('payment_status') != 'succeeded' or not payment_id:
            response.status_code = 202
            return {'status': 'pending', 'unlocked': False}
        event = {'type': 'payment.succeeded', 'data': {
            'payment_id': payment_id, 'checkout_session_id': checkout.provider_order_id}}
    analytics_event = complete_purchase(db, config, gateway, event)
    db.commit()
    if analytics_event:
        capture_event(analytics_event[0], analytics_event[1], {**analytics_event[2], "via": "verify"})
    return {'status': 'completed', 'unlocked': True}


async def seller_webhook(seller_id, request, db, gateway):
    config = db.get(SellerGatewayConfig, seller_id)
    if not config or not (config.has_razorpay if gateway == "razorpay" else config.has_dodo):
        raise HTTPException(404, "Seller gateway is not connected")
    if gateway == 'razorpay' and config.razorpay_account_id:
        raise HTTPException(404, 'Use the Razorpay partner application webhook')
    body = await request.body()
    encrypted = config.razorpay_webhook_secret_enc if gateway == "razorpay" else config.dodo_webhook_secret_enc
    event_id = verify_webhook(request, body, gateway, decrypt_secret(encrypted))
    scope = f"seller:{gateway}:{seller_id}"
    if not claim_webhook(db, scope, event_id):
        return {"status": "ok"}
    analytics_event = complete_purchase(db, config, gateway, webhook_json(body))
    if gateway == "razorpay":
        config.razorpay_last_webhook_at = datetime.now(timezone.utc)
    else:
        config.dodo_last_webhook_at = datetime.now(timezone.utc)
    db.commit()
    if analytics_event:
        capture_event(analytics_event[0], analytics_event[1], {**analytics_event[2], "via": "webhook"})
    return {"status": "ok"}


@router.post('/webhooks/razorpay/partner')
async def razorpay_partner_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    event_id = verify_webhook(request, body, 'razorpay', settings.RAZORPAY_PARTNER_WEBHOOK_SECRET)
    event = webhook_json(body)
    account_id = event.get('account_id')
    config = db.query(SellerGatewayConfig).filter_by(razorpay_account_id=account_id).first() if account_id else None
    if not config:
        # Application events may concern authorized merchants that have not
        # finished onboarding, and orders created outside Promptally.
        return {'status': 'ignored'}
    scope = f'seller:razorpay:{config.seller_id}'
    if not claim_webhook(db, scope, event_id):
        return {"status": "ok"}
    analytics_event = None
    if event.get('event') == 'account.app.authorization_revoked':
        created = event.get('created_at')
        if (not isinstance(created, (int, float)) or not config.razorpay_verified_at
                or created >= utc(config.razorpay_verified_at).timestamp()):
            config.razorpay_revoked_at = datetime.now(timezone.utc)
    else:
        # Ignore merchant payments not started through a saved Promptally checkout.
        order_id = event.get('payload', {}).get('payment', {}).get('entity', {}).get('order_id')
        if event.get('event') == 'order.paid' and db.query(PendingCheckout).filter_by(
                seller_id=config.seller_id, gateway=SellerGateway.RAZORPAY, provider_order_id=order_id).first():
            analytics_event = complete_purchase(db, config, 'razorpay', event)
    config.razorpay_last_webhook_at = datetime.now(timezone.utc)
    db.commit()
    if analytics_event:
        capture_event(analytics_event[0], analytics_event[1], {**analytics_event[2], "via": "partner_webhook"})
    return {'status': 'ok'}


@router.post("/webhooks/razorpay/{seller_id}")
async def razorpay_seller_webhook(seller_id: str, request: Request, db: Session = Depends(get_db)):
    return await seller_webhook(seller_id, request, db, "razorpay")


@router.post("/webhooks/dodo/{seller_id}")
async def dodo_seller_webhook(seller_id: str, request: Request, db: Session = Depends(get_db)):
    return await seller_webhook(seller_id, request, db, "dodo")
