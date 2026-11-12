from typing import Optional, Dict, Any
from pydantic import BaseModel

class UserProfileResponse(BaseModel):
    id: str
    email: str
    username: str
    name: str
    avatar_url: Optional[str] = None
    tier: str
    email_verified: bool = False
    email_verification_required: bool = True
    country_code: str
    payouts_enabled: bool
    seller_payment_config: Dict[str, Any] = {}
    subscription: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

