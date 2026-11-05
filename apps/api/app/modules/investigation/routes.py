"""Authenticated, read-only mock-investigation orchestration endpoints."""
from uuid import UUID, uuid4
from urllib.parse import quote, unquote, urlsplit

from datetime import datetime
from threading import BoundedSemaphore
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, SecretStr
from sqlalchemy import and_, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.domain.models import (CodeSnapshot, Installation, Issue,
                               InvestigationEvidence, InvestigationJob, InvestigationOutbox,
                               InvestigationReportJob, Repository)
from app.core.config import get_settings
from app.infra.database import get_db
from app.modules.auth.session import Principal, principal, require_csrf, utc
from app.modules.github.client import GitHubClient, get_github_client
from app.modules.github.guards import installation_guard, repository_guard
from app.modules.github.issue_context import authorize, issue_context
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.code_selection import contains_sensitive_source
from app.modules.investigation.retrieval import (InvalidEvidence, SnapshotUnavailable, load_verified_evidence,
                                                readable_snapshot, validate_snapshot)
from app.modules.investigation.code_intelligence_schema import AnalysisResponse

router = APIRouter(prefix="/v1/repositories")
SNIPPET_CHARS = 4000
_analysis_slot = BoundedSemaphore(1)


class HistoryItem(BaseModel):
    job_id: str
    issue_number: int
    issue_title: str | None
    status: Literal['queued', 'running', 'completed', 'failed', 'cancelled']
    created_at: datetime
    updated_at: datetime
    attempts: int
    evidence_count: int
    report_status: Literal['queued', 'running', 'completed', 'failed', 'cancelled'] | None
    operation: Literal['code_evidence', 'mock_orchestration']


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    next_offset: int | None


@router.get('/{repository_id}/investigations', response_model=HistoryPage)
def history(repository_id: int = Path(gt=0, lt=2**63),
            limit: int = Query(default=20, ge=1, le=50), offset: int = Query(default=0, ge=0, le=10000),
            status: Literal['queued', 'running', 'completed', 'failed', 'cancelled'] | None = None,
            identity: Principal = Depends(principal), db: Session = Depends(get_db),
            github: GitHubClient = Depends(get_github_client)):
    authorize(repository_id, identity, db, github)
    evidence_count = (select(func.count()).select_from(InvestigationEvidence).where(
        InvestigationEvidence.job_id == InvestigationJob.id,
        InvestigationEvidence.repository_id == repository_id,
        InvestigationEvidence.tenant_id == identity.tenant_id).correlate(InvestigationJob).scalar_subquery())
    report_status = (select(InvestigationReportJob.status).where(
        InvestigationReportJob.investigation_id == InvestigationJob.id,
        InvestigationReportJob.repository_id == repository_id,
        InvestigationReportJob.tenant_id == identity.tenant_id,
        InvestigationReportJob.user_id == identity.user_id).correlate(InvestigationJob).scalar_subquery())
    statement = (select(InvestigationJob, Issue.title, evidence_count, report_status)
        .outerjoin(Issue, and_(Issue.id == InvestigationJob.issue_id,
            Issue.number == InvestigationJob.issue_number, Issue.repository_id == repository_id,
            Issue.tenant_id == identity.tenant_id))
        .where(InvestigationJob.tenant_id == identity.tenant_id,
            InvestigationJob.repository_id == repository_id, InvestigationJob.user_id == identity.user_id))
    if status is not None:
        statement = statement.where(InvestigationJob.status == status)
    rows = db.execute(statement.order_by(InvestigationJob.created_at.desc(), InvestigationJob.id.desc())
                      .offset(offset).limit(limit + 1)).all()
    return {'items': [HistoryItem(job_id=job.id, issue_number=job.issue_number, issue_title=title,
        status=job.status, created_at=job.created_at, updated_at=job.updated_at, attempts=job.attempts,
        evidence_count=count, report_status=report, operation=job.operation)
        for job, title, count, report in rows[:limit]],
        'next_offset': offset + limit if len(rows) > limit and offset + limit <= 10000 else None}


def source_excerpt(source: str, identity: Principal, request: Request) -> tuple[str | None, bool]:
    """Bound excerpts and withhold known credentials; this is not a complete secret scanner."""
    settings = get_settings()
    try:
        secrets = [getattr(settings, name).get_secret_value() for name in type(settings).model_fields
                   if isinstance(getattr(settings, name), SecretStr)]
        secrets.extend([identity.token, identity.session_hash, request.cookies.get("rp_session"), request.cookies.get("rp_csrf"),
                        make_url(settings.database_url).password,
                        unquote(urlsplit(settings.redis_url).password or "")])
    except (TypeError, ValueError):
        return None, False
    if contains_sensitive_source(source) or any(secret and secret in source for secret in secrets):
        return None, False
    return source[:SNIPPET_CHARS], len(source) > SNIPPET_CHARS


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
    try:
        validate_snapshot(db, snapshot_id=snapshot.id, repository_id=repository_id,
                          tenant_id=identity.tenant_id, commit=snapshot.commit_sha, lock=True)
    except SnapshotUnavailable:
        raise HTTPException(409, "Repository has no eligible snapshot") from None
    settings = get_settings()
    job = InvestigationJob(id=str(uuid4()), tenant_id=identity.tenant_id, user_id=identity.user_id,
        query_limit=settings.investigation_query_limit, per_query_limit=settings.investigation_per_query_limit,
        evidence_limit=settings.investigation_evidence_limit,
        query_body_limit=min(4000, settings.issue_context_body_chars),
        operation="code_evidence", query_version="terms-v2", snapshot_id=snapshot.id, snapshot_commit_sha=snapshot.commit_sha,
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
        try:
            snapshot = readable_snapshot(db, job, allow_historical=True)
        except (SnapshotUnavailable, InvalidEvidence):
            snapshot = None
        if not snapshot or job.source_repository_name != name:
            retrieval_status = "snapshot_unavailable"
        elif job.status == "completed":
            snapshot_partial = bool(snapshot.skipped_count)
            retrieval_status = job.retrieval_warning or "ready"
        else:
            snapshot_partial = bool(snapshot.skipped_count)
            retrieval_status = job.status
    return {"job_id": job.id, "issue_id": str(job.issue_id), "issue_number": job.issue_number,
            "status": job.status, "attempts": job.attempts,
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
def evidence(request: Request, repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
             include_snippets: bool = False,
             identity: Principal = Depends(principal), db: Session = Depends(get_db),
             github: GitHubClient = Depends(get_github_client)):
    name = authorize(repository_id, identity, db, github)
    # Serialize evidence reads with local session, installation and repository revocation.
    from app.modules.investigation.report_routes import lock_report_read_access
    lock_report_read_access(db, repository_id, identity, name)
    job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == str(job_id),
        InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id,
        InvestigationJob.repository_id == repository_id))
    if not job:
        raise HTTPException(404, "Investigation not found")
    if job.operation != "code_evidence" or job.status != "completed":
        raise HTTPException(409, "Evidence is not available")
    try:
        snapshot = readable_snapshot(db, job, allow_historical=True, lock=True)
    except (SnapshotUnavailable, InvalidEvidence):
        snapshot = None
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
        if include_snippets:
            for result, (_, chunk, _) in zip(items, rows, strict=True):
                snippet, truncated = source_excerpt(chunk.source_text, identity, request)
                result.update(snippet=snippet, snippet_truncated=truncated,
                              snippet_unavailable=snippet is None)
    except ValueError:
        raise HTTPException(409, "Evidence is unavailable") from None
    return {"job_id": job.id, "snapshot_id": snapshot.id, "commit_sha": snapshot.commit_sha,
            "retrieval_status": job.retrieval_warning or "ready", "snapshot_partial": bool(snapshot.skipped_count),
            "query_version": job.query_version, "query_input_truncated": job.query_input_truncated,
            "evidence_count": len(items), "items": items}


@router.get('/{repository_id}/investigations/{job_id}/code-intelligence', response_model=AnalysisResponse)
def code_intelligence(request: Request, repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
                      identity: Principal = Depends(principal), db: Session = Depends(get_db),
                      github: GitHubClient = Depends(get_github_client)):
    """Opt-in analysis of existing evidence; never publishes a job or invokes a model."""
    from app.modules.investigation.code_intelligence import (
        MAX_CHUNK_BYTES, MAX_CHUNKS, MAX_TOTAL_BYTES, AnalysisProcessError, AnalysisTimeout, run_bounded,
    )
    from app.modules.investigation.report_routes import lock_report_read_access, parent_and_snapshot

    if not _analysis_slot.acquire(blocking=False):
        raise HTTPException(429, 'Analysis is busy; try again later')
    try:
        name = authorize(repository_id, identity, db, github)
        parent, _snapshot = parent_and_snapshot(db, repository_id, job_id, identity, name, allow_historical=True)
        number, issue_id, updated = parent.issue_number, parent.issue_id, utc(parent.issue_updated_at)
        db.rollback()  # Do not hold locks or transactions across GitHub requests.
        context = issue_context(repository_id, number, identity, db, github)
        if context['issue_id'] != str(issue_id) or utc(context['updated_at']) != updated:
            raise HTTPException(409, 'Issue changed since the investigation')
        lock_report_read_access(db, repository_id, identity, name)
        parent, snapshot = parent_and_snapshot(db, repository_id, job_id, identity, name,
                                              lock_snapshot=True, allow_historical=True)
        if parent.issue_id != issue_id or utc(parent.issue_updated_at) != updated:
            raise HTTPException(409, 'Issue changed since the investigation')
        try:
            rows = load_verified_evidence(db, parent, snapshot)
            items, citations, source_bytes, omitted = [], {}, 0, False
            for evidence_row, chunk, file in rows:
                if len(items) >= MAX_CHUNKS:
                    omitted = True
                    continue
                excerpt, _truncated = source_excerpt(chunk.source_text, identity, request)
                if excerpt is None:
                    continue
                url = github_citation(name, snapshot.commit_sha, file.path, chunk.start_line, chunk.end_line)
                citation = {'chunk_id': chunk.id, 'path': file.path, 'symbol': chunk.symbol,
                            'start_line': chunk.start_line, 'end_line': chunk.end_line,
                            'snapshot_id': snapshot.id, 'commit_sha': snapshot.commit_sha, 'url': url}
                citations[chunk.id] = citation
                size = len(chunk.source_text.encode('utf-8'))
                if size > MAX_CHUNK_BYTES or source_bytes + size > MAX_TOTAL_BYTES:
                    source = ' ' * (MAX_CHUNK_BYTES + 1)
                else:
                    source, source_bytes = chunk.source_text, source_bytes + size
                items.append({**citation, 'rank': evidence_row.rank, 'source': source})
        except (InvalidEvidence, ValueError):
            raise HTTPException(409, 'Evidence is unavailable') from None
        try:
            result = run_bounded(context['title'], context['body'], items)
        except AnalysisTimeout:
            raise HTTPException(503, 'Analysis timed out') from None
        except (AnalysisProcessError, OSError, RuntimeError):
            raise HTTPException(503, 'Analysis is unavailable') from None
        if omitted and 'evidence_budget' not in result['limitations']:
            result['limitations'].append('evidence_budget')
        for finding in result['findings']:
            finding['citation'] = citations[finding['chunk_id']]
        result.update(job_id=parent.id, repository_id=str(repository_id), snapshot_id=snapshot.id,
                      commit_sha=snapshot.commit_sha)
        return result
    finally:
        _analysis_slot.release()
