"""Add durable investigation jobs and transactional dispatch records."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("investigation_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_hash", sa.String(64), sa.ForeignKey("auth_sessions.id_hash"), nullable=False),
        sa.Column("issue_id", sa.BigInteger(), nullable=False), sa.Column("issue_number", sa.Integer(), nullable=False),
        sa.Column("issue_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context_retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_token", sa.String(36)), sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.ForeignKeyConstraint(["repository_id", "tenant_id"], ["repositories.id", "repositories.tenant_id"]),
        sa.UniqueConstraint("id", "repository_id", "tenant_id"),
        sa.CheckConstraint("issue_number > 0 AND issue_id > 0 AND attempts >= 0"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"))
    op.create_index("uq_investigation_active", "investigation_jobs", ["tenant_id", "user_id", "repository_id", "issue_number"],
                    unique=True, postgresql_where=sa.text("status IN ('queued', 'running')"),
                    sqlite_where=sa.text("status IN ('queued', 'running')"))
    op.create_table("investigation_outbox",
        sa.Column("job_id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id", "repository_id", "tenant_id"],
          ["investigation_jobs.id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"]),
        sa.CheckConstraint("status IN ('pending', 'processed') AND attempts >= 0"))
    op.create_index("ix_investigation_outbox_dispatch", "investigation_outbox", ["status", "next_dispatch_at"])


def downgrade():
    op.drop_table("investigation_outbox")
    op.drop_table("investigation_jobs")
