"""Verification challenges and outbox are committed with account creation.

Redis caches token hashes only; PostgreSQL atomically consumes the challenge and
marks the account verified. A Redis restart cannot resurrect a consumed link.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from redis import Redis
from backend.app.core.config import settings
from backend.app.models.registration import EmailChallenge, EmailOutbox
from backend.app.models.user import User
from backend.app.services.crypto import encrypt_secret
from backend.app.services.membership import utc

log = logging.getLogger(__name__)


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_challenge(db, user):
    now = datetime.now(timezone.utc)
    challenge = db.get(EmailChallenge, user.id)
    if challenge and utc(challenge.created_at) + timedelta(seconds=settings.EMAIL_RESEND_COOLDOWN_SECONDS) > now:
        retry = max(1, int((utc(challenge.created_at) + timedelta(seconds=settings.EMAIL_RESEND_COOLDOWN_SECONDS) - now).total_seconds()))
        raise HTTPException(429, 'Please wait before requesting another verification email.', headers={'Retry-After': str(retry)})
    token = secrets.token_urlsafe(32)
    digest = token_digest(token)
    if challenge is None:
        challenge = EmailChallenge(user_id=user.id)
        db.add(challenge)
    challenge.token_hash = digest
    challenge.created_at = now
    challenge.expires_at = now + timedelta(seconds=settings.EMAIL_TOKEN_TTL_SECONDS)
    # Cancel superseded unsent emails; retries must not send an invalidated link.
    db.query(EmailOutbox).filter_by(user_id=user.id, status='pending').update({'status': 'canceled', 'token_enc': ''})
    outbox = EmailOutbox(user_id=user.id, token_hash=digest, token_enc=encrypt_secret(token),
                        next_attempt_at=now, status='pending')
    db.add(outbox)
    db.flush()
    return outbox


def kick_delivery(outbox_id):
    # Never roll back a successful signup because the broker is unavailable.
    # Celery beat periodically re-enqueues durable pending outbox rows.
    try:
        from backend.app.worker import send_verification_email
        send_verification_email.apply_async(args=[outbox_id], retry=False)
    except Exception:
        log.warning('Verification email remains queued in the durable outbox')


def cache_challenge(challenge):
    if not settings.REDIS_URL:
        return
    try:
        ttl = max(1, int((utc(challenge.expires_at) - datetime.now(timezone.utc)).total_seconds()))
        with Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1) as client:
            client.set('promptally:verify:' + challenge.token_hash, challenge.user_id, ex=ttl)
    except Exception:
        pass  # Durable hash remains valid; no raw token is cached.


def verify_token(db, token):
    if not isinstance(token, str) or len(token) < 32 or len(token) > 128:
        raise HTTPException(400, 'Verification link is invalid or expired. Request a new email.')
    digest = token_digest(token)
    # Read identity first, then lock user before challenge/outbox, matching resend
    # and worker lock order. Recheck the digest after acquiring the locks.
    identity = None
    try:
        if settings.REDIS_URL:
            with Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1) as client:
                cached = client.get('promptally:verify:' + digest)
                identity = cached.decode() if cached else None
    except Exception:
        pass
    if not identity:
        identity = db.query(EmailChallenge.user_id).filter_by(token_hash=digest).scalar()
    if not identity:
        raise HTTPException(400, 'Verification link is invalid or expired. Request a new email.')
    user = db.query(User).filter_by(id=identity).with_for_update().first()
    if not user:
        raise HTTPException(400, 'Verification link is invalid or expired. Request a new email.')
    challenge = db.query(EmailChallenge).filter_by(user_id=identity, token_hash=digest).with_for_update().first()
    if not challenge or utc(challenge.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(400, 'Verification link is invalid or expired. Request a new email.')
    user.email_verified_at = datetime.now(timezone.utc)
    db.delete(challenge)
    db.query(EmailOutbox).filter_by(user_id=user.id, status='pending').update({'status': 'canceled', 'token_enc': ''})
    db.commit()
    try:
        if settings.REDIS_URL:
            with Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1) as client:
                client.delete('promptally:verify:' + digest)
    except Exception:
        pass
    return {'status': 'verified', 'message': 'Your email address is verified.'}
