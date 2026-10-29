"""Add independently dispatched mock report jobs and evidence-backed reports."""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("investigation_report_jobs",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False), sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_hash", sa.String(64), sa.ForeignKey("auth_sessions.id_hash"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_token", sa.String(36)), sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.ForeignKeyConstraint(["investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_jobs.id", "investigation_jobs.snapshot_id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"], name="fk_report_job_investigation_snapshot"),
        sa.UniqueConstraint("investigation_id", name="uq_report_job_investigation"),
        sa.UniqueConstraint("id", "repository_id", "tenant_id", name="uq_report_job_owner"),
        sa.UniqueConstraint("id", "investigation_id", "snapshot_id", "repository_id", "tenant_id", name="uq_report_job_full_owner"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled') AND attempts >= 0", name="ck_report_job_status"))
    op.create_table("investigation_report_outbox",
        sa.Column("job_id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id", "repository_id", "tenant_id"], ["investigation_report_jobs.id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"], name="fk_report_outbox_owner"),
        sa.CheckConstraint("status IN ('pending', 'processed') AND attempts >= 0", name="ck_report_outbox_status"))
    op.create_index("ix_report_outbox_dispatch", "investigation_report_outbox", ["status", "next_dispatch_at"])
    op.create_table("investigation_reports",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("report_job_id", sa.String(36), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False), sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False), sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False), sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("input_tokens", sa.Integer()), sa.Column("output_tokens", sa.Integer()), sa.Column("cost_microusd", sa.Integer()),
        sa.Column("input_truncated", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id", "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"], name="fk_report_job_full_owner"),
        sa.UniqueConstraint("investigation_id", name="uq_report_investigation"), sa.UniqueConstraint("report_job_id", name="uq_report_job"),
        sa.CheckConstraint("provider = 'mock' AND model = 'deterministic-v1'", name="ck_report_mock_provider"),
        sa.CheckConstraint("(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0) AND (cost_microusd IS NULL OR cost_microusd >= 0)", name="ck_report_usage"))


def downgrade():
    op.drop_table("investigation_reports")
    op.drop_table("investigation_report_outbox")
    op.drop_table("investigation_report_jobs")
