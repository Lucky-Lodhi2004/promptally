from datetime import datetime, timezone
from backend.app.models.enums import UserTier, SubscriptionStatus


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def is_pro(user):
    if user.tier == UserTier.ADMIN:
        return True
    sub = user.subscription
    return bool(sub and sub.status == SubscriptionStatus.ACTIVE
                and utc(sub.current_period_end) > datetime.now(timezone.utc))


def refresh_tier(user):
    if user.tier != UserTier.ADMIN:
        user.tier = UserTier.PRO if is_pro(user) else UserTier.FREE
