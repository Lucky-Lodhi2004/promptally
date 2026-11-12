"""Automated seller onboarding and Razorpay OAuth.

Revision ID: a81d92f41002
Revises: f4b91c2d7001
"""
from alembic import op
import sqlalchemy as sa

revision = "a81d92f41002"
down_revision = "f4b91c2d7001"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("razorpay_account_id", sa.String(120), nullable=True),
        sa.Column("razorpay_access_token_enc", sa.Text(), nullable=True),
        sa.Column("razorpay_refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("razorpay_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("razorpay_oauth_environment", sa.String(10), nullable=True),
        sa.Column("razorpay_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dodo_webhook_id", sa.String(120), nullable=True),
        sa.Column("dodo_webhook_url", sa.Text(), nullable=True),
    ):
        op.add_column("seller_gateway_configs", column)
    op.create_index("uq_seller_razorpay_account", "seller_gateway_configs", ["razorpay_account_id"], unique=True)
    op.create_table("seller_oauth_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("seller_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_seller_oauth_states_seller_id", "seller_oauth_states", ["seller_id"])


def downgrade():
    op.drop_table("seller_oauth_states")
    op.drop_index("uq_seller_razorpay_account", table_name="seller_gateway_configs")
    for name in ("dodo_webhook_url", "dodo_webhook_id", "razorpay_revoked_at",
                 "razorpay_oauth_environment", "razorpay_token_expires_at",
                 "razorpay_refresh_token_enc", "razorpay_access_token_enc", "razorpay_account_id"):
        op.drop_column("seller_gateway_configs", name)
