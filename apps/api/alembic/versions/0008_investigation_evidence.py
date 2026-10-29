"""Bind new investigations to snapshots and add chunk-reference evidence."""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("investigation_jobs", table_args=(
        sa.CheckConstraint("issue_number > 0 AND issue_id > 0 AND attempts >= 0"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"),
    )) as batch:
        batch.add_column(sa.Column("operation", sa.String(30), nullable=False, server_default="mock_orchestration"))
        batch.add_column(sa.Column("snapshot_id", sa.String(36)))
        batch.add_column(sa.Column("snapshot_commit_sha", sa.String(40)))
        batch.add_column(sa.Column("source_repository_name", sa.String(250)))
        batch.add_column(sa.Column("retrieval_warning", sa.String(40)))
        batch.add_column(sa.Column("query_version", sa.String(30)))
        batch.add_column(sa.Column("query_limit", sa.Integer()))
        batch.add_column(sa.Column("per_query_limit", sa.Integer()))
        batch.add_column(sa.Column("evidence_limit", sa.Integer()))
        batch.add_column(sa.Column("query_body_limit", sa.Integer()))
        batch.add_column(sa.Column("query_input_truncated", sa.Boolean()))
        batch.create_unique_constraint("uq_investigation_snapshot_owner", ["id", "snapshot_id", "repository_id", "tenant_id"])
        batch.create_foreign_key("fk_investigation_snapshot_owner", "code_snapshots",
            ["snapshot_id", "repository_id", "tenant_id"], ["id", "repository_id", "tenant_id"])
        batch.create_check_constraint("ck_investigation_operation_snapshot", "(operation = 'mock_orchestration' AND snapshot_id IS NULL AND snapshot_commit_sha IS NULL AND source_repository_name IS NULL AND query_version IS NULL) OR (operation = 'code_evidence' AND snapshot_id IS NOT NULL AND snapshot_commit_sha IS NOT NULL AND source_repository_name IS NOT NULL AND query_version IS NOT NULL AND query_limit IS NOT NULL AND query_limit BETWEEN 1 AND 3 AND per_query_limit IS NOT NULL AND per_query_limit BETWEEN 1 AND 20 AND evidence_limit IS NOT NULL AND evidence_limit BETWEEN 1 AND 30 AND query_body_limit IS NOT NULL AND query_body_limit BETWEEN 1 AND 4000)")
    op.create_table("investigation_evidence",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False), sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False), sa.Column("query_id", sa.String(40), nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False), sa.Column("chunk_fingerprint", sa.String(64), nullable=False),
        sa.Column("query_rank", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_jobs.id", "investigation_jobs.snapshot_id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"], name="fk_evidence_investigation_snapshot"),
        sa.ForeignKeyConstraint(["chunk_id", "repository_id", "tenant_id"],
            ["code_chunks.id", "code_chunks.repository_id", "code_chunks.tenant_id"], name="fk_evidence_chunk_owner"),
        sa.UniqueConstraint("job_id", "chunk_id", name="uq_evidence_job_chunk"),
        sa.UniqueConstraint("job_id", "rank", name="uq_evidence_job_rank"),
        sa.CheckConstraint("rank > 0 AND query_rank > 0 AND method = 'keyword'", name="ck_evidence_rank_method"))


def downgrade():
    op.drop_table("investigation_evidence")
    with op.batch_alter_table("investigation_jobs", table_args=(
        sa.CheckConstraint("issue_number > 0 AND issue_id > 0 AND attempts >= 0"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"),
    )) as batch:
        batch.drop_constraint("ck_investigation_operation_snapshot", type_="check")
        batch.drop_constraint("fk_investigation_snapshot_owner", type_="foreignkey")
        batch.drop_constraint("uq_investigation_snapshot_owner", type_="unique")
        for name in ("query_input_truncated", "query_body_limit", "evidence_limit", "per_query_limit", "query_limit", "query_version", "retrieval_warning", "source_repository_name", "snapshot_commit_sha", "snapshot_id", "operation"):
            batch.drop_column(name)
