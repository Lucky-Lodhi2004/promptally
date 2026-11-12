import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Enum as SQLEnum, JSON, func, true
from sqlalchemy.orm import relationship
from backend.app.db.session import Base
from backend.app.models.enums import UserTier, OAuthProvider
from backend.app.core.avatars import DEFAULT_AVATAR_URL

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    username = Column(String(60), unique=True, index=True, nullable=False)
    avatar_url = Column(String(500), nullable=True, default=DEFAULT_AVATAR_URL)
    password_hash = Column(String(255), nullable=True)
    token_version = Column(Integer, nullable=False, default=0, server_default='0')
    login_failure_count = Column(Integer, nullable=False, default=0, server_default='0')
    login_locked_until = Column(DateTime(timezone=True), nullable=True)
    tier = Column(SQLEnum(UserTier), default=UserTier.FREE, nullable=False)
    
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    email_verification_required = Column(Boolean, default=True, server_default=true(), nullable=False)

    # Device fingerprint to enforce max 2 accounts per device
    device_fingerprint = Column(String(128), index=True, nullable=True)
    signup_ip = Column(String(64), nullable=True)
    country_code = Column(String(10), default="US", nullable=False)
    
    # Authentication method
    oauth_provider = Column(SQLEnum(OAuthProvider), default=OAuthProvider.EMAIL, nullable=False)
    google_sub = Column(String(128), unique=True, index=True, nullable=True)
    
    # Direct Seller Payout configuration (100% direct buyer-to-seller payment)
    payouts_enabled = Column(Boolean, default=False, nullable=False)
    seller_payment_config = Column(JSON, default=dict, nullable=False)
    
    # Legacy Stripe references (preserved if needed)
    stripe_customer_id = Column(String(120), unique=True, nullable=True)
    stripe_connect_id = Column(String(120), unique=True, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    assets = relationship("Asset", back_populates="author", cascade="all, delete-orphan")
    collections = relationship("Collection", back_populates="owner", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    purchases = relationship("AssetPurchase", foreign_keys="[AssetPurchase.buyer_id]", back_populates="buyer")
    sales = relationship("AssetPurchase", foreign_keys="[AssetPurchase.seller_id]", back_populates="seller")

    gateway_config = relationship("SellerGatewayConfig", back_populates="seller", uselist=False, cascade="all, delete-orphan")
