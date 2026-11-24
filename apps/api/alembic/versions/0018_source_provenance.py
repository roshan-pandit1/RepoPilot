"""Persist source byte identity and explicit coverage for newly indexed files."""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("indexed_files", sa.Column("source_byte_length", sa.Integer(), nullable=True))
    op.add_column("indexed_files", sa.Column("source_encoding", sa.String(24), nullable=True))
    op.add_column("indexed_files", sa.Column("source_normalization", sa.String(24), nullable=True))
    op.add_column("indexed_files", sa.Column("source_coverage", sa.String(24), nullable=False,
                                              server_default="UNKNOWN_COVERAGE"))
    with op.batch_alter_table("indexed_files") as batch_op:
        batch_op.create_check_constraint(
            "ck_indexed_files_source_provenance",
            "(source_coverage = 'UNKNOWN_COVERAGE' AND source_byte_length IS NULL "
            "AND source_encoding IS NULL AND source_normalization IS NULL) OR "
            "(source_coverage = 'COMPLETE_FILE' AND source_byte_length IS NOT NULL "
            "AND source_byte_length >= 0 AND source_encoding IS NOT NULL "
            "AND source_encoding = 'utf-8' AND source_normalization IS NOT NULL "
            "AND source_normalization = 'identity')",
        )


def downgrade():
    with op.batch_alter_table("indexed_files") as batch_op:
        batch_op.drop_constraint("ck_indexed_files_source_provenance", type_="check")
        batch_op.drop_column("source_coverage")
        batch_op.drop_column("source_normalization")
        batch_op.drop_column("source_encoding")
        batch_op.drop_column("source_byte_length")
