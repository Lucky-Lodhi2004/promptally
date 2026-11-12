from typing import Literal, Optional
from pydantic import BaseModel, SecretStr, Field, model_validator


class SubscribeResponse(BaseModel):
    gateway: Literal["razorpay", "dodo"]
    currency: str
    amount: int  # Always minor units: paise for INR, cents for USD.
    country_code: str
    subscription_id: Optional[str] = None
    checkout_url: Optional[str] = None
    key_id: Optional[str] = None
    checkout_session_id: Optional[str] = None
    status: str = "pending"


class CancelSubscriptionResponse(BaseModel):
    status: str
    message: str


class SellerConnectRequest(BaseModel):
    gateway_type: Literal["razorpay", "dodo"]
    key_id: Optional[str] = Field(None, max_length=64)
    key_secret: Optional[SecretStr] = Field(None, max_length=256)
    api_key: Optional[SecretStr] = Field(None, max_length=512)
    webhook_secret: Optional[SecretStr] = Field(None, max_length=256)
    environment: Literal["test", "live"] = "live"

    @model_validator(mode="after")
    def credentials_present(self):
        if self.gateway_type == "razorpay" and (not self.webhook_secret or not self.webhook_secret.get_secret_value()):
            raise ValueError("Webhook signing secret is required for manual Razorpay connections")
        if self.gateway_type == "razorpay" and (not self.key_id or not self.key_secret or not self.key_secret.get_secret_value()):
            raise ValueError("Razorpay key_id and key_secret are required")
        if self.gateway_type == "dodo" and (not self.api_key or not self.api_key.get_secret_value()):
            raise ValueError("Dodo api_key is required")
        return self


class VerifyPurchaseRequest(BaseModel):
    payment_reference: str = Field(min_length=1, max_length=120)
    payment_id: Optional[str] = Field(None, pattern=r"^pay_[A-Za-z0-9]+$", max_length=120)
    signature: Optional[str] = Field(None, pattern=r"^[a-fA-F0-9]{64}$")


class DirectBuyResponse(BaseModel):
    gateway: Optional[str] = None
    payment_reference: str
    checkout_url: Optional[str] = None
    seller_username: str
    amount_usd: float
    amount: int
    currency: str
    key_id: Optional[str] = None
    order_id: Optional[str] = None
    status: str = "pending"
