"""Add tenant-scoped content-addressed embedding storage."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import UserDefinedType

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


class Vector(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "vector"


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    with op.batch_alter_table("code_chunks", table_args=(sa.CheckConstraint("start_line > 0 AND end_line >= start_line"),)) as batch:
        batch.create_unique_constraint("uq_code_chunks_owner", ["id", "repository_id", "tenant_id"])
    op.create_table("embedding_cache",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(150), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector", Vector() if dialect == "postgresql" else sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id", "tenant_id"], ["repositories.id", "repositories.tenant_id"]),
        sa.UniqueConstraint("id", "repository_id", "tenant_id"),
        sa.UniqueConstraint("repository_id", "tenant_id", "content_hash", "provider", "model", "model_version", "dimensions", name="uq_embedding_cache_key"),
        sa.CheckConstraint("dimensions BETWEEN 1 AND 2000"),
        sa.CheckConstraint("status IN ('ready', 'failed')"))
    if dialect == "postgresql":
        op.create_check_constraint("ck_embedding_vector_dimensions", "embedding_cache", "vector_dims(vector) = dimensions")
    op.create_table("chunk_embeddings",
        sa.Column("chunk_id", sa.String(36), primary_key=True),
        sa.Column("cache_id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id", "repository_id", "tenant_id"],
                                ["code_chunks.id", "code_chunks.repository_id", "code_chunks.tenant_id"]),
        sa.ForeignKeyConstraint(["cache_id", "repository_id", "tenant_id"],
                                ["embedding_cache.id", "embedding_cache.repository_id", "embedding_cache.tenant_id"]))
    op.create_index("ix_chunk_embeddings_owner", "chunk_embeddings", ["tenant_id", "repository_id"])


def downgrade():
    op.drop_table("chunk_embeddings")
    op.drop_table("embedding_cache")
    with op.batch_alter_table("code_chunks", table_args=(sa.CheckConstraint("start_line > 0 AND end_line >= start_line"),)) as batch:
        batch.drop_constraint("uq_code_chunks_owner", type_="unique")
