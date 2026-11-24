"""Persist evidence-bound patch proposals and their transactional outbox."""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("patch_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_hash", sa.String(64), sa.ForeignKey("auth_sessions.id_hash"), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("provider", sa.String(40)), sa.Column("model", sa.String(100)),
        sa.Column("diff", sa.Text()), sa.Column("rationale", sa.Text()),
        sa.Column("evidence", sa.JSON()), sa.Column("changed_files", sa.JSON()),
        sa.Column("static_result", sa.JSON()), sa.Column("test_result", sa.JSON()),
        sa.Column("review_state", sa.String(24), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)), sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_jobs.id", "investigation_jobs.snapshot_id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"],
            name="fk_patch_investigation_snapshot"),
        sa.UniqueConstraint("id", "repository_id", "tenant_id", name="uq_patch_proposal_owner"),
        sa.UniqueConstraint("investigation_id", "user_id", "request_key", name="uq_patch_proposal_request"),
        sa.CheckConstraint("status IN ('queued', 'generating', 'static_validated', 'validation_pending', "
                           "'validating', 'tests_passed', 'tests_failed', 'stale', 'failed') AND attempts >= 0",
                           name="ck_patch_proposal_status"),
        sa.CheckConstraint("review_state IN ('unreviewed', 'approved_for_review', 'rejected')",
                           name="ck_patch_proposal_review"))
    op.create_table("patch_outbox",
        sa.Column("proposal_id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id", "repository_id", "tenant_id"],
            ["patch_proposals.id", "patch_proposals.repository_id", "patch_proposals.tenant_id"],
            name="fk_patch_outbox_owner"),
        sa.CheckConstraint("status IN ('pending', 'processed', 'failed') AND attempts >= 0", name="ck_patch_outbox_status"))
    op.create_index("ix_patch_outbox_dispatch", "patch_outbox", ["status", "next_dispatch_at"])


def downgrade():
    op.drop_index("ix_patch_outbox_dispatch", table_name="patch_outbox")
    op.drop_table("patch_outbox")
    op.drop_table("patch_proposals")
