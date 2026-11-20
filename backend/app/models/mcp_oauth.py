"""MCP credentials are opaque, hashed, and separate from website sessions."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from backend.app.db.session import Base


class MCPClient(Base):
    __tablename__ = 'mcp_oauth_clients'
    id = Column(String(64), primary_key=True)
    name = Column(String(120), nullable=False)
    redirect_uris = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class MCPAuthorization(Base):
    __tablename__ = 'mcp_oauth_authorizations'
    id = Column(String(64), primary_key=True)  # hash of browser request handle
    client_id = Column(String(64), ForeignKey('mcp_oauth_clients.id'), nullable=False)
    browser_hash = Column(String(64), nullable=False)
    redirect_uri = Column(String(2048), nullable=False)
    state = Column(String(2048), nullable=True)
    challenge = Column(String(43), nullable=False)
    resource = Column(String(2048), nullable=False)
    scope = Column(String(120), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    code_hash = Column(String(64), unique=True, nullable=True)
    code_expires_at = Column(DateTime(timezone=True), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    token_version = Column(Integer, nullable=True)


class MCPGrant(Base):
    __tablename__ = 'mcp_oauth_grants'
    id = Column(String(64), primary_key=True)
    client_id = Column(String(64), ForeignKey('mcp_oauth_clients.id'), nullable=False)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_version = Column(Integer, nullable=False)
    resource = Column(String(2048), nullable=False)
    scope = Column(String(120), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class MCPToken(Base):
    __tablename__ = 'mcp_oauth_tokens'
    access_hash = Column(String(64), primary_key=True)
    refresh_hash = Column(String(64), unique=True, nullable=False)
    grant_id = Column(String(64), ForeignKey('mcp_oauth_grants.id', ondelete='CASCADE'), nullable=False, index=True)
    access_expires_at = Column(DateTime(timezone=True), nullable=False)
    refresh_used_at = Column(DateTime(timezone=True), nullable=True)
