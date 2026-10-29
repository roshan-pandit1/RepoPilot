"""Authenticated, read-only mock-investigation orchestration endpoints."""
from uuid import UUID, uuid4
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import (CodeSnapshot, Installation,
                               InvestigationEvidence, InvestigationJob, InvestigationOutbox, Repository)
from app.core.config import get_settings
from app.infra.database import get_db
from app.modules.auth.session import Principal, principal, require_csrf
from app.modules.github.client import GitHubClient, get_github_client
from app.modules.github.guards import installation_guard, repository_guard
from app.modules.github.issue_context import authorize, issue_context
from app.modules.ingestion.citations import github_citation
from app.modules.investigation.retrieval import InvalidEvidence, load_verified_evidence

router = APIRouter(prefix="/v1/repositories")


@router.post("/{repository_id}/issues/{issue_number}/investigations", status_code=202)
def submit(request: Request, repository_id: int = Path(gt=0, lt=2**63),
           issue_number: int = Path(gt=0, lt=2**31), identity: Principal = Depends(principal),
           db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    # Reject bad CSRF before network access; release the session lock before fetching.
    require_csrf(request, identity, db)
    db.rollback()
    # Recheck CSRF and local authorization before committing the job.
    context = issue_context(repository_id, issue_number, identity, db, github)
    require_csrf(request, identity, db)
    repo = db.scalar(select(Repository).where(Repository.id == repository_id,
                     Repository.tenant_id == identity.tenant_id))
    if not repo:
        raise HTTPException(404, "Repository not found")
    installation_id = repo.installation_id
    if installation_guard(db, installation_id).revoked:
        raise HTTPException(404, "Repository not found")
    installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
    if repository_guard(db, installation_id, repository_id).revoked:
        raise HTTPException(404, "Repository not found")
    repo = db.scalar(select(Repository).where(Repository.id == repository_id).with_for_update().execution_options(populate_existing=True))
    expected_url = "https://github.com/" + "/".join(quote(part, safe="") for part in repo.full_name.split("/")) + f"/issues/{issue_number}" if repo else None
    if (not installation or not installation.active or installation.tenant_id != identity.tenant_id or not repo
            or not repo.enabled or repo.tenant_id != identity.tenant_id or repo.installation_id != installation_id
            or context["url"] != expected_url):
        raise HTTPException(404, "Repository not found")
    active = db.scalar(select(InvestigationJob).where(InvestigationJob.tenant_id == identity.tenant_id,
        InvestigationJob.user_id == identity.user_id, InvestigationJob.repository_id == repository_id,
        InvestigationJob.issue_number == issue_number, InvestigationJob.status.in_(["queued", "running"])))
    if active and active.operation != "code_evidence":
        raise HTTPException(409, "Existing mock job is still active")
    if active:
        result = {"job_id": active.id, "status": active.status}
        db.commit()
        return result
    snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.repository_id == repository_id,
        CodeSnapshot.tenant_id == identity.tenant_id, CodeSnapshot.published.is_(True)).with_for_update())
    if not snapshot:
        raise HTTPException(409, "Repository has no published snapshot")
    settings = get_settings()
    job = InvestigationJob(id=str(uuid4()), tenant_id=identity.tenant_id, user_id=identity.user_id,
        query_limit=settings.investigation_query_limit, per_query_limit=settings.investigation_per_query_limit,
        evidence_limit=settings.investigation_evidence_limit,
        query_body_limit=min(4000, settings.issue_context_body_chars),
        operation="code_evidence", query_version="terms-v1", snapshot_id=snapshot.id, snapshot_commit_sha=snapshot.commit_sha,
        source_repository_name=repo.full_name,
        repository_id=repository_id, session_hash=identity.session_hash, issue_id=int(context["issue_id"]),
        issue_number=issue_number, issue_updated_at=context["updated_at"], context_retrieved_at=context["retrieved_at"])
    db.add(job)
    db.flush()
    db.add(InvestigationOutbox(job_id=job.id, tenant_id=identity.tenant_id, repository_id=repository_id))
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{repository_id}/investigations/{job_id}")
def status(repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
           identity: Principal = Depends(principal), db: Session = Depends(get_db),
           github: GitHubClient = Depends(get_github_client)):
    name = authorize(repository_id, identity, db, github)
    job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == str(job_id),
        InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id,
        InvestigationJob.repository_id == repository_id))
    if not job:
        raise HTTPException(404, "Investigation not found")
    retrieval_status = "not_applicable"
    snapshot_partial = None
    if job.operation == "code_evidence":
        snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.id == job.snapshot_id,
            CodeSnapshot.repository_id == repository_id, CodeSnapshot.tenant_id == identity.tenant_id,
            CodeSnapshot.published.is_(True), CodeSnapshot.commit_sha == job.snapshot_commit_sha))
        if not snapshot or job.source_repository_name != name:
            retrieval_status = "snapshot_unavailable"
        elif job.status == "completed":
            snapshot_partial = bool(snapshot.skipped_count)
            retrieval_status = job.retrieval_warning or "ready"
        else:
            snapshot_partial = bool(snapshot.skipped_count)
            retrieval_status = job.status
    return {"job_id": job.id, "status": job.status, "attempts": job.attempts,
            "created_at": job.created_at, "updated_at": job.updated_at, "started_at": job.started_at,
            "completed_at": job.completed_at, "error_code": job.error_code,
            "operation": job.operation, "snapshot_id": job.snapshot_id, "commit_sha": job.snapshot_commit_sha,
            "retrieval_status": retrieval_status,
            "evidence_count": db.scalar(select(func.count()).select_from(InvestigationEvidence).where(
                InvestigationEvidence.job_id == job.id)), "retrieval_warning": job.retrieval_warning, "snapshot_partial": snapshot_partial,
            "query_version": job.query_version, "query_input_truncated": job.query_input_truncated,
            "retrieval_limits": {"queries": job.query_limit, "per_query": job.per_query_limit,
                                 "evidence": job.evidence_limit, "body_chars": job.query_body_limit} if job.operation == "code_evidence" else None}


@router.get("/{repository_id}/investigations/{job_id}/evidence")
def evidence(repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
             identity: Principal = Depends(principal), db: Session = Depends(get_db),
             github: GitHubClient = Depends(get_github_client)):
    name = authorize(repository_id, identity, db, github)
    job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == str(job_id),
        InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id,
        InvestigationJob.repository_id == repository_id))
    if not job:
        raise HTTPException(404, "Investigation not found")
    if job.operation != "code_evidence" or job.status != "completed":
        raise HTTPException(409, "Evidence is not available")
    snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.id == job.snapshot_id,
        CodeSnapshot.repository_id == repository_id, CodeSnapshot.tenant_id == identity.tenant_id,
        CodeSnapshot.published.is_(True), CodeSnapshot.commit_sha == job.snapshot_commit_sha))
    if not snapshot or name != job.source_repository_name:
        raise HTTPException(409, "Snapshot is no longer available")
    try:
        rows = load_verified_evidence(db, job, snapshot)
    except InvalidEvidence:
        raise HTTPException(409, "Evidence is unavailable") from None
    try:
        items = [{"chunk_id": chunk.id, "rank": item.rank, "query_id": item.query_id,
                  "query_hash": item.query_hash, "query_rank": item.query_rank, "method": item.method,
                  "created_at": item.created_at,
                  "path": file.path, "symbol": chunk.symbol, "start_line": chunk.start_line,
                  "end_line": chunk.end_line, "commit_sha": snapshot.commit_sha,
                  "url": github_citation(name, snapshot.commit_sha, file.path, chunk.start_line, chunk.end_line)}
                 for item, chunk, file in rows]
    except ValueError:
        raise HTTPException(409, "Evidence is unavailable") from None
    return {"job_id": job.id, "snapshot_id": snapshot.id, "commit_sha": snapshot.commit_sha,
            "retrieval_status": job.retrieval_warning or "ready", "snapshot_partial": bool(snapshot.skipped_count),
            "query_version": job.query_version, "query_input_truncated": job.query_input_truncated,
            "evidence_count": len(items), "items": items}
