"""Durable signup quotas, email verification and mail outbox.

Existing accounts are grandfathered without claiming their email was verified.
"""
from collections import Counter
import hashlib
import ipaddress
from alembic import op
import sqlalchemy as sa

revision = 'c03f42b63004'
down_revision = 'b92e31a52003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('email_verification_required', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('users', 'email_verification_required', server_default=sa.true())
    op.create_table('signup_quotas',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('used', sa.Integer(), nullable=False))
    op.create_table('email_challenges',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('email_outbox',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('token_enc', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_email_outbox_user_id', 'email_outbox', ['user_id'])
    op.create_index('ix_email_outbox_status', 'email_outbox', ['status'])
    counts = Counter()
    conn = op.get_bind()
    for ip, device in conn.execute(sa.text('SELECT signup_ip, device_fingerprint FROM users')):
        if ip:
            try:
                parsed = ipaddress.ip_address(ip)
                ip = str(parsed.ipv4_mapped or parsed) if isinstance(parsed, ipaddress.IPv6Address) else str(parsed)
            except ValueError:
                pass
            counts[('ip', ip)] += 1
        if device:
            counts[('device', device)] += 1
    table = sa.table('signup_quotas', sa.column('key'), sa.column('kind'), sa.column('used'))
    if counts:
        op.bulk_insert(table, [{'key': hashlib.sha256(f'{kind}:{value}'.encode()).hexdigest(),
                               'kind': kind, 'used': count} for (kind, value), count in counts.items()])


def downgrade():
    op.drop_table('email_outbox')
    op.drop_table('email_challenges')
    op.drop_table('signup_quotas')
    op.drop_column('users', 'email_verification_required')
    op.drop_column('users', 'email_verified_at')
