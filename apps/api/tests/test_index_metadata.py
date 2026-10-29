from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from app.domain.models import CodeChunk


def test_postgres_fts_metadata_matches_reflected_expression():
    """PostgreSQL adds casts and grouping when reflecting the migrated GIN index."""
    index = next(index for index in CodeChunk.__table__.indexes if index.name == "ix_code_chunks_fts")
    impl = MigrationContext.configure(dialect=postgresql.dialect()).impl
    reflected = text("to_tsvector('simple'::regconfig, (COALESCE(symbol, ''::text) || ' '::text) || source_text)")
    assert impl._cleanup_index_expr(index, str(index.expressions[0])) == impl._cleanup_index_expr(index, str(reflected))
