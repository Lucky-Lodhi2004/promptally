"""Dedicated MCP OAuth clients, authorizations, grants and hashed tokens."""
from alembic import op
from backend.app.models.mcp_oauth import MCPClient, MCPAuthorization, MCPGrant, MCPToken

revision = 'e25f64d85006'
down_revision = 'd14e53c74005'
branch_labels = None
depends_on = None


def upgrade():
    for model in (MCPClient, MCPAuthorization, MCPGrant, MCPToken):
        model.__table__.create(op.get_bind())


def downgrade():
    for model in (MCPToken, MCPGrant, MCPAuthorization, MCPClient):
        model.__table__.drop(op.get_bind())
