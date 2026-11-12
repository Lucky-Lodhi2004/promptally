import re
import time
from functools import lru_cache, partial
from pydantic import TypeAdapter, EmailStr, ValidationError
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
try:
    from google.oauth2 import id_token
    from google.auth.exceptions import GoogleAuthError, TransportError
    from google.auth.transport import requests as google_requests
    HAS_GOOGLE_AUTH = True
except ImportError:
    GoogleAuthError, TransportError = ValueError, ConnectionError
    id_token = None
    google_requests = None
    HAS_GOOGLE_AUTH = False

from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.enums import UserTier, OAuthProvider
from backend.app.schemas.auth import SignupRequest, LoginRequest, GoogleAuthRequest, TokenResponse, VerifyEmailRequest, GoogleStartRequest
from backend.app.core.config import settings
from backend.app.core.avatars import DEFAULT_AVATAR_URL, avatar_url
from backend.app.core.security import (
    get_password_hash, verify_password, create_access_token, get_session_user, revoke_sessions
)
from backend.app.services.geoip import get_client_ip, detect_country

from backend.app.services.registration import registration_identity, reserve_signup
from backend.app.services.email_verification import create_challenge, kick_delivery, verify_token
from backend.app.core.rate_limit import consume_sync
from backend.app.models.registration import EmailChallenge
from backend.app.services.google_login import (new_challenge, check_browser, consume_challenge, COOKIE as GOOGLE_COOKIE, COOKIE_PATH as GOOGLE_COOKIE_PATH)

router = APIRouter()

def generate_username_from_email(email: str, db: Session) -> str:
    """Auto-generates a clean, unique username from an email address."""
    base = email.split("@")[0].lower()
    clean_base = re.sub(r'[^a-z0-9_]', '', base)[:30] or "user"
    username = clean_base
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{clean_base}{counter}"
        counter += 1
    return username

def set_auth_cookie(response: Response, token: str):
    """Sets a secure HttpOnly cookie for session persistence."""
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=settings.secure_cookies
    )

@router.post("/auth/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    req: SignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Email + password sign-up.
    - Checks device fingerprint (blocks if >= 2 accounts already exist on device).
    - Auto-generates username from email.
    - Assigns default profile picture.
    - Records signup IP & country code.
    """
    # 1. Check if email already registered
    existing_user = db.query(User).filter(User.email == req.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    client_ip, fingerprint = registration_identity(request, req.device_fingerprint)
    reserve_signup(db, client_ip, fingerprint)
    country_code, _ = detect_country(request)

    # 4. Generate unique username
    username = generate_username_from_email(req.email, db)

    # 5. Create User
    new_user = User(
        email=req.email.lower(),
        name=req.name or username,
        username=username,
        avatar_url=DEFAULT_AVATAR_URL,
        password_hash=get_password_hash(req.password),
        tier=UserTier.FREE,
        device_fingerprint=fingerprint,
        signup_ip=client_ip,
        country_code=country_code,
        oauth_provider=OAuthProvider.EMAIL,
        email_verification_required=True,
        payouts_enabled=False,
        seller_payment_config={}
    )
    try:
        db.add(new_user)
        db.flush()
        outbox_id = create_challenge(db, new_user).id
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Account information is already registered. Please sign in or try again.") from None
    kick_delivery(outbox_id)
    db.refresh(new_user)

    token = create_access_token(new_user.id, token_version=new_user.token_version)
    set_auth_cookie(response, token)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": new_user.id,
            "email": new_user.email,
            "username": new_user.username,
            "name": new_user.name,
            "avatar_url": avatar_url(new_user.avatar_url),
            "tier": new_user.tier.value,
            "email_verified": False,
            "email_verification_required": True,
            "country_code": new_user.country_code
        }
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """Email + password login."""
    from backend.app.services.membership import utc
    user = db.query(User).filter(User.email == req.email.lower()).with_for_update().first()
    now = datetime.now(timezone.utc)
    if user and user.login_locked_until and utc(user.login_locked_until) > now:
        raise HTTPException(429, "Too many login attempts. Try again later.", headers={
            'Retry-After': str(max(1, int((utc(user.login_locked_until) - now).total_seconds())))})
    if user and user.login_locked_until:
        user.login_failure_count, user.login_locked_until = 0, None
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        if user:
            user.login_failure_count += 1
            if user.login_failure_count >= settings.LOGIN_MAX_FAILURES:
                user.login_locked_until = now + timedelta(seconds=settings.LOGIN_LOCKOUT_SECONDS)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    user.login_failure_count, user.login_locked_until = 0, None
    db.commit()
    token = create_access_token(user.id, token_version=user.token_version)
    set_auth_cookie(response, token)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "name": user.name,
            "avatar_url": avatar_url(user.avatar_url),
            "tier": user.tier.value,
            "email_verified": bool(user.email_verified_at),
            "email_verification_required": user.email_verification_required,
            "country_code": user.country_code
        }
    )


@lru_cache(maxsize=1)
def google_certificate_request():
    import requests
    from cachecontrol import CacheControl
    # Honor Google's public-key cache headers and bound certificate-fetch latency.
    return partial(google_requests.Request(session=CacheControl(requests.Session())), timeout=5)


def verify_google_credential(credential):
    try:
        info = id_token.verify_oauth2_token(credential, google_certificate_request(), settings.GOOGLE_CLIENT_ID)
    except TransportError:
        raise HTTPException(503, "Google identity verification is temporarily unavailable") from None
    except (ValueError, GoogleAuthError):
        raise HTTPException(400, "Invalid Google credential") from None
    except Exception:
        # Never expose credentials or raw provider errors.
        raise HTTPException(503, "Google identity verification is temporarily unavailable") from None
    if (not isinstance(info, dict) or info.get('iss') not in {'accounts.google.com', 'https://accounts.google.com'}
            or info.get('aud') != settings.GOOGLE_CLIENT_ID
            or not isinstance(info.get('exp'), (int, float)) or info['exp'] <= time.time()
            or not isinstance(info.get('sub'), str) or not 1 <= len(info['sub']) <= 128
            or info.get('email_verified') is not True):
        raise HTTPException(400, "Invalid Google credential")
    try:
        info['email'] = str(TypeAdapter(EmailStr).validate_python(info.get('email'))).lower()
    except (ValidationError, TypeError):
        raise HTTPException(400, "Google token did not contain a valid email") from None
    return info


@router.post("/auth/google/start")
def start_google_login(req: GoogleStartRequest, request: Request, response: Response):
    if not HAS_GOOGLE_AUTH or not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google authentication is not configured")
    return new_challenge(request, response, req.device_fingerprint)


@router.post("/auth/google", response_model=TokenResponse)
def google_auth(req: GoogleAuthRequest, request: Request, response: Response,
                db: Session = Depends(get_db)):
    if not HAS_GOOGLE_AUTH or not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google authentication is not configured")
    binding = check_browser(request, req.csrf_token, req.device_fingerprint)
    info = verify_google_credential(req.credential)
    consume_challenge(info.get('nonce'), binding)
    email, subject = info['email'], info['sub']
    # Google is authoritative for Gmail and Workspace addresses, but not all
    # third-party email addresses attached to a Google account.
    authoritative = email.endswith('@gmail.com') or (isinstance(info.get('hd'), str) and bool(info['hd']))
    user = db.query(User).filter_by(google_sub=subject).with_for_update().first()
    outbox_id = None
    if user is None:
        user = db.query(User).filter_by(email=email).with_for_update().first()
        if user:
            if user.google_sub or not user.email_verified_at or not authoritative:
                raise HTTPException(409, "An account with this email already exists. Sign in with email and password and verify your email before using Google.")
            # Both the local email and Google's authoritative ownership are proven.
            user.google_sub = subject
        else:
            client_ip, fingerprint = registration_identity(request, req.device_fingerprint)
            reserve_signup(db, client_ip, fingerprint)
            country_code, _ = detect_country(request)
            username = generate_username_from_email(email, db)
            picture = info.get('picture')
            user = User(email=email, name=str(info.get('name') or username)[:120], username=username,
                avatar_url=picture if isinstance(picture, str) and picture.startswith('https://') else DEFAULT_AVATAR_URL,
                tier=UserTier.FREE, device_fingerprint=fingerprint, signup_ip=client_ip,
                country_code=country_code, oauth_provider=OAuthProvider.GOOGLE, google_sub=subject,
                email_verification_required=True,
                email_verified_at=datetime.now(timezone.utc) if authoritative else None,
                payouts_enabled=False, seller_payment_config={})
            db.add(user)
            try:
                db.flush()
                if not authoritative:
                    outbox_id = create_challenge(db, user).id
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, "Account information is already registered. Please try signing in again.") from None
    # Stable subject identity takes precedence over a changed Google email. Do
    # not silently replace the user's stored email, password, tier or purchases.
    if authoritative and email == user.email and not user.email_verified_at:
        user.email_verified_at = datetime.now(timezone.utc)
        db.query(EmailChallenge).filter_by(user_id=user.id).delete()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Google account is already connected. Please try signing in again.") from None
    if outbox_id:
        kick_delivery(outbox_id)
    from backend.app.services.membership import refresh_tier
    refresh_tier(user)
    token = create_access_token(user.id, token_version=user.token_version)
    set_auth_cookie(response, token)
    response.delete_cookie(GOOGLE_COOKIE, path=GOOGLE_COOKIE_PATH)
    return TokenResponse(access_token=token, user={
        'id': user.id, 'email': user.email, 'username': user.username, 'name': user.name,
        'avatar_url': avatar_url(user.avatar_url), 'tier': user.tier.value,
        'email_verified': bool(user.email_verified_at),
        'email_verification_required': user.email_verification_required, 'country_code': user.country_code})


@router.post("/auth/logout")
def logout(response: Response, db: Session = Depends(get_db),
           current_user: User = Depends(get_session_user)):
    """Revoke all sessions for this account and clear the browser cookie."""
    revoke_sessions(db, current_user)
    db.commit()
    response.delete_cookie(key="access_token")
    response.delete_cookie(GOOGLE_COOKIE, path=GOOGLE_COOKIE_PATH)
    return {"status": "success", "message": "Logged out successfully."}


@router.post("/auth/verify-email")
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    return verify_token(db, req.token)


@router.post("/auth/resend-verification")
def resend_verification(request: Request, db: Session = Depends(get_db),
                        current_user: User = Depends(get_session_user)):
    user = db.query(User).filter_by(id=current_user.id).with_for_update().one()
    if user.email_verified_at:
        return {"status": "verified", "message": "Your email is already verified."}
    consume_sync(['email-resend:ip:' + get_client_ip(request), 'email-resend:user:' + user.id], 5, 3600)
    outbox_id = create_challenge(db, user).id
    db.commit()
    kick_delivery(outbox_id)
    return {"status": "queued", "message": "Verification email queued. Check your inbox."}
