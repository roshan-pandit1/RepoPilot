"""Exact pgvector cosine search; authorization remains the caller's responsibility."""
from sqlalchemy import Float, bindparam, cast, select
from sqlalchemy.orm import Session

from app.domain.models import ChunkEmbedding, CodeChunk, CodeSnapshot, EmbeddingCache, IndexedFile
from app.infra.vector_type import Vector
from app.modules.ingestion.embeddings import EmbeddingProvider, validate_vectors


def cosine_distance():
    return EmbeddingCache.vector.op("<=>", return_type=Float())(
        cast(bindparam("query_vector", type_=Vector()), Vector()))


def search_vectors(db: Session, *, repository_id: int, tenant_id: int, snapshot_id: str,
                   provider: EmbeddingProvider, query_vector: list[float], limit: int = 10):
    if db.get_bind().dialect.name != "postgresql":
        raise ValueError("PostgreSQL vector search required")
    if not 1 <= limit <= 50:
        raise ValueError("Invalid limit")
    vector = validate_vectors([query_vector], 1, provider.dimensions)[0]
    distance = cosine_distance()
    stmt = (select(CodeChunk, IndexedFile, distance.label("distance"))
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == CodeChunk.id)
        .join(EmbeddingCache, EmbeddingCache.id == ChunkEmbedding.cache_id)
        .join(IndexedFile, IndexedFile.id == CodeChunk.file_id)
        .join(CodeSnapshot, CodeSnapshot.id == IndexedFile.snapshot_id)
        .where(CodeChunk.repository_id == repository_id, CodeChunk.tenant_id == tenant_id,
               IndexedFile.repository_id == repository_id, IndexedFile.tenant_id == tenant_id,
               IndexedFile.snapshot_id == snapshot_id, CodeSnapshot.id == snapshot_id,
               CodeSnapshot.repository_id == repository_id, CodeSnapshot.tenant_id == tenant_id,
               CodeSnapshot.published.is_(True), ChunkEmbedding.repository_id == repository_id,
               ChunkEmbedding.tenant_id == tenant_id, EmbeddingCache.repository_id == repository_id,
               EmbeddingCache.tenant_id == tenant_id, EmbeddingCache.provider == provider.provider,
               EmbeddingCache.model == provider.model, EmbeddingCache.model_version == provider.version,
               EmbeddingCache.dimensions == provider.dimensions, EmbeddingCache.status == "ready")
        .order_by(distance.asc(), IndexedFile.path, CodeChunk.start_line, CodeChunk.id).limit(limit))
    return db.execute(stmt, {"query_vector": vector}).all()
