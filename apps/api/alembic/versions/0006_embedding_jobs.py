"""Add durable embedding jobs."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("embedding_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("session_hash", sa.String(64), sa.ForeignKey("auth_sessions.id_hash"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False), sa.Column("model", sa.String(150), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False), sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36)), sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)), sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("completed_chunks", sa.Integer(), nullable=False), sa.Column("token_usage", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id", "repository_id", "tenant_id"],
                                ["code_snapshots.id", "code_snapshots.repository_id", "code_snapshots.tenant_id"]),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')"),
        sa.CheckConstraint("dimensions BETWEEN 1 AND 2000"))
    op.create_index("ix_embedding_jobs_dispatch", "embedding_jobs", ["status", "next_dispatch_at"])
    op.create_index("uq_embedding_jobs_active", "embedding_jobs", ["repository_id"], unique=True,
                    postgresql_where=sa.text("status IN ('pending', 'running')"),
                    sqlite_where=sa.text("status IN ('pending', 'running')"))


def downgrade():
    op.drop_table("embedding_jobs")
