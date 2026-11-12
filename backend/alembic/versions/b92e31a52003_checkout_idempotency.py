"""Durable checkout idempotency; existing webhook ledger remains authoritative.

Revision ID: b92e31a52003
Revises: a81d92f41002
"""
from alembic import op
import sqlalchemy as sa

revision = 'b92e31a52003'
down_revision = 'a81d92f41002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('checkout_attempts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operation', sa.String(32), nullable=False),
        sa.Column('resource', sa.String(500), nullable=False),
        sa.Column('idempotency_key', sa.String(128), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('request_data', sa.JSON(), nullable=True),
        sa.Column('response', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'operation', 'idempotency_key', name='uq_checkout_attempt_key'))
    op.create_index('uq_checkout_attempt_inflight', 'checkout_attempts', ['user_id', 'operation', 'resource'],
        unique=True, postgresql_where=sa.text("status IN ('processing', 'unknown')"),
        sqlite_where=sa.text("status IN ('processing', 'unknown')"))


def downgrade():
    op.drop_table('checkout_attempts')
