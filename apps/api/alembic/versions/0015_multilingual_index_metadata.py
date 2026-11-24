"""Record optional language and parser provenance on new indexed files."""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("index_jobs", sa.Column("indexing_mode", sa.String(20)))
    op.add_column("code_snapshots", sa.Column("indexing_mode", sa.String(20)))
    op.add_column("code_snapshots", sa.Column("unsupported_count", sa.Integer()))
    op.add_column("indexed_files", sa.Column("language", sa.String(24)))
    op.add_column("indexed_files", sa.Column("parser_version", sa.String(100)))
    op.add_column("indexed_files", sa.Column("parser_status", sa.String(40)))
    op.add_column("indexed_files", sa.Column("import_ranges", sa.JSON()))
    op.add_column("code_chunks", sa.Column("symbol_kind", sa.String(24)))


def downgrade():
    op.drop_column("code_chunks", "symbol_kind")
    op.drop_column("indexed_files", "import_ranges")
    op.drop_column("indexed_files", "parser_status")
    op.drop_column("indexed_files", "parser_version")
    op.drop_column("indexed_files", "language")
    op.drop_column("code_snapshots", "unsupported_count")
    op.drop_column("code_snapshots", "indexing_mode")
    op.drop_column("index_jobs", "indexing_mode")
