"""Add tenant-owned indexing jobs and immutable source snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("index_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("session_hash", sa.String(64), sa.ForeignKey("auth_sessions.id_hash"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("commit_sha", sa.String(40)),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["repository_id", "tenant_id"], ["repositories.id", "repositories.tenant_id"]),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'partial', 'failed', 'cancelled')"))
    op.create_index("ix_index_jobs_dispatch", "index_jobs", ["status", "next_dispatch_at"])
    op.create_index("uq_index_jobs_active", "index_jobs", ["repository_id"], unique=True,
                    postgresql_where=sa.text("status IN ('pending', 'running')"),
                    sqlite_where=sa.text("status IN ('pending', 'running')"))
    op.create_table("code_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["repository_id", "tenant_id"], ["repositories.id", "repositories.tenant_id"]),
        sa.UniqueConstraint("id", "repository_id", "tenant_id"))
    op.create_index("uq_code_snapshots_published", "code_snapshots", ["repository_id"], unique=True,
                    postgresql_where=sa.text("published"), sqlite_where=sa.text("published = 1"))
    op.create_table("indexed_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id", "repository_id", "tenant_id"],
            ["code_snapshots.id", "code_snapshots.repository_id", "code_snapshots.tenant_id"]),
        sa.UniqueConstraint("snapshot_id", "path"), sa.UniqueConstraint("id", "repository_id", "tenant_id"))
    op.create_table("code_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("file_id", sa.String(36), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.Text()),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["file_id", "repository_id", "tenant_id"],
            ["indexed_files.id", "indexed_files.repository_id", "indexed_files.tenant_id"]),
        sa.UniqueConstraint("file_id", "start_line"),
        sa.CheckConstraint("start_line > 0 AND end_line >= start_line"))
    op.create_index("ix_code_chunks_tenant_repository", "code_chunks", ["tenant_id", "repository_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE INDEX ix_code_chunks_fts ON code_chunks USING gin "
                   "(to_tsvector('simple', coalesce(symbol, '') || ' ' || source_text))")
        op.execute("CREATE INDEX ix_indexed_files_path_fts ON indexed_files USING gin "
                   "(to_tsvector('simple', path))")


def downgrade():
    op.drop_table("code_chunks")
    op.drop_table("indexed_files")
    op.drop_table("code_snapshots")
    op.drop_table("index_jobs")
