import re
from typing import Optional
from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File,
    Form, Response, status
)
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.purchase import Subscription
from backend.app.schemas.user import UserProfileResponse, PasswordChangeRequest
from backend.app.core.security import (
    get_current_user, get_session_user, verify_password, get_password_hash,
    revoke_sessions, create_access_token
)
from backend.app.services.storage import save_avatar_file
from backend.app.core.avatars import avatar_url
from backend.app.core.upload_routes import BoundedFormRoute

router = APIRouter(route_class=BoundedFormRoute)

@router.get("/users/me", response_model=UserProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_session_user),
    db: Session = Depends(get_db)
):
    """Fetches current logged-in user details."""
    sub_data = None
    if current_user.subscription:
        sub: Subscription = current_user.subscription
        sub_data = {
            "id": sub.id,
            "gateway": sub.gateway.value if hasattr(sub.gateway, "value") else str(sub.gateway),
            "status": sub.status.value if hasattr(sub.status, "value") else str(sub.status),
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "currency": sub.currency
        }

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        name=current_user.name,
        avatar_url=avatar_url(current_user.avatar_url),
        tier=current_user.tier.value if hasattr(current_user.tier, "value") else str(current_user.tier),
        country_code=current_user.country_code or "US",
        payouts_enabled=current_user.payouts_enabled,
        seller_payment_config=current_user.seller_payment_config or {},
        email_verified=bool(current_user.email_verified_at),
        email_verification_required=current_user.email_verification_required,
        subscription=sub_data
    )


@router.patch("/users/me", response_model=UserProfileResponse)
async def update_my_profile(
    username: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates username, display name, and/or profile picture.
    Enforces username format and uniqueness.
    """
    # 1. Update username
    if username and username.strip():
        new_username = re.sub(r'[^a-z0-9_]', '', username.strip().lower())
        if len(new_username) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username must be at least 3 alphanumeric characters."
            )
        if new_username != current_user.username:
            existing = db.query(User).filter(User.username == new_username).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This username is already taken."
                )
            current_user.username = new_username

    # 2. Update name
    if name and name.strip():
        current_user.name = name.strip()

    # 3. Update avatar
    if avatar and avatar.filename:
        avatar_url = await save_avatar_file(avatar)
        current_user.avatar_url = avatar_url

    db.commit()
    db.refresh(current_user)

    return get_my_profile(current_user=current_user, db=db)


@router.post("/users/me/password")
def change_password(
    req: PasswordChangeRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Changes user password (requires current password validation)."""
    current_user = db.query(User).filter_by(id=current_user.id).with_for_update().one()
    if current_user.password_hash:
        if not verify_password(req.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password."
            )

    if len(req.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters."
        )

    current_user.password_hash = get_password_hash(req.new_password)
    revoke_sessions(db, current_user)
    db.commit()
    from backend.app.api.v1.endpoints.auth import set_auth_cookie
    set_auth_cookie(response, create_access_token(current_user.id, token_version=current_user.token_version))

    return {"status": "success", "message": "Password changed successfully."}

