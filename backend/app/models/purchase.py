import uuid
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    ForeignKey, Enum as SQLEnum, UniqueConstraint, func
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base
from backend.app.models.enums import SubscriptionStatus, SubscriptionGateway, PurchaseStatus

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Multi-Gateway Support (Razorpay for Indian IPs, Dodo for Foreign IPs)
    gateway = Column(SQLEnum(SubscriptionGateway), default=SubscriptionGateway.DODO, nullable=False)
    gateway_subscription_id = Column(String(120), unique=True, nullable=True)
    gateway_plan_id = Column(String(120), nullable=True)
    currency = Column(String(10), default="USD", nullable=False)
    expected_amount_minor = Column(Integer, default=100, nullable=False)
    checkout_reference = Column(String(36), nullable=True)
    checkout_session_id = Column(String(120), unique=True, nullable=True)
    checkout_url = Column(String(1000), nullable=True)
    provider_customer_id = Column(String(120), nullable=True)
    last_event_at = Column(DateTime(timezone=True), nullable=True)
    
    # Legacy fields (nullable)
    stripe_subscription_id = Column(String(120), unique=True, nullable=True)
    stripe_price_id = Column(String(120), nullable=True)
    
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.PENDING, nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="subscription")

class AssetPurchase(Base):
    __tablename__ = "asset_purchases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    buyer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True)
    seller_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    amount_cents = Column(Integer, nullable=False)
    # Direct seller payouts: 100% to seller, $0 platform fee
    platform_fee_cents = Column(Integer, default=0, nullable=False)
    seller_payout_cents = Column(Integer, nullable=False)
    
    provider = Column(String(40), default="legacy", nullable=False)
    provider_payment_id = Column(String(120), unique=True, nullable=True)
    currency = Column(String(10), default="USD", nullable=False)
    payment_reference = Column(String(120), unique=True, nullable=True)
    stripe_payment_intent_id = Column(String(120), unique=True, nullable=True)
    status = Column(SQLEnum(PurchaseStatus), default=PurchaseStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="purchases")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="sales")
    asset = relationship("Asset", back_populates="purchases")

    __table_args__ = (
        UniqueConstraint("buyer_id", "asset_id", name="uq_buyer_asset"),
    )
