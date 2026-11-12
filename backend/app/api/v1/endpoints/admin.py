from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.purchase import Subscription
from backend.app.models.enums import UserTier, SubscriptionStatus, SubscriptionGateway
from backend.app.schemas.admin import AdminUsersResponse, AdminUserCard
from backend.app.core.security import get_current_admin_user

router = APIRouter()

@router.get("/admin/users", response_model=AdminUsersResponse)
def get_admin_users(
    status: Optional[str] = Query("all", description="'all' or 'subscribed'"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    Admin-only endpoint:
    - Lists signed-up users and active $1 subscribers.
    - Returns user counts, emails, usernames, signup dates, signup IP, country code, device fingerprint, and gateway (Razorpay vs Dodo).
    """
    total_signed_up = db.query(func.count(User.id)).scalar() or 0

    total_subscribed = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
        .scalar() or 0
    )

    razorpay_subscribers = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.gateway == SubscriptionGateway.RAZORPAY
        )
        .scalar() or 0
    )

    dodo_subscribers = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.gateway == SubscriptionGateway.DODO
        )
        .scalar() or 0
    )

    query = db.query(User)
    if status == "subscribed":
        query = query.join(Subscription, Subscription.user_id == User.id).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        )

    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    user_cards = []
    for u in users:
        sub_gateway = None
        sub_status = None
        if u.subscription:
            sub_gateway = u.subscription.gateway.value if hasattr(u.subscription.gateway, "value") else str(u.subscription.gateway)
            sub_status = u.subscription.status.value if hasattr(u.subscription.status, "value") else str(u.subscription.status)

        user_cards.append(
            AdminUserCard(
                id=u.id,
                email=u.email,
                username=u.username,
                name=u.name,
                tier=u.tier.value if hasattr(u.tier, "value") else str(u.tier),
                signup_ip=u.signup_ip,
                country_code=u.country_code or "US",
                device_fingerprint=u.device_fingerprint,
                created_at=u.created_at.isoformat() if u.created_at else None,
                subscription_gateway=sub_gateway,
                subscription_status=sub_status
            )
        )

    return AdminUsersResponse(
        total_signed_up=total_signed_up,
        total_subscribed=total_subscribed,
        razorpay_subscribers=razorpay_subscribers,
        dodo_subscribers=dodo_subscribers,
        users=user_cards
    )

