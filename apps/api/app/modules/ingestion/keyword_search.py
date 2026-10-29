"""Shared PostgreSQL lexical ranking for authorized, explicitly scoped snapshots."""
from sqlalchemy import Text, case, cast, func, select, text

from app.domain.models import CodeChunk, IndexedFile


def keyword_statement(*, repository_id: int, tenant_id: int, snapshot_id: str, query_text: str, limit: int):
    """Build the existing search expression; caller must authorize and check publication."""
    if not query_text.strip() or len(query_text) > 200 or not 1 <= limit <= 50:
        raise ValueError("invalid_keyword_query")
    normalized = func.replace(query_text, "_", " ")
    parsed = func.plainto_tsquery(text("'english'"), normalized)
    query = func.to_tsquery(text("'english'"), func.replace(cast(parsed, Text), " & ", " | "))
    source_vector = func.to_tsvector(text("'english'"), func.replace(
        func.coalesce(CodeChunk.symbol, text("''")) + text("' '") + CodeChunk.source_text, "_", " "))
    path_vector = func.to_tsvector(text("'english'"), func.replace(IndexedFile.path, "_", " "))
    exact_symbol = case((func.lower(CodeChunk.symbol) == query_text.strip().lower(), 5.0), else_=0.0)
    score = func.ts_rank_cd(source_vector, query) + func.ts_rank_cd(path_vector, query) + exact_symbol
    return (select(CodeChunk, IndexedFile, score.label("score")).join(IndexedFile,
        CodeChunk.file_id == IndexedFile.id).where(
        CodeChunk.tenant_id == tenant_id, CodeChunk.repository_id == repository_id,
        IndexedFile.tenant_id == tenant_id, IndexedFile.repository_id == repository_id,
        IndexedFile.snapshot_id == snapshot_id,
        (source_vector.op("@@")(query) | path_vector.op("@@")(query)))
        .order_by(score.desc(), IndexedFile.path, CodeChunk.start_line, CodeChunk.id).limit(limit))
