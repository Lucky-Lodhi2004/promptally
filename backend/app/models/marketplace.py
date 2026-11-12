import uuid
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, Enum as SQLEnum,
    UniqueConstraint, Index, JSON, text, func
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base
from backend.app.models.enums import SellerGateway, CheckoutStatus


class SellerGatewayConfig(Base):
    """
    Bring-Your-Own-Gateway credentials for a seller.
    Buyers pay the seller's own Razorpay / Dodo account directly.
    All *_enc columns are Fernet-encrypted and are never returned by any API.
    """
    __tablename__ = "seller_gateway_configs"

    seller_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    # Seller's Razorpay (Indian buyers, INR)
    razorpay_key_id = Column(String(64), nullable=True)
    razorpay_key_secret_enc = Column(String(512), nullable=True)
    razorpay_webhook_secret_enc = Column(String(512), nullable=True)
    razorpay_verified_at = Column(DateTime(timezone=True), nullable=True)
    razorpay_last_webhook_at = Column(DateTime(timezone=True), nullable=True)
    razorpay_account_id = Column(String(120), unique=True, nullable=True)
    razorpay_access_token_enc = Column(Text, nullable=True)
    razorpay_refresh_token_enc = Column(Text, nullable=True)
    razorpay_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    razorpay_oauth_environment = Column(String(10), nullable=True)
    razorpay_revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Seller's Dodo Payments (foreign buyers, USD)
    dodo_api_key_enc = Column(String(1024), nullable=True)
    dodo_webhook_secret_enc = Column(String(512), nullable=True)
    dodo_environment = Column(String(10), default="live", nullable=False)  # 'test' or 'live'
    dodo_verified_at = Column(DateTime(timezone=True), nullable=True)
    dodo_last_webhook_at = Column(DateTime(timezone=True), nullable=True)
    dodo_webhook_id = Column(String(120), nullable=True)
    dodo_webhook_url = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller = relationship("User", back_populates="gateway_config")

    @property
    def has_razorpay(self) -> bool:
        if self.razorpay_account_id:
            return bool(self.razorpay_key_id and self.razorpay_access_token_enc
                        and self.razorpay_refresh_token_enc and self.razorpay_verified_at
                        and not self.razorpay_revoked_at)
        return bool(self.razorpay_key_id and self.razorpay_key_secret_enc
                    and self.razorpay_webhook_secret_enc and self.razorpay_verified_at)

    @property
    def has_dodo(self) -> bool:
        return bool(self.dodo_api_key_enc and self.dodo_webhook_secret_enc and self.dodo_verified_at)


class SellerOAuthState(Base):
    __tablename__ = "seller_oauth_states"

    state_hash = Column(String(64), primary_key=True)
    seller_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    environment = Column(String(10), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)


class PendingCheckout(Base):
    """
    Server-side record of every prompt checkout we start on a seller's gateway.
    Webhooks are matched against this row (provider_order_id + expected amount),
    so we never trust webhook notes/metadata alone.
    """
    __tablename__ = "pending_checkouts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    buyer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    gateway = Column(SQLEnum(SellerGateway), nullable=False)
    # Razorpay order_id or Dodo checkout session_id
    provider_order_id = Column(String(120), unique=True, nullable=False, index=True)
    expected_amount_minor = Column(Integer, nullable=False)  # paise or cents
    currency = Column(String(10), nullable=False)
    status = Column(SQLEnum(CheckoutStatus), default=CheckoutStatus.PENDING, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class WebhookEvent(Base):
    """Idempotency log: gateways retry webhooks, each event is processed once."""
    __tablename__ = "webhook_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(100), nullable=False)
    event_id = Column(String(200), nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),
    )



class CheckoutAttempt(Base):
    __tablename__ = "checkout_attempts"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    operation = Column(String(32), nullable=False)
    resource = Column(String(500), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    request_data = Column(JSON, nullable=True)
    response = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("user_id", "operation", "idempotency_key", name="uq_checkout_attempt_key"),
        Index("uq_checkout_attempt_inflight", "user_id", "operation", "resource", unique=True,
              postgresql_where=text("status IN ('processing', 'unknown')"),
              sqlite_where=text("status IN ('processing', 'unknown')")),
    )
