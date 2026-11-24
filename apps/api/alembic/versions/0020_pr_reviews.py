"""Create tenant-bound read-only pull request review records."""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("pr_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False), sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("session_hash", sa.String(64), sa.ForeignKey("auth_sessions.id_hash"), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False), sa.Column("number", sa.Integer(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("lease_token", sa.String(36)), sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("github_pr_id", sa.BigInteger()), sa.Column("title", sa.String(1024)), sa.Column("author", sa.String(100)), sa.Column("base_sha", sa.String(40)), sa.Column("head_sha", sa.String(40)),
        sa.Column("coverage", sa.String(20)), sa.Column("files", sa.JSON()), sa.Column("limitations", sa.JSON()), sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(80)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id", "tenant_id"], ["repositories.id", "repositories.tenant_id"]),
        sa.UniqueConstraint("id", "repository_id", "tenant_id", name="uq_pr_review_owner"), sa.UniqueConstraint("repository_id", "user_id", "request_key", name="uq_pr_review_request"),
        sa.CheckConstraint("number > 0 AND attempts >= 0 AND status IN ('queued','running','completed','failed','stale')", name="ck_pr_review_state"),
        sa.CheckConstraint("coverage IS NULL OR coverage IN ('complete','partial')", name="ck_pr_review_coverage"))
    op.create_table("pr_review_outbox",
        sa.Column("review_id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.BigInteger(), nullable=False), sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["review_id", "repository_id", "tenant_id"], ["pr_reviews.id", "pr_reviews.repository_id", "pr_reviews.tenant_id"], name="fk_pr_outbox_owner"),
        sa.CheckConstraint("status IN ('pending','processed','failed') AND attempts >= 0", name="ck_pr_outbox_state"))
    op.create_index("ix_pr_outbox_dispatch", "pr_review_outbox", ["status", "next_dispatch_at"])
    op.create_table("pr_review_findings",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("review_id", sa.String(36), nullable=False), sa.Column("repository_id", sa.BigInteger(), nullable=False), sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False), sa.Column("rule_id", sa.String(80), nullable=False), sa.Column("category", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False), sa.Column("confidence", sa.String(20), nullable=False), sa.Column("path", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False), sa.Column("end_line", sa.Integer(), nullable=False), sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False), sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["review_id", "repository_id", "tenant_id"], ["pr_reviews.id", "pr_reviews.repository_id", "pr_reviews.tenant_id"], name="fk_pr_finding_owner"),
        sa.UniqueConstraint("id", "review_id", "repository_id", "tenant_id", name="uq_pr_finding_owner"), sa.UniqueConstraint("review_id", "fingerprint", name="uq_pr_finding_fingerprint"),
        sa.CheckConstraint("start_line > 0 AND end_line >= start_line", name="ck_pr_finding_lines"),
        sa.CheckConstraint("severity IN ('CRITICAL','HIGH','MEDIUM','LOW','INFORMATIONAL')", name="ck_pr_finding_severity"),
        sa.CheckConstraint("category IN ('BUG','SECURITY','PERFORMANCE','RELIABILITY','MAINTAINABILITY','TEST_COVERAGE')", name="ck_pr_finding_category"),
        sa.CheckConstraint("confidence IN ('HIGH','MEDIUM','LOW')", name="ck_pr_finding_confidence"))
    op.create_table("pr_finding_feedback",
        sa.Column("finding_id", sa.String(36), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("review_id", sa.String(36), nullable=False), sa.Column("repository_id", sa.BigInteger(), nullable=False), sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False), sa.Column("reason", sa.String(500)), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["finding_id", "review_id", "repository_id", "tenant_id"], ["pr_review_findings.id", "pr_review_findings.review_id", "pr_review_findings.repository_id", "pr_review_findings.tenant_id"], name="fk_pr_feedback_finding_owner"),
        sa.CheckConstraint("state IN ('useful','false_positive','acknowledged')", name="ck_pr_feedback_state"))


def downgrade():
    op.drop_table("pr_finding_feedback")
    op.drop_table("pr_review_findings")
    op.drop_index("ix_pr_outbox_dispatch", table_name="pr_review_outbox")
    op.drop_table("pr_review_outbox")
    op.drop_table("pr_reviews")
