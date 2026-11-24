"""Tenant-scoped, content-addressed persistence; caller owns authorization and transaction."""
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain.models import ChunkEmbedding, CodeChunk, EmbeddingCache, IndexedFile
from app.modules.ingestion.embeddings import EmbeddingProvider, validate_vectors
from app.modules.investigation.retrieval import fingerprint_chunk


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
    file = db.get(IndexedFile, chunk.file_id)
    if not file or (file.repository_id, file.tenant_id) != (chunk.repository_id, chunk.tenant_id):
        raise ValueError("Embedding source unavailable")
    fingerprint = fingerprint_chunk(chunk, file)
    db.execute(insert(EmbeddingCache).values(id=str(uuid4()), **key, vector=values, status="ready",
               model_revision=provider.revision, representation_contract=provider.contract,
               normalization=provider.normalization)
               .on_conflict_do_nothing(index_elements=list(key)))
    cached = db.scalar(select(EmbeddingCache).filter_by(**key))
    if (not cached or cached.status != "ready" or cached.model_revision != provider.revision
            or cached.representation_contract != provider.contract or cached.normalization != provider.normalization):
        raise ValueError("Embedding unavailable")
    db.execute(insert(ChunkEmbedding).values(chunk_id=chunk.id, cache_id=cached.id,
               repository_id=chunk.repository_id, tenant_id=chunk.tenant_id, chunk_fingerprint=fingerprint)
               .on_conflict_do_nothing(index_elements=["chunk_id", "cache_id"]))
    link = db.get(ChunkEmbedding, (chunk.id, cached.id))
    if not link or link.chunk_fingerprint != fingerprint:
        raise ValueError("Embedding source changed")
    return cached
