from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
import bcrypt
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.enums import UserTier

# Bearer security schemes: mandatory and optional
bearer_scheme = HTTPBearer(auto_error=True)
optional_bearer_scheme = HTTPBearer(auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Generates a bcrypt password hash."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None, *, token_version: int = 0) -> str:
    """Generates a signed JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
        "ver": token_version,
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[dict]:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

def extract_token_from_request(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = None
) -> Optional[str]:
    """
    Extracts JWT from Authorization header OR fallback to HttpOnly session cookie 'access_token'.
    """
    if auth_header and auth_header.credentials:
        return auth_header.credentials
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        # Strip potential 'Bearer ' prefix in cookie
        if cookie_token.startswith("Bearer "):
            return cookie_token[7:]
        return cookie_token
    return None

def get_session_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency that enforces authentication. Returns current User or raises HTTP 401.
    """
    token = extract_token_from_request(request, auth_header)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user or type(payload.get('ver')) is not int or payload['ver'] != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from backend.app.services.membership import refresh_tier
    refresh_tier(user)
    return user

def get_current_user(current_user: User = Depends(get_session_user)) -> User:
    if current_user.email_verification_required and not current_user.email_verified_at:
        raise HTTPException(403, "Verify your email address before using this feature.")
    return current_user


def get_optional_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency that returns the current User if valid token is provided, or None if anonymous.
    Used for public browse/intent routes to verify seller/buyer ownership without blocking anonymous visitors.
    """
    token = extract_token_from_request(request, auth_header)
    if not token:
        return None
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if not user or type(payload.get('ver')) is not int or payload['ver'] != user.token_version:
        return None
    return user


def revoke_sessions(db: Session, user: User):
    # Atomic increment: concurrent logouts/password changes cannot lose a revoke.
    db.query(User).filter_by(id=user.id).update(
        {User.token_version: User.token_version + 1}, synchronize_session='fetch')

def get_current_active_pro_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Ensures user has an active Pro ($1) subscription or Admin privileges.
    """
    from backend.app.services.membership import is_pro
    if not is_pro(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active $1 Pro subscription required for this feature",
        )
    return current_user

def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Ensures user has Admin privileges.
    """
    if current_user.tier != UserTier.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user

