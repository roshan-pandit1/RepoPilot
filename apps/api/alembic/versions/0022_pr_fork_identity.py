"""Persist the independently pinned PR head repository identity."""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pr_reviews", sa.Column("head_repository_id", sa.BigInteger(), nullable=True))
    op.add_column("pr_reviews", sa.Column("head_repository_name", sa.String(250), nullable=True))
    with op.batch_alter_table("pr_reviews") as batch:
        batch.create_check_constraint("ck_pr_review_head_repository", "(head_repository_id IS NULL AND head_repository_name IS NULL) OR (head_repository_id IS NOT NULL AND head_repository_id > 0 AND head_repository_name IS NOT NULL)")


def downgrade():
    with op.batch_alter_table("pr_reviews") as batch:
        batch.drop_constraint("ck_pr_review_head_repository", type_="check")
    op.drop_column("pr_reviews", "head_repository_name")
    op.drop_column("pr_reviews", "head_repository_id")
