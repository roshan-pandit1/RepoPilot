"""Authenticated indexing and PostgreSQL lexical search endpoints."""
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.v1.routes import authorized_repos
from app.core.config import get_settings
from app.core.index_logging import index_event
from app.domain.models import CodeSnapshot, EmbeddingJob, IndexJob, IndexedFile, Repository
from app.infra.database import get_db
from app.modules.auth.session import Principal, principal, require_csrf
from app.modules.github.client import GitHubClient, get_github_client
from app.modules.ingestion.embeddings import EmbeddingError, configured_provider
from app.modules.ingestion.rank_fusion import reciprocal_rank_fusion
from app.modules.ingestion.keyword_search import keyword_statement
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.semantic_search import search_vectors
from app.modules.investigation.retrieval import SnapshotUnavailable, validate_snapshot

router = APIRouter(prefix="/v1/repositories")


def allowed_repository(repo_id: int, identity: Principal, db: Session, github: GitHubClient) -> Repository:
    if identity.demo or not 0 < repo_id < 2**63:
        raise HTTPException(404, "Repository not found")
    repo = next((item for item in authorized_repos(identity, db, github) if item.id == repo_id), None)
    if not repo:
        raise HTTPException(404, "Repository not found")
    return repo


@router.post("/{repository_id}/index", status_code=202)
def start_index(repository_id: int, request: Request, identity: Principal = Depends(principal),
                db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    require_csrf(request, identity, db)
    allowed_repository(repository_id, identity, db, github)
    repo = db.scalar(select(Repository).where(Repository.id == repository_id,
                    Repository.tenant_id == identity.tenant_id, Repository.enabled.is_(True)).with_for_update())
    if not repo:
        raise HTTPException(404, "Repository not found")
    job = db.scalar(select(IndexJob).where(IndexJob.repository_id == repo.id,
                    IndexJob.tenant_id == identity.tenant_id, IndexJob.status.in_(["pending", "running"])))
    created = job is None
    if created:
        settings = get_settings()
        indexing_mode = ("multi_supervised" if settings.index_multilingual_supervised_parser_enabled
                         else "multilingual") if settings.index_multilingual_enabled else "python"
        job = IndexJob(id=str(uuid4()), repository_id=repo.id, tenant_id=identity.tenant_id,
                       session_hash=identity.session_hash,
                       indexing_mode=indexing_mode)
        db.add(job)
        db.flush()
    result = {"job_id": job.id, "status": job.status}
    db.commit()
    if created:
        index_event("index_job_queued", job_id=result["job_id"], repository_id=repository_id)
    return result


@router.get("/{repository_id}/index-status")
def index_status(repository_id: int, identity: Principal = Depends(principal),
                 db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    repo = allowed_repository(repository_id, identity, db, github)
    job = db.scalar(select(IndexJob).where(IndexJob.repository_id == repo.id,
                    IndexJob.tenant_id == identity.tenant_id).order_by(IndexJob.created_at.desc()).limit(1))
    snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.repository_id == repo.id,
                         CodeSnapshot.tenant_id == identity.tenant_id, CodeSnapshot.published.is_(True)))
    fallback_count = db.scalar(select(func.count()).select_from(IndexedFile).where(
        IndexedFile.snapshot_id == snapshot.id, IndexedFile.repository_id == repo.id,
        IndexedFile.tenant_id == identity.tenant_id, IndexedFile.parser_status.is_not(None),
        IndexedFile.parser_status != "parsed")) if snapshot else 0
    return {"status": job.status if job else "not_indexed", "job_id": job.id if job else None,
            "error_code": job.error_code if job else None,
            "commit_sha": snapshot.commit_sha if snapshot else None,
            "indexed_at": snapshot.created_at.isoformat() if snapshot else None,
            "file_count": snapshot.file_count if snapshot else 0,
            "chunk_count": snapshot.chunk_count if snapshot else 0,
            "skipped_count": snapshot.skipped_count if snapshot else 0,
            "indexing_mode": snapshot.indexing_mode if snapshot else None,
            "unsupported_count": snapshot.unsupported_count if snapshot else None,
            "parser_fallback_count": fallback_count}


@router.post("/{repository_id}/embeddings", status_code=202)
def start_embeddings(repository_id: int, request: Request, identity: Principal = Depends(principal),
                     db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    require_csrf(request, identity, db)
    allowed_repository(repository_id, identity, db, github)
    try:
        provider = configured_provider()
        if provider.provider == "local-onnx":
            provider.available()
    except EmbeddingError as exc:
        detail = str(exc) if str(exc) in {"MODEL_NOT_AVAILABLE", "LOCAL_RUNTIME_NOT_AVAILABLE", "LOCAL_RUNTIME_UNSAFE", "LOCAL_RUNTIME_INCOMPATIBLE"} else "Embeddings are not configured"
        raise HTTPException(503, detail) from None
    if provider.provider not in {"fake", "local-onnx"}:
        raise HTTPException(503, "Paid embedding generation is not enabled")
    repo = db.scalar(select(Repository).where(Repository.id == repository_id,
                     Repository.tenant_id == identity.tenant_id, Repository.enabled.is_(True)).with_for_update())
    if not repo:
        raise HTTPException(404, "Repository not found")
    snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.repository_id == repo.id,
                         CodeSnapshot.tenant_id == identity.tenant_id, CodeSnapshot.published.is_(True)))
    if not snapshot:
        raise HTTPException(409, "Repository has no published index")
    job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.repository_id == repo.id,
                    EmbeddingJob.tenant_id == identity.tenant_id, EmbeddingJob.status.in_(["pending", "running"])))
    if not job:
        job = EmbeddingJob(id=str(uuid4()), snapshot_id=snapshot.id, repository_id=repo.id,
            tenant_id=identity.tenant_id, session_hash=identity.session_hash, provider=provider.provider,
            model=provider.model, model_version=provider.version, dimensions=provider.dimensions,
            model_revision=provider.revision, representation_contract=provider.contract,
            normalization=provider.normalization)
        db.add(job)
        db.flush()
    result = {"job_id": job.id, "status": job.status}
    db.commit()
    return result


@router.get("/{repository_id}/embedding-status")
def embedding_status(repository_id: int, identity: Principal = Depends(principal),
                     db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    repo = allowed_repository(repository_id, identity, db, github)
    job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.repository_id == repo.id,
                    EmbeddingJob.tenant_id == identity.tenant_id).order_by(EmbeddingJob.created_at.desc()).limit(1))
    snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.repository_id == repo.id,
                         CodeSnapshot.tenant_id == identity.tenant_id, CodeSnapshot.published.is_(True)))
    availability_error = None
    try:
        provider = configured_provider()
        if provider.provider == "local-onnx":
            provider.available()
    except EmbeddingError as exc:
        availability_error = str(exc)
        provider = None
    enabled = bool(provider and provider.provider in {"fake", "local-onnx"})
    ready = bool(enabled and snapshot and db.scalar(select(EmbeddingJob.id).where(
        EmbeddingJob.repository_id == repo.id, EmbeddingJob.tenant_id == identity.tenant_id,
        EmbeddingJob.snapshot_id == snapshot.id, EmbeddingJob.status == "completed",
        EmbeddingJob.total_chunks > 0, EmbeddingJob.provider == provider.provider,
        EmbeddingJob.model == provider.model, EmbeddingJob.model_version == provider.version,
        EmbeddingJob.dimensions == provider.dimensions, EmbeddingJob.model_revision == provider.revision,
        EmbeddingJob.representation_contract == provider.contract, EmbeddingJob.normalization == provider.normalization,
        EmbeddingJob.completed_chunks == EmbeddingJob.total_chunks).limit(1)))
    job_snapshot = db.get(CodeSnapshot, job.snapshot_id) if job else None
    return {"status": job.status if job else "not_started", "job_id": job.id if job else None,
            "completed_chunks": job.completed_chunks if job else 0, "total_chunks": job.total_chunks if job else 0,
            "token_usage": job.token_usage if job else 0,
            "error_code": job.error_code if job and job.error_code else availability_error,
            "availability_error": availability_error,
            "provider": job.provider if job else None, "model": job.model if job else None,
            "dimensions": job.dimensions if job else None,
            "model_revision": job.model_revision if job else None,
            "representation_contract": job.representation_contract if job else None,
            "normalization": job.normalization if job else None, "ready": ready,
            "generation_available": enabled, "snapshot_commit": snapshot.commit_sha if snapshot else None,
            "job_commit": job_snapshot.commit_sha if job_snapshot else None}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)
    mode: Literal["keyword", "semantic", "hybrid"] = "keyword"


@router.post("/{repository_id}/search")
def search_code(repository_id: int, body: SearchRequest, request: Request,
                identity: Principal = Depends(principal), db: Session = Depends(get_db),
                github: GitHubClient = Depends(get_github_client)):
    require_csrf(request, identity, db)
    repo = allowed_repository(repository_id, identity, db, github)
    if not body.query.strip():
        raise HTTPException(422, "Search query cannot be empty")
    if db.bind.dialect.name != "postgresql":
        raise HTTPException(503, "Search requires PostgreSQL")
    snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.repository_id == repo.id,
                         CodeSnapshot.tenant_id == identity.tenant_id, CodeSnapshot.published.is_(True)))
    if not snapshot:
        raise HTTPException(409, "Repository has no published index")
    try:
        validate_snapshot(db, snapshot_id=snapshot.id, repository_id=repo.id,
                          tenant_id=identity.tenant_id, commit=snapshot.commit_sha)
    except SnapshotUnavailable:
        raise HTTPException(409, "Repository index is unavailable") from None
    stmt = keyword_statement(repository_id=repo.id, tenant_id=identity.tenant_id,
                             snapshot_id=snapshot.id, query_text=body.query, limit=min(50, body.limit * 3))
    db.execute(text("SET LOCAL statement_timeout = '3s'"))
    keyword_rows = db.execute(stmt).all() if body.mode in {"keyword", "hybrid"} else []
    semantic_rows = []
    semantic_identity = None
    fallback = None
    if body.mode != "keyword":
        try:
            provider = configured_provider()
            if provider.provider not in {"fake", "local-onnx"}:
                raise EmbeddingError("semantic_provider_not_enabled")
            if provider.provider == "local-onnx":
                provider.available()
            completed = db.scalar(select(EmbeddingJob.total_chunks).where(
                EmbeddingJob.repository_id == repo.id, EmbeddingJob.tenant_id == identity.tenant_id,
                EmbeddingJob.snapshot_id == snapshot.id, EmbeddingJob.status == "completed",
                EmbeddingJob.provider == provider.provider, EmbeddingJob.model == provider.model,
                EmbeddingJob.model_version == provider.version, EmbeddingJob.dimensions == provider.dimensions,
                EmbeddingJob.model_revision == provider.revision, EmbeddingJob.representation_contract == provider.contract,
                EmbeddingJob.normalization == provider.normalization,
                EmbeddingJob.completed_chunks == EmbeddingJob.total_chunks).limit(1))
            if not completed:
                raise EmbeddingError("embeddings_not_ready")
            vector = (provider.embed_query(body.query) if provider.provider == "local-onnx"
                      else provider.embed([body.query])).vectors[0]
            semantic_rows = search_vectors(db, repository_id=repo.id, tenant_id=identity.tenant_id,
                                           snapshot_id=snapshot.id, provider=provider,
                                           query_vector=vector, limit=min(50, body.limit * 3),
                                           expected_chunks=completed)
            if not semantic_rows:
                raise EmbeddingError("embeddings_not_ready")
            semantic_identity = {"provider": provider.provider, "model": provider.model, "dimensions": provider.dimensions,
                "revision": provider.revision, "representation_contract": provider.contract,
                "normalization": provider.normalization, "quality": "not_evaluated"}
        except EmbeddingError as exc:
            fallback = str(exc)
            if body.mode == "semantic":
                keyword_rows = db.execute(stmt).all()
    if body.mode == "keyword" or fallback:
        ranked = [(chunk, file, float(rank), "keyword") for chunk, file, rank in keyword_rows[:body.limit]]
        actual_mode = "keyword"
    elif body.mode == "semantic":
        ranked = [(chunk, file, 1.0 - float(distance), "semantic") for chunk, file, distance in semantic_rows[:body.limit]]
        actual_mode = "semantic"
    else:
        keyword = {chunk.id: (chunk, file) for chunk, file, _ in keyword_rows}
        semantic = {chunk.id: (chunk, file) for chunk, file, _ in semantic_rows}
        fused = reciprocal_rank_fusion([[chunk.id for chunk, _, _ in keyword_rows],
                                       [chunk.id for chunk, _, _ in semantic_rows]])
        ranked = []
        for chunk_id, rank in fused[:body.limit]:
            chunk, file = keyword.get(chunk_id) or semantic[chunk_id]
            method = "hybrid" if chunk_id in keyword and chunk_id in semantic else "keyword" if chunk_id in keyword else "semantic"
            ranked.append((chunk, file, rank, method))
        actual_mode = "hybrid"
    return {"snapshot_id": snapshot.id, "commit_sha": snapshot.commit_sha, "partial": bool(snapshot.skipped_count),
            "semantic_identity": semantic_identity,
            "missing_embeddings": fallback in {"embeddings_incomplete", "embeddings_not_ready"},
            "mode": actual_mode, "fallback_reason": fallback, "items": [
        {"repository_id": str(repo.id), "path": file.path, "symbol": chunk.symbol,
         "language": file.language, "parser_status": file.parser_status, "symbol_kind": chunk.symbol_kind,
         "snippet": chunk.source_text, "start_line": chunk.start_line, "end_line": chunk.end_line,
         "commit_sha": snapshot.commit_sha,
         "url": github_citation(repo.full_name, snapshot.commit_sha, file.path, chunk.start_line, chunk.end_line),
         "score": rank, "retrieval_method": method} for chunk, file, rank, method in ranked]}
