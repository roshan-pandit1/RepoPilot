"""Add worker claim leases without changing existing data."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("index_jobs", sa.Column("lease_token", sa.String(36), nullable=True))
    op.add_column("index_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("index_jobs", "lease_expires_at")
    op.drop_column("index_jobs", "lease_token")
