"""Persist rate-limit retry eligibility for pinned PR reviews."""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pr_reviews", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("pr_reviews", "next_retry_at")
