"""Celery mail worker. Start worker AND beat; outbox survives broker outages."""
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from celery import Celery
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models import User
from backend.app.models.registration import EmailChallenge, EmailOutbox
from backend.app.services.crypto import decrypt_secret
from backend.app.services.membership import utc
from backend.app.services.email_verification import cache_challenge

celery_app = Celery('promptally', broker=settings.CELERY_BROKER_URL)
celery_app.conf.update(
    task_ignore_result=True, task_serializer='json', accept_content=['json'],
    task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, broker_connection_retry_on_startup=True,
    broker_connection_timeout=2, broker_transport_options={'socket_connect_timeout': 2, 'socket_timeout': 2},
    beat_schedule={'verification-outbox': {'task': 'promptally.drain_email_outbox', 'schedule': 30.0}},
)


def smtp_send(recipient, token):
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        raise RuntimeError('SMTP is not configured')
    if settings.SMTP_SECURITY not in {'starttls', 'ssl'}:
        raise RuntimeError('SMTP requires TLS')
    # Token fragment stays out of HTTP access logs and Referer headers.
    link = settings.SITE_URL.rstrip('/') + '/verify-email#token=' + token
    message = EmailMessage()
    message['From'] = settings.EMAIL_FROM
    message['To'] = recipient
    message['Subject'] = 'Verify your Promptally email address'
    message.set_content('Welcome to Promptally!\n\nVerify your email address:\n' + link +
        f'\n\nThis link expires in {settings.EMAIL_TOKEN_TTL_SECONDS // 60} minutes and can be used once.\n'
        'If you did not create this account, you can ignore this email.')
    context = ssl.create_default_context()
    smtp = smtplib.SMTP_SSL if settings.SMTP_SECURITY == 'ssl' else smtplib.SMTP
    kwargs = {'context': context} if settings.SMTP_SECURITY == 'ssl' else {}
    with smtp(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15, **kwargs) as client:
        if settings.SMTP_SECURITY == 'starttls':
            client.ehlo(); client.starttls(context=context); client.ehlo()
        client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        client.send_message(message)


def deliver_outbox(db, outbox_id):
    identity = db.query(EmailOutbox.user_id).filter_by(id=outbox_id).scalar()
    if not identity:
        return
    user = db.query(User).filter_by(id=identity).with_for_update().first()
    row = db.query(EmailOutbox).filter_by(id=outbox_id).with_for_update().first()
    if not user or not row or row.status != 'pending':
        return
    now = datetime.now(timezone.utc)
    if utc(row.next_attempt_at) > now:
        return
    challenge = db.get(EmailChallenge, user.id)
    if (user.email_verified_at or not challenge or challenge.token_hash != row.token_hash
            or utc(challenge.expires_at) <= now):
        row.status, row.token_enc = 'canceled', ''
        db.commit()
        return
    row.attempts += 1
    try:
        token = decrypt_secret(row.token_enc)
        cache_challenge(challenge)
        smtp_send(user.email, token)
    except Exception:
        # Do not log SMTP exception text: it can contain credentials or content.
        row.next_attempt_at = now + timedelta(seconds=min(300, 15 * 2 ** min(row.attempts, 5)))
        db.commit()
        return
    row.status, row.sent_at, row.token_enc = 'sent', now, ''
    db.commit()


@celery_app.task(name='promptally.send_verification_email')
def send_verification_email(outbox_id):
    with SessionLocal() as db:
        deliver_outbox(db, outbox_id)


@celery_app.task(name='promptally.drain_email_outbox')
def drain_email_outbox():
    with SessionLocal() as db:
        ids = [row[0] for row in db.query(EmailOutbox.id).filter_by(status='pending').filter(
            EmailOutbox.next_attempt_at <= datetime.now(timezone.utc)).order_by(EmailOutbox.created_at).limit(100).all()]
    for outbox_id in ids:
        send_verification_email.apply_async(args=[outbox_id], retry=False)
