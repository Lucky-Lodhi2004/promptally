"""Durable checkout claims; Redis is an optional contention optimization.

A claim is committed BEFORE calling a provider. A crash/ambiguous provider error
leaves it blocked for reconciliation, never eligible for automatic recreation.
"""
import hashlib
import json
import logging
import re
import secrets
import uuid
from contextvars import ContextVar
from functools import wraps
from inspect import signature
from contextlib import contextmanager

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from backend.app.core.config import settings
from backend.app.models.user import User
from backend.app.models.asset import Asset
from backend.app.models.marketplace import CheckoutAttempt, PendingCheckout, WebhookEvent
from backend.app.models.purchase import Subscription
from backend.app.models.enums import CheckoutStatus, SubscriptionStatus
from backend.app.services.geoip import checkout_country

log = logging.getLogger(__name__)
_current = ContextVar('checkout_attempt', default=None)
_RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


def checkout_reference():
    context = _current.get()
    return context['id'] if context else str(uuid.uuid4())


def record_checkout_intent(db, **snapshot):
    """Save immutable pricing/account context before any remote mutation."""
    context = _current.get()
    if context is not None:
        attempt = db.get(CheckoutAttempt, context['id'])
        attempt.request_data = {**snapshot, "reference": context["id"]}
        db.commit()


def provider_mutation_started():
    context = _current.get()
    if context is not None:
        context['remote_started'] = True


@contextmanager
def redis_lock(scope):
    client = None
    token = secrets.token_hex(24)
    key = 'promptally:checkout:' + hashlib.sha256(scope.encode()).hexdigest()
    acquired = False
    if settings.REDIS_URL:
        try:
            from redis import Redis
            client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
            acquired = bool(client.set(key, token, nx=True, ex=60))
        except Exception:
            # PostgreSQL still serializes claims and forbids a second in-flight operation.
            log.warning('Checkout Redis unavailable; using PostgreSQL claim protection')
        else:
            if not acquired:
                client.close()
                raise HTTPException(409, 'Checkout creation is in progress. Retry with the same Idempotency-Key.',
                                    headers={'Retry-After': '2'})
    try:
        yield
    finally:
        if client is not None:
            try:
                if acquired:
                    client.eval(_RELEASE, 1, key, token)
            except Exception:
                log.warning('Checkout lock release failed; lock will expire')
            finally:
                client.close()


def claim_webhook(db, scope, event_id):
    """Only this named conflict is a duplicate; unrelated DB failures propagate.

    PostgreSQL waits for any conflicting uncommitted insert: if its transaction
    rolls back, this insert succeeds. Caller commits this claim with its effects.
    """
    insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
    stmt = insert(WebhookEvent).values(id=str(uuid.uuid4()), provider=scope, event_id=event_id)
    stmt = stmt.on_conflict_do_nothing(index_elements=['provider', 'event_id']).returning(WebhookEvent.id)
    return db.execute(stmt).scalar_one_or_none() is not None


def _pending(db, attempt):
    reference = (attempt.request_data or {}).get('reference', attempt.id)
    if attempt.operation == 'subscription':
        return db.query(Subscription).filter_by(user_id=attempt.user_id,
            checkout_reference=reference, status=SubscriptionStatus.PENDING).first() is not None
    reference = (attempt.response or {}).get('payment_reference', reference)
    return db.query(PendingCheckout).filter_by(id=reference, status=CheckoutStatus.PENDING).first() is not None


def idempotent_checkout(operation):
    def decorate(fn):
        sig = signature(fn)
        @wraps(fn)
        def wrapped(*args, **kwargs):
            bound = sig.bind(*args, **kwargs).arguments
            db, request, user = bound['db'], bound['request'], bound['current_user']
            resource = bound.get('slug', 'pro').removesuffix('.md')
            if operation == 'purchase':
                asset = db.query(Asset).filter_by(slug=resource, is_published=True).first()
                # Use immutable identity so renaming an asset cannot bypass an in-flight claim.
                if asset is not None:
                    resource = asset.id
            country, _ = checkout_country(request)
            key = request.headers.get('Idempotency-Key')
            # Compatibility with older API clients: cross-key resource guards still apply.
            if key is None:
                key = str(uuid.uuid4())
            if not re.fullmatch(r'[A-Za-z0-9_.:-]{8,128}', key):
                raise HTTPException(400, 'Idempotency-Key must contain 8–128 letters, digits, dots, colons, underscores or hyphens')
            fingerprint = hashlib.sha256(json.dumps([operation, resource, country]).encode()).hexdigest()
            user_id = user.id
            with redis_lock(f'{user_id}:{operation}:{resource}'):
                # All workers serialize the durable claim, even if Redis expires or fails.
                db.query(User).filter_by(id=user_id).with_for_update().one()
                attempt = db.query(CheckoutAttempt).filter_by(user_id=user_id, operation=operation,
                                                              idempotency_key=key).first()
                if attempt and attempt.request_hash != fingerprint:
                    raise HTTPException(409, 'Idempotency-Key was already used with different checkout parameters')
                if attempt and attempt.status == 'succeeded':
                    return attempt.response
                active = db.query(CheckoutAttempt).filter_by(user_id=user_id, operation=operation,
                    resource=resource).filter(CheckoutAttempt.status.in_(['processing', 'unknown'])).first()
                if active:
                    raise HTTPException(409, 'An existing checkout has an unconfirmed outcome. Check payment status or contact support; do not pay again.',
                                        headers={'Retry-After': '5', 'X-Checkout-Attempt': active.id})
                previous = db.query(CheckoutAttempt).filter_by(user_id=user_id, operation=operation,
                    resource=resource, status='succeeded').order_by(CheckoutAttempt.created_at.desc()).all()
                for pending in previous:
                    if _pending(db, pending):
                        if pending.request_hash != fingerprint:
                            raise HTTPException(409, 'Resume the existing checkout before changing payment region')
                        # Keep every caller's key bound to this response, including across tabs.
                        alias = CheckoutAttempt(user_id=user_id, operation=operation, resource=resource,
                            idempotency_key=key, request_hash=fingerprint, status='succeeded', response=pending.response, request_data=pending.request_data)
                        if attempt:
                            attempt.status, attempt.response = 'succeeded', pending.response
                            attempt.request_data = pending.request_data
                        else:
                            db.add(alias)
                        db.commit()
                        return pending.response
                if attempt is None:
                    attempt = CheckoutAttempt(user_id=user_id, operation=operation, resource=resource,
                        idempotency_key=key, request_hash=fingerprint, status='processing')
                    db.add(attempt)
                else:
                    attempt.status = 'processing'
                db.commit()  # Durable intent survives provider acceptance + process termination.
                attempt_id = attempt.id
                context = {'id': attempt_id, 'remote_started': False}
                token = _current.set(context)
                try:
                    result = fn(*args, **kwargs)
                    attempt = db.get(CheckoutAttempt, attempt_id)
                    attempt.status, attempt.response = 'succeeded', jsonable_encoder(result)
                    db.commit()  # Checkout/subscription and replay response are atomic.
                    return result
                except Exception:
                    db.rollback()
                    attempt = db.get(CheckoutAttempt, attempt_id)
                    attempt.status = 'unknown' if context['remote_started'] else 'failed'
                    db.commit()
                    raise
                finally:
                    _current.reset(token)
        return wrapped
    return decorate
