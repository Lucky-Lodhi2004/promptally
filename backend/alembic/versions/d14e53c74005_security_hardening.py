"""Revocable sessions, account login lockout, and retained sold artifacts."""
from alembic import op
import sqlalchemy as sa

revision = 'd14e53c74005'
down_revision = 'c03f42b63004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('login_failure_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('login_locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assets', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    for fk in sa.inspect(op.get_bind()).get_foreign_keys('asset_purchases'):
        if fk['constrained_columns'] == ['asset_id']:
            with op.batch_alter_table('asset_purchases', naming_convention={
                    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s'}) as batch:
                batch.drop_constraint(fk['name'] or 'fk_asset_purchases_asset_id_assets', type_='foreignkey')
                batch.create_foreign_key('fk_asset_purchases_asset_id_assets', 'assets', ['asset_id'], ['id'], ondelete='RESTRICT')


def downgrade():
    # Restoring cascading deletion would permit destroying financial records.
    raise RuntimeError('Security migration requires a reviewed manual rollback')
