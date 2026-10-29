"""Tenant-scoped, content-addressed persistence; caller owns authorization and transaction."""
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain.models import ChunkEmbedding, CodeChunk, EmbeddingCache
from app.modules.ingestion.embeddings import EmbeddingProvider, validate_vectors


def cache_key(source: str) -> str:
    return sha256(source.encode("utf-8")).hexdigest()


def persist_embedding(db: Session, chunk: CodeChunk, provider: EmbeddingProvider,
                      vector: list[float]) -> EmbeddingCache:
    """Persist a validated vector and link it to a same-tenant chunk, idempotently."""
    values = validate_vectors([vector], 1, provider.dimensions)[0]
    key = {"repository_id": chunk.repository_id, "tenant_id": chunk.tenant_id,
           "content_hash": cache_key(chunk.source_text), "provider": provider.provider,
           "model": provider.model, "model_version": provider.version, "dimensions": provider.dimensions}
    dialect = db.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise ValueError("Unsupported database")
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    db.execute(insert(EmbeddingCache).values(id=str(uuid4()), **key, vector=values, status="ready")
               .on_conflict_do_nothing(index_elements=list(key)))
    cached = db.scalar(select(EmbeddingCache).filter_by(**key))
    if not cached or cached.status != "ready":
        raise ValueError("Embedding unavailable")
    db.execute(insert(ChunkEmbedding).values(chunk_id=chunk.id, cache_id=cached.id,
               repository_id=chunk.repository_id, tenant_id=chunk.tenant_id)
               .on_conflict_do_nothing(index_elements=["chunk_id", "cache_id"]))
    return cached
