"""Durable signup quotas, one-use email challenges and transactional mail outbox."""
import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func
from backend.app.db.session import Base


class SignupQuota(Base):
    __tablename__ = 'signup_quotas'
    key = Column(String(64), primary_key=True)
    kind = Column(String(16), nullable=False)
    used = Column(Integer, nullable=False, default=0)


class EmailChallenge(Base):
    __tablename__ = 'email_challenges'
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class EmailOutbox(Base):
    __tablename__ = 'email_outbox'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    token_enc = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default='pending', index=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
