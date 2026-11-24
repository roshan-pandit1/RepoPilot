"""Authenticated, read-only mock-investigation orchestration endpoints."""
from uuid import UUID, uuid4
from urllib.parse import quote, unquote, urlsplit
import re

from datetime import datetime
from threading import BoundedSemaphore
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import and_, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.domain.models import (CodeSnapshot, Installation, Issue,
                               InvestigationEvidence, InvestigationIssueOrigin, InvestigationJob, InvestigationOutbox,
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


class UpstreamFileSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, max_length=512)
    byte_length: int = Field(gt=0, le=100_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_blob_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")


class UpstreamPartialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    parent_repository_id: int = Field(gt=0, lt=2**63)
    issue_id: int = Field(gt=0, lt=2**63)
    issue_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    branch: str = Field(min_length=1, max_length=255)
    files: list[UpstreamFileSpec] = Field(min_length=1, max_length=5)


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
    issue_origin: dict | None = None


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
    statement = (select(InvestigationJob, Issue.title, evidence_count, report_status, InvestigationIssueOrigin)
        .outerjoin(Issue, and_(Issue.id == InvestigationJob.issue_id,
            Issue.number == InvestigationJob.issue_number, Issue.repository_id == repository_id,
            Issue.tenant_id == identity.tenant_id))
        .outerjoin(InvestigationIssueOrigin, and_(InvestigationIssueOrigin.job_id == InvestigationJob.id,
            InvestigationIssueOrigin.repository_id == repository_id,
            InvestigationIssueOrigin.tenant_id == identity.tenant_id))
        .where(InvestigationJob.tenant_id == identity.tenant_id,
            InvestigationJob.repository_id == repository_id, InvestigationJob.user_id == identity.user_id))
    if status is not None:
        statement = statement.where(InvestigationJob.status == status)
    rows = db.execute(statement.order_by(InvestigationJob.created_at.desc(), InvestigationJob.id.desc())
                      .offset(offset).limit(limit + 1)).all()
    items = []
    for job, title, count, report, origin in rows[:limit]:
        saved = _saved_upstream(job, origin, job.source_repository_name)
        items.append(HistoryItem(job_id=job.id, issue_number=job.issue_number,
            issue_title=origin.issue_title if saved else title, status=job.status,
            created_at=job.created_at, updated_at=job.updated_at, attempts=job.attempts,
            evidence_count=count, report_status=report, operation=job.operation,
            issue_origin=_origin_response(saved) if saved else None))
    return {'items': items,
        'next_offset': offset + limit if len(rows) > limit and offset + limit <= 10000 else None}


def _saved_upstream(job, origin, target_name):
    from app.modules.github.upstream_issue import VerifiedUpstreamIssue, _valid_name

    if job.issue_origin_repository_id is None:
        if origin is not None:
            raise HTTPException(409, "Upstream issue identity is unavailable")
        return None
    if (not origin or not isinstance(target_name, str) or job.source_repository_name != target_name
            or origin.repository_id != job.repository_id or origin.tenant_id != job.tenant_id
            or origin.origin_repository_id != job.issue_origin_repository_id
            or origin.issue_id != job.issue_id or origin.issue_number != job.issue_number
            or origin.relationship != "direct_public_parent" or utc(origin.issue_updated_at) != utc(job.issue_updated_at)
            or not _valid_name(origin.origin_repository_name)
            or origin.issue_url != "https://github.com/" + "/".join(quote(part, safe="") for part in
                origin.origin_repository_name.split("/")) + f"/issues/{origin.issue_number}"
            or not isinstance(origin.issue_body_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", origin.issue_body_sha256)):

        raise HTTPException(409, "Upstream issue identity is unavailable")
    try:
        return VerifiedUpstreamIssue(job.repository_id, target_name, origin.origin_repository_id,
            origin.origin_repository_name, origin.issue_id, origin.issue_number, origin.issue_url,
            origin.issue_title, origin.issue_body_sha256, utc(origin.issue_updated_at), utc(origin.verified_at), "")
    except (TypeError, ValueError):
        raise HTTPException(409, "Upstream issue identity is unavailable") from None


def _origin_response(saved):
    return {"repository_id": str(saved.origin_repository_id), "repository": saved.origin_repository_name,
            "issue_id": str(saved.issue_id), "issue_number": saved.issue_number, "url": saved.issue_url,
            "relationship": saved.relationship, "verified_at": saved.verified_at}


def _refresh_upstream(saved, identity, github):
    from app.modules.github.client import GitHubFailure, HttpGitHubClient
    from app.modules.github.issue_context_client import IssueContextClient
    from app.modules.github.upstream_issue import revalidate_direct_parent_issue

    client = IssueContextClient(get_settings().issue_context_max_requests) if type(github) is HttpGitHubClient else github
    try:
        return revalidate_direct_parent_issue(client, identity.token, saved)
    except GitHubFailure as exc:
        if str(exc) in {"upstream_identity_invalid", "upstream_relationship_invalid", "upstream_issue_invalid",
                        "upstream_issue_changed", "github_not_found"}:
            raise HTTPException(409, "Upstream issue identity changed or is unavailable") from None
        raise HTTPException(503, "GitHub verification unavailable") from None


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
        InvestigationJob.issue_origin_repository_id.is_(None), InvestigationJob.issue_number == issue_number,
        InvestigationJob.status.in_(["queued", "running"])))
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


@router.post("/{repository_id}/upstream-issues/{issue_number}/investigations", status_code=202)
def submit_upstream_partial(payload: UpstreamPartialRequest, request: Request,
                            repository_id: int = Path(gt=0, lt=2**63),
                            issue_number: int = Path(gt=0, lt=2**31),
                            identity: Principal = Depends(principal), db: Session = Depends(get_db),
                            github: GitHubClient = Depends(get_github_client)):
    """Create a parent-issue investigation against a strictly pinned partial inventory.

    Parent identity and every selected commit/blob are independently read from GitHub;
    the caller's fingerprints are constraints, never a source of authority.
    No provider or code-execution task is created here.
    """
    from app.modules.github.client import GitHubFailure, HttpGitHubClient
    from app.modules.github.issue_context_client import IssueContextClient
    from app.modules.github.source_client import GitHubSourceClient
    from app.modules.github.upstream_issue import read_direct_parent_issue, revalidate_direct_parent_issue
    from app.modules.ingestion.code_collect import CollectionError, collect_source
    from app.modules.ingestion.code_persistence import bind_partial_snapshot, persist_partial_snapshot
    from app.modules.ingestion.partial_snapshot import PartialSnapshotError, build_partial_manifest, plan_pinned_partial
    from app.modules.investigation.report_routes import lock_report_read_access

    require_csrf(request, identity, db)
    db.rollback()
    target_name = authorize(repository_id, identity, db, github)
    db.rollback()
    issue_client = IssueContextClient(get_settings().issue_context_max_requests) if type(github) is HttpGitHubClient else github
    source_client = GitHubSourceClient(max_requests=80, max_seconds=60) if type(github) is HttpGitHubClient else github
    specs = {entry.path: entry for entry in payload.files}
    if len(specs) != len(payload.files):
        raise HTTPException(422, "Duplicate source path")
    try:
        upstream = read_direct_parent_issue(issue_client, identity.token, repository_id, target_name,
            issue_number, expected_parent_id=payload.parent_repository_id, expected_issue_id=payload.issue_id)
        if upstream.issue_body_sha256 != payload.issue_body_sha256:
            raise PartialSnapshotError("upstream_issue_changed")
        plan = plan_pinned_partial(source_client, identity.token, repository_id=repository_id,
            repository_full_name=target_name, commit_sha=payload.commit_sha, paths=tuple(specs),
            expected_branch=payload.branch)
        for candidate in plan.files:
            spec = specs[candidate.path]
            if candidate.blob_sha != spec.git_blob_sha1 or candidate.size != spec.byte_length:
                raise PartialSnapshotError("partial_source_identity_invalid")
        collection = collect_source(source_client, identity.token, target_name, plan,
                                    max_total_bytes=256 * 1024, text_only=True)
        if any(item.content_hash != specs[item.path].sha256 for item in collection.files):
            raise PartialSnapshotError("partial_source_identity_invalid")
        manifest, digest = build_partial_manifest(repository_id=repository_id, tenant_id=identity.tenant_id,
            repository_full_name=target_name, plan=plan, collection=collection)
        revalidate_direct_parent_issue(issue_client, identity.token, upstream)
    except GitHubFailure as exc:
        if str(exc) in {"upstream_identity_invalid", "upstream_relationship_invalid", "upstream_issue_invalid",
                        "upstream_issue_changed", "github_not_found"}:
            raise HTTPException(409, "Upstream issue identity could not be verified") from None
        raise HTTPException(503, "GitHub verification unavailable") from None
    except (PartialSnapshotError, CollectionError, ValueError):
        raise HTTPException(409, "Pinned source identity could not be verified") from None
    if authorize(repository_id, identity, db, github) != target_name:
        raise HTTPException(404, "Repository not found")
    require_csrf(request, identity, db)
    lock_report_read_access(db, repository_id, identity, target_name)
    repo = db.scalar(select(Repository).where(Repository.id == repository_id,
        Repository.tenant_id == identity.tenant_id).with_for_update())
    if not repo or not repo.enabled or repo.full_name != target_name:
        raise HTTPException(404, "Repository not found")
    active = db.scalar(select(InvestigationJob).where(InvestigationJob.tenant_id == identity.tenant_id,
        InvestigationJob.user_id == identity.user_id, InvestigationJob.repository_id == repository_id,
        InvestigationJob.issue_origin_repository_id == upstream.origin_repository_id,
        InvestigationJob.issue_number == issue_number, InvestigationJob.status.in_(["queued", "running"]))
        .with_for_update())
    if active:
        old_origin = db.get(InvestigationIssueOrigin, active.id)
        old_snapshot = db.get(CodeSnapshot, active.snapshot_id)
        if (not old_origin or old_origin.issue_id != upstream.issue_id
                or old_origin.issue_body_sha256 != upstream.issue_body_sha256
                or old_origin.issue_title != upstream.issue_title
                or utc(old_origin.issue_updated_at) != utc(upstream.issue_updated_at)
                or not old_snapshot or active.snapshot_commit_sha != payload.commit_sha
                or old_snapshot.inventory_manifest_sha256 != digest or old_snapshot.inventory_manifest != manifest):
            raise HTTPException(409, "An investigation with a different identity is already active")
        db.commit()
        return {"job_id": active.id, "status": active.status}
    snapshot = persist_partial_snapshot(db, repo, plan, collection)
    settings = get_settings()
    job = InvestigationJob(id=str(uuid4()), tenant_id=identity.tenant_id, user_id=identity.user_id,
        query_limit=settings.investigation_query_limit, per_query_limit=settings.investigation_per_query_limit,
        evidence_limit=settings.investigation_evidence_limit,
        query_body_limit=min(4000, settings.issue_context_body_chars), operation="code_evidence",
        query_version="terms-v2", snapshot_id=snapshot.id, snapshot_commit_sha=snapshot.commit_sha,
        source_repository_name=target_name, repository_id=repository_id, session_hash=identity.session_hash,
        issue_id=upstream.issue_id, issue_number=upstream.issue_number,
        issue_origin_repository_id=upstream.origin_repository_id, issue_updated_at=upstream.issue_updated_at,
        context_retrieved_at=upstream.verified_at)
    db.add(job)
    db.flush()
    bind_partial_snapshot(db, job, snapshot)
    db.add(InvestigationIssueOrigin(job_id=job.id, repository_id=repository_id, tenant_id=identity.tenant_id,
        origin_repository_id=upstream.origin_repository_id, origin_repository_name=upstream.origin_repository_name,
        issue_id=upstream.issue_id, issue_number=upstream.issue_number, issue_url=upstream.issue_url,
        issue_title=upstream.issue_title, issue_body_sha256=upstream.issue_body_sha256,
        issue_updated_at=upstream.issue_updated_at, verified_at=upstream.verified_at,
        relationship=upstream.relationship))
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
    upstream = db.get(InvestigationIssueOrigin, job.id)
    saved = _saved_upstream(job, upstream, name)
    if saved:
        db.rollback()
        _refresh_upstream(saved, identity, github)
        if authorize(repository_id, identity, db, github) != name:
            raise HTTPException(404, "Repository not found")
        job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == str(job_id),
            InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id,
            InvestigationJob.repository_id == repository_id).execution_options(populate_existing=True))
        if not job or _saved_upstream(job, db.get(InvestigationIssueOrigin, job.id), name) != saved:
            raise HTTPException(409, "Upstream issue identity changed or is unavailable")
    if job.operation == "code_evidence":
        try:
            snapshot = readable_snapshot(db, job, allow_historical=True)
        except (SnapshotUnavailable, InvalidEvidence):
            snapshot = None
        if not snapshot or job.source_repository_name != name:
            retrieval_status = "snapshot_unavailable"
        elif job.status == "completed":
            snapshot_partial = snapshot.inventory_coverage == "PARTIAL_INVENTORY" or bool(snapshot.skipped_count)
            retrieval_status = job.retrieval_warning or "ready"
        else:
            snapshot_partial = snapshot.inventory_coverage == "PARTIAL_INVENTORY" or bool(snapshot.skipped_count)
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
            "issue_origin": _origin_response(saved) if saved else None,
            "snapshot_inventory": ({"classification": snapshot.inventory_coverage,
                "manifest_sha256": snapshot.inventory_manifest_sha256,
                "files": snapshot.inventory_manifest.get("files", []) if snapshot.inventory_manifest else []}
                if job.operation == "code_evidence" and snapshot else None),
            "retrieval_limits": {"queries": job.query_limit, "per_query": job.per_query_limit,
                                 "evidence": job.evidence_limit, "body_chars": job.query_body_limit} if job.operation == "code_evidence" else None}


@router.get("/{repository_id}/investigations/{job_id}/upstream-context")
def upstream_context(repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
                     identity: Principal = Depends(principal), db: Session = Depends(get_db),
                     github: GitHubClient = Depends(get_github_client)):
    from app.modules.github.issue_context import build_context
    from app.modules.investigation.report_routes import lock_report_read_access

    name = authorize(repository_id, identity, db, github)
    job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == str(job_id),
        InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id,
        InvestigationJob.repository_id == repository_id))
    if not job:
        raise HTTPException(404, "Investigation not found")
    saved = _saved_upstream(job, db.get(InvestigationIssueOrigin, job.id), name)
    if saved is None:
        raise HTTPException(404, "Upstream issue not found")
    db.rollback()
    fresh = _refresh_upstream(saved, identity, github)
    if fresh.issue_data is None or authorize(repository_id, identity, db, github) != name:
        raise HTTPException(404, "Investigation not found")
    lock_report_read_access(db, repository_id, identity, name)
    job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == str(job_id),
        InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id,
        InvestigationJob.repository_id == repository_id).execution_options(populate_existing=True))
    if not job or _saved_upstream(job, db.get(InvestigationIssueOrigin, job.id), name) != saved:
        raise HTTPException(409, "Upstream issue identity changed or is unavailable")
    try:
        readable_snapshot(db, job, allow_historical=True, lock=True)
    except (SnapshotUnavailable, InvalidEvidence):
        raise HTTPException(409, "Snapshot is no longer available") from None
    return build_context(fresh.issue_data.model_dump(mode="json"), [], repository_id,
                         saved.origin_repository_name, saved.issue_number, get_settings())


@router.get("/{repository_id}/investigations/{job_id}/evidence")
def evidence(request: Request, repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
             include_snippets: bool = False,
             identity: Principal = Depends(principal), db: Session = Depends(get_db),
             github: GitHubClient = Depends(get_github_client)):
    name = authorize(repository_id, identity, db, github)
    job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == str(job_id),
        InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id,
        InvestigationJob.repository_id == repository_id))
    if not job:
        raise HTTPException(404, "Investigation not found")
    saved = _saved_upstream(job, db.get(InvestigationIssueOrigin, job.id), name)
    if saved:
        db.rollback()
        _refresh_upstream(saved, identity, github)
        if authorize(repository_id, identity, db, github) != name:
            raise HTTPException(404, "Repository not found")
    # Serialize evidence reads with local session, installation and repository revocation.
    from app.modules.investigation.report_routes import lock_report_read_access
    lock_report_read_access(db, repository_id, identity, name)
    job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == str(job_id),
        InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id,
        InvestigationJob.repository_id == repository_id).execution_options(populate_existing=True))
    if not job or _saved_upstream(job, db.get(InvestigationIssueOrigin, job.id), name) != saved:
        raise HTTPException(409, "Upstream issue identity changed or is unavailable")
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
            "retrieval_status": job.retrieval_warning or "ready", "snapshot_partial": snapshot.inventory_coverage == "PARTIAL_INVENTORY" or bool(snapshot.skipped_count),
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
