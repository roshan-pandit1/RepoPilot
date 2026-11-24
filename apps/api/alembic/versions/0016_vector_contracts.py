"""Bind future vectors to a representation contract and chunk fingerprint."""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("embedding_cache", "embedding_jobs"):
        op.add_column(table, sa.Column("model_revision", sa.String(80)))
        op.add_column(table, sa.Column("representation_contract", sa.String(64)))
        op.add_column(table, sa.Column("normalization", sa.String(16)))
    op.add_column("chunk_embeddings", sa.Column("chunk_fingerprint", sa.String(64)))


def downgrade():
    op.drop_column("chunk_embeddings", "chunk_fingerprint")
    for table in ("embedding_jobs", "embedding_cache"):
        op.drop_column(table, "normalization")
        op.drop_column(table, "representation_contract")
        op.drop_column(table, "model_revision")
