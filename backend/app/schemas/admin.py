from typing import List, Optional
from pydantic import BaseModel

class AdminUserCard(BaseModel):
    id: str
    email: str
    username: str
    name: str
    tier: str
    signup_ip: Optional[str] = None
    country_code: str
    device_fingerprint: Optional[str] = None
    created_at: Optional[str] = None
    subscription_gateway: Optional[str] = None
    subscription_status: Optional[str] = None

class AdminUsersResponse(BaseModel):
    total_signed_up: int
    total_subscribed: int
    razorpay_subscribers: int
    dodo_subscribers: int
    users: List[AdminUserCard]

