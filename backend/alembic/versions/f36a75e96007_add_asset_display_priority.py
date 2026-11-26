"""Add display_priority to assets for admin catalog curation and pinning."""
from alembic import op
import sqlalchemy as sa

revision = "f36a75e96007"
down_revision = "e25f64d85006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "assets",
        sa.Column("display_priority", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_assets_display_priority", "assets", ["display_priority"])
    op.create_index("idx_assets_priority", "assets", ["is_published", "display_priority"])


def downgrade():
    op.drop_index("idx_assets_priority", table_name="assets")
    op.drop_index("ix_assets_display_priority", table_name="assets")
    op.drop_column("assets", "display_priority")

