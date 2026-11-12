"""Verified platform billing and BYOG checkout state.

Revision ID: f4b91c2d7001
Revises: e3f2f2494e54
"""
from alembic import op
import sqlalchemy as sa

revision = 'f4b91c2d7001'
down_revision = 'e3f2f2494e54'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL enum additions must commit before their first use.
    if op.get_bind().dialect.name == 'postgresql':
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE subscriptiongateway ADD VALUE IF NOT EXISTS 'DODO'")
            op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'PENDING'")
    op.add_column('subscriptions', sa.Column('expected_amount_minor', sa.Integer(), nullable=False, server_default='100'))
    op.add_column('subscriptions', sa.Column('checkout_reference', sa.String(36), nullable=True))
    op.add_column('subscriptions', sa.Column('checkout_session_id', sa.String(120), nullable=True))
    op.add_column('subscriptions', sa.Column('checkout_url', sa.String(1000), nullable=True))
    op.add_column('subscriptions', sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table('subscriptions') as batch:
        batch.create_unique_constraint('uq_subscription_checkout_session', ['checkout_session_id'])
    with op.batch_alter_table('webhook_events') as batch:
        batch.alter_column('provider', existing_type=sa.String(40), type_=sa.String(100), nullable=False)
    # Old implementation generated these locally and granted Pro before payment.
    op.execute("UPDATE subscriptions SET status='CANCELED' WHERE gateway_subscription_id LIKE 'sub_rzp_%' OR gateway_subscription_id LIKE 'sub_pad_%'")
    op.execute("UPDATE users SET tier='FREE' WHERE tier='PRO' AND id IN (SELECT user_id FROM subscriptions WHERE status='CANCELED')")
    # Old purchase rows were marked complete without a provider confirmation.
    # Preserve the rows for audit, but require a verified payment to unlock them.
    op.execute("UPDATE asset_purchases SET status='PENDING' WHERE provider='legacy' AND provider_payment_id IS NULL")


def downgrade():
    with op.batch_alter_table('webhook_events') as batch:
        batch.alter_column('provider', existing_type=sa.String(100), type_=sa.String(40), nullable=False)
    with op.batch_alter_table('subscriptions') as batch:
        batch.drop_constraint('uq_subscription_checkout_session', type_='unique')
        for name in ('last_event_at', 'checkout_url', 'checkout_session_id', 'checkout_reference', 'expected_amount_minor'):
            batch.drop_column(name)
    # Do not restore unverified entitlements or remove enum values in use.
