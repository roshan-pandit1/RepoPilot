"""Exact pgvector cosine search; authorization remains the caller's responsibility."""
import math
from sqlalchemy import Float, bindparam, cast, select, text
from sqlalchemy.orm import Session

from app.domain.models import (ChunkEmbedding, CodeChunk, CodeSnapshot, EmbeddingCache, IndexedFile,
                               Repository, SnapshotPublication)
from app.infra.vector_type import Vector
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.embedding_store import cache_key
from app.modules.ingestion.embeddings import EmbeddingError, EmbeddingProvider, validate_vectors
from app.modules.investigation.retrieval import fingerprint_chunk


def cosine_distance():
    return EmbeddingCache.vector.op("<=>", return_type=Float())(
        cast(bindparam("query_vector", type_=Vector()), Vector()))


def search_vectors(db: Session, *, repository_id: int, tenant_id: int, snapshot_id: str,
                   provider: EmbeddingProvider, query_vector: list[float], limit: int = 10,
                   expected_chunks: int | None = None):
    if db.get_bind().dialect.name != "postgresql":
        raise ValueError("PostgreSQL vector search required")
    if not 1 <= limit <= 50:
        raise ValueError("Invalid limit")
    # A future HNSW/IVFFlat index must not silently turn this baseline into ANN.
    db.execute(text("SET LOCAL enable_indexscan = off"))
    vector = validate_vectors([query_vector], 1, provider.dimensions)[0]
    repo = db.get(Repository, repository_id)
    snapshot = db.get(CodeSnapshot, snapshot_id)
    if (not repo or repo.tenant_id != tenant_id or not repo.enabled or not snapshot
            or snapshot.repository_id != repository_id or snapshot.tenant_id != tenant_id or not snapshot.published):
        return []
    publication = db.get(SnapshotPublication, snapshot_id)
    if publication and (publication.revoked_at is not None or publication.revocation_reason is not None
            or publication.repository_id != repository_id or publication.tenant_id != tenant_id
            or publication.commit_sha != snapshot.commit_sha
            or (publication.file_count, publication.chunk_count, publication.skipped_count)
            != (snapshot.file_count, snapshot.chunk_count, snapshot.skipped_count)):
        return []
    distance = cosine_distance()
    stmt = (select(CodeChunk, IndexedFile, distance.label("distance"), ChunkEmbedding, EmbeddingCache)
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
               EmbeddingCache.dimensions == provider.dimensions, EmbeddingCache.status == "ready",
               EmbeddingCache.model_revision == provider.revision,
               EmbeddingCache.representation_contract == provider.contract,
               EmbeddingCache.normalization == provider.normalization)
        .order_by(distance.asc(), IndexedFile.path, CodeChunk.start_line, CodeChunk.id).limit(10_001))
    rows = db.execute(stmt, {"query_vector": vector}).all()
    if len(rows) > 10_000 or (expected_chunks is not None and len(rows) != expected_chunks):
        raise EmbeddingError("embeddings_incomplete")
    for chunk, file, _distance, link, cached in rows:
        if (link.chunk_fingerprint != fingerprint_chunk(chunk, file)
                or cached.content_hash != cache_key(chunk.source_text)
                or len(chunk.source_text.splitlines()) != chunk.end_line - chunk.start_line + 1):
            raise EmbeddingError("embedding_integrity_failed")
        try:
            stored = validate_vectors([cached.vector], 1, provider.dimensions)[0]
            if (_distance is None or not math.isfinite(float(_distance))
                    or (provider.normalization == "l2" and not math.isclose(math.hypot(*stored), 1.0, abs_tol=1e-5))):
                raise ValueError("invalid_vector")
        except (EmbeddingError, ValueError, TypeError):
            raise EmbeddingError("embedding_integrity_failed") from None
        try:
            github_citation(repo.full_name, snapshot.commit_sha, file.path, chunk.start_line, chunk.end_line)
        except ValueError:
            raise EmbeddingError("embedding_integrity_failed") from None
    return [(chunk, file, distance) for chunk, file, distance, _link, _cache in rows[:limit]]
