"""Authorized proposal operations. A review decision never writes to GitHub."""
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import PatchOutbox, PatchProposal, now
from app.infra.database import get_db
from app.modules.auth.session import Principal, principal, require_csrf
from app.modules.github.client import GitHubClient, get_github_client
from app.modules.github.issue_context import authorize
from app.modules.investigation.report_routes import lock_report_read_access, parent_and_snapshot
from app.modules.investigation.routes import source_excerpt
from app.modules.patches.context import assemble_context
from app.modules.patches.service import (candidate_provider_status, get_candidate_provider,
                                         static_validation_record, verified_patch_digest, verify_saved)
from app.modules.patches.source_coverage import describe_coverage, verified_identity
from app.modules.patches.validation import PatchError

router = APIRouter(prefix="/v1/repositories")
ROOT = "/{repository_id}/investigations/{job_id}/patch-proposals"


class CreateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved_for_review", "rejected"]


def _access(db, repository_id, job_id, identity, github, request=None, *, historical=False, proposal_id=None):
    if request is not None:
        require_csrf(request, identity, db)
        db.rollback()
    name = authorize(repository_id, identity, db, github)
    if proposal_id is not None:
        _enabled()
        # Match the worker's proposal -> session -> installation -> repository lock order.
        task = db.scalar(select(PatchProposal).where(PatchProposal.id == str(proposal_id),
            PatchProposal.investigation_id == str(job_id), PatchProposal.repository_id == repository_id,
            PatchProposal.tenant_id == identity.tenant_id, PatchProposal.user_id == identity.user_id)
            .with_for_update())
        if not task:
            raise HTTPException(404, "Proposal not found")
    if request is not None:
        require_csrf(request, identity, db)
    lock_report_read_access(db, repository_id, identity, name)
    return parent_and_snapshot(db, repository_id, job_id, identity, name, lock_snapshot=True,
                               allow_historical=historical)


def _item(db, proposal_id, parent, identity, *, lock=False):
    statement = select(PatchProposal).where(PatchProposal.id == str(proposal_id),
        PatchProposal.investigation_id == parent.id, PatchProposal.repository_id == parent.repository_id,
        PatchProposal.tenant_id == identity.tenant_id, PatchProposal.user_id == identity.user_id)
    proposal = db.scalar(statement.with_for_update() if lock else statement)
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    return proposal


def _enabled():
    if not get_settings().patch_proposals_enabled:
        raise HTTPException(503, "Patch proposals are disabled")


def _summary(task, db=None, *, validated=False):
    outbox = db.get(PatchOutbox, task.id) if db else None
    unverified = task.status in {"tests_passed", "tests_failed"} and not validated
    return {"id": task.id, "status": "failed" if unverified else task.status, "snapshot_id": task.snapshot_id,
            "commit_sha": task.commit_sha, "review_state": task.review_state,
            "error_code": "test_result_unverified" if unverified else task.error_code,
            "dispatch_status": outbox.status if outbox else None,
            "created_at": task.created_at, "updated_at": task.updated_at}


@router.get(ROOT)
def list_proposals(repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
                   identity: Principal = Depends(principal), db: Session = Depends(get_db),
                   github: GitHubClient = Depends(get_github_client)):
    parent, snapshot = _access(db, repository_id, job_id, identity, github, historical=True)
    enabled = get_settings().patch_proposals_enabled
    if not enabled:
        return {"available": False, "reason": "Patch proposals are disabled.", "items": []}
    if parent.issue_origin_repository_id is not None or snapshot.inventory_coverage == "PARTIAL_INVENTORY":
        return {"available": False, "reason": "Scoped inference approval is not available.", "items": []}
    provider = get_candidate_provider()
    if callable(getattr(provider, "check_readiness", None)):
        # Probe only after releasing locks, then recheck authorization before returning data.
        db.rollback()
        available, reason = candidate_provider_status(provider)
        parent, snapshot = _access(db, repository_id, job_id, identity, github, historical=True)
        if not get_settings().patch_proposals_enabled:
            return {"available": False, "reason": "Patch proposals are disabled.", "items": []}
        if parent.issue_origin_repository_id is not None or snapshot.inventory_coverage == "PARTIAL_INVENTORY":
            return {"available": False, "reason": "Scoped inference approval is not available.", "items": []}
    else:
        available, reason = candidate_provider_status(provider)
    tasks = db.scalars(select(PatchProposal).where(PatchProposal.investigation_id == parent.id,
        PatchProposal.repository_id == repository_id, PatchProposal.tenant_id == identity.tenant_id,
        PatchProposal.user_id == identity.user_id).order_by(PatchProposal.created_at.desc()).limit(50)).all()
    items = []
    for task in tasks:
        verified = False
        if task.status in {"tests_passed", "tests_failed"}:
            try:
                verify_saved(task, assemble_context(db, parent, snapshot), parent.source_repository_name)
                verified = True
            except PatchError:
                pass
        items.append(_summary(task, db, validated=verified))
    return {"available": available, "reason": reason, "items": items}


@router.post(ROOT, status_code=202)
def create_proposal(payload: CreateProposal, request: Request, repository_id: int = Path(gt=0, lt=2**63),
                    job_id: UUID = Path(), identity: Principal = Depends(principal),
                    db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    parent, snapshot = _access(db, repository_id, job_id, identity, github, request)
    _enabled()
    # A separate immutable single-use approval mechanism is required for upstream
    # real-source generation; no route may enqueue or probe a provider before it exists.
    if parent.issue_origin_repository_id is not None or snapshot.inventory_coverage == "PARTIAL_INVENTORY":
        raise HTTPException(409, "Scoped inference approval is not available")
    provider = get_candidate_provider()
    if provider is None:
        raise HTTPException(503, "Patch generation provider is unavailable")
    if callable(getattr(provider, "check_readiness", None)):
        # Release all database locks while checking the provider, then reauthorize.
        db.rollback()
        available, reason = candidate_provider_status(provider)
        if not available:
            raise HTTPException(503, reason)
        parent, snapshot = _access(db, repository_id, job_id, identity, github, request)
        _enabled()
        if parent.issue_origin_repository_id is not None or snapshot.inventory_coverage == "PARTIAL_INVENTORY":
            raise HTTPException(409, "Scoped inference approval is not available")
    try:
        assemble_context(db, parent, snapshot)
    except PatchError:
        raise HTTPException(409, "Verified source evidence is unavailable") from None
    task = db.scalar(select(PatchProposal).where(PatchProposal.investigation_id == parent.id,
        PatchProposal.user_id == identity.user_id, PatchProposal.request_key == str(payload.request_id)))
    if not task:
        owned = (PatchProposal.investigation_id == parent.id, PatchProposal.user_id == identity.user_id,
                 PatchProposal.repository_id == repository_id, PatchProposal.tenant_id == identity.tenant_id)
        total = db.scalar(select(func.count()).select_from(PatchProposal).where(*owned))
        active = db.scalar(select(func.count()).select_from(PatchProposal).where(*owned,
            PatchProposal.status.in_(["queued", "generating", "validation_pending", "validating"])))
        if total >= 20 or active >= 3:
            raise HTTPException(429, "Proposal limit reached")
        task = PatchProposal(id=str(uuid4()), investigation_id=parent.id, snapshot_id=snapshot.id,
            repository_id=repository_id, tenant_id=identity.tenant_id, user_id=identity.user_id,
            session_hash=identity.session_hash, request_key=str(payload.request_id), commit_sha=snapshot.commit_sha)
        db.add(task)
        db.flush()
        db.add(PatchOutbox(proposal_id=task.id, repository_id=repository_id, tenant_id=identity.tenant_id))
    db.flush()
    result = _summary(task, db)
    db.commit()
    return result


def _evidence_coverage(context, evidence):
    """Describe only ranges and complete-file identities independently verified in context."""
    files = {file.path: file for file in context.files}
    refs = {ref.id: ref for ref in context.evidence}
    result = []
    for row in evidence:
        ref = refs[row["id"]]
        file = files[ref.path]
        lines = file.content.splitlines(keepends=True)
        start = sum(len(line) for line in lines[:ref.start_line - 1])
        end = sum(len(line) for line in lines[:ref.end_line])
        description = describe_coverage(identity=file.pinned_identity, snapshot_id=context.snapshot_id,
            commit_sha=context.commit_sha, repository_id=context.repository_id, tenant_id=context.tenant_id,
            file_id=file.file_id, path=file.path, digest=file.sha256, source=file.content,
            start_line=ref.start_line, end_line=ref.end_line, start_byte=start, end_byte=end,
            snippet=file.content[start:end])
        result.append({"evidence_id": ref.id, "path": ref.path, "start_line": ref.start_line,
                       "end_line": ref.end_line, "classification": description["classification"]})
    return result


def _complete_changed_files(context, changed):
    """Export requires a verified complete original identity for every changed file."""
    files = {file.file_id: file for file in context.files}
    for item in changed:
        file = files.get(item.file_id)
        if file is None or not verified_identity(file.pinned_identity, snapshot_id=context.snapshot_id,
                commit_sha=context.commit_sha, repository_id=context.repository_id, tenant_id=context.tenant_id,
                file_id=file.file_id, path=file.path, digest=file.sha256, source=file.content):
            return False
    return bool(changed)


def _export_reason(task, snapshot, digest, complete):
    if not snapshot.published:
        return "source_stale"
    if task.review_state == "rejected":
        return "rejected"
    if task.status not in {"static_validated", "tests_passed", "tests_failed"}:
        return "proposal_not_validated"
    if digest is None:
        return "patch_digest_missing"
    if not complete:
        return "source_identity_unverified"
    return None


@router.get(ROOT + "/{proposal_id}")
def get_proposal(request: Request, repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(), proposal_id: UUID = Path(),
                 identity: Principal = Depends(principal), db: Session = Depends(get_db),
                 github: GitHubClient = Depends(get_github_client)):
    parent, snapshot = _access(db, repository_id, job_id, identity, github, historical=True)
    _enabled()
    task = _item(db, proposal_id, parent, identity)
    result = _summary(task, db)
    if task.diff is not None:
        try:
            context = assemble_context(db, parent, snapshot)
            changed = verify_saved(task, context, parent.source_repository_name)
            digest = verified_patch_digest(task)
            coverage = _evidence_coverage(context, task.evidence)
            reason = _export_reason(task, snapshot, digest, _complete_changed_files(context, changed))
        except PatchError:
            raise HTTPException(409, "Proposal source or evidence is no longer valid") from None
        if (source_excerpt(task.diff, identity, request)[0] is None
                or source_excerpt(task.rationale or "", identity, request)[0] is None):
            raise HTTPException(409, "Proposal content is unavailable")
        result = _summary(task, db, validated=True)
        result.update(diff=task.diff, rationale=task.rationale, provider=task.provider, model=task.model,
                      evidence=task.evidence, changed_files=task.changed_files,
                      static_result=task.static_result, test_result=task.test_result,
                      patch_sha256=digest, source_coverage=coverage, source_stale=not snapshot.published,
                      export_available=reason is None, export_reason=reason,
                      reviewer_id=task.reviewer_id, reviewed_at=task.reviewed_at)
    return result


@router.get(ROOT + "/{proposal_id}/export")
def export_proposal(request: Request, expected_sha256: str = Query(alias="sha256", pattern=r"^[0-9a-f]{64}$"),
                    repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
                    proposal_id: UUID = Path(), identity: Principal = Depends(principal),
                    db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    parent, snapshot = _access(db, repository_id, job_id, identity, github, proposal_id=proposal_id)
    _enabled()
    task = _item(db, proposal_id, parent, identity)
    if task.status not in {"static_validated", "tests_passed", "tests_failed"} or task.review_state == "rejected":
        raise HTTPException(409, "Proposal is not available for export")
    try:
        context = assemble_context(db, parent, snapshot)
        changed = verify_saved(task, context, parent.source_repository_name)
        digest = verified_patch_digest(task)
        if not _complete_changed_files(context, changed):
            raise PatchError("source_identity_unverified")
    except PatchError:
        raise HTTPException(409, "Proposal source or evidence is no longer valid") from None
    if digest is None or digest != expected_sha256:
        raise HTTPException(409, "Patch changed or requires a static recheck")
    if source_excerpt(task.diff, identity, request)[0] is None:
        raise HTTPException(409, "Proposal content is unavailable")
    return Response(content=task.diff.encode("utf-8"), media_type="text/x-diff", headers={
        "Content-Disposition": f'attachment; filename="repopilot-{proposal_id}.patch"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "X-Patch-SHA256": digest, "X-Source-Commit": snapshot.commit_sha,
        "X-Source-Snapshot": snapshot.id,
    })


@router.post(ROOT + "/{proposal_id}/static-validation")
def static_validation(request: Request, repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
                      proposal_id: UUID = Path(), identity: Principal = Depends(principal),
                      db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    parent, snapshot = _access(db, repository_id, job_id, identity, github, request, proposal_id=proposal_id)
    _enabled()
    task = _item(db, proposal_id, parent, identity, lock=True)
    if task.status not in {"static_validated", "tests_passed", "tests_failed"} or task.review_state == "rejected":
        raise HTTPException(409, "Proposal is not available for validation")
    try:
        verify_saved(task, assemble_context(db, parent, snapshot), parent.source_repository_name)
    except PatchError:
        raise HTTPException(409, "Proposal source or evidence is no longer valid") from None
    task.static_result = static_validation_record(task.diff)
    task.updated_at = now()
    db.commit()
    return task.static_result


@router.post(ROOT + "/{proposal_id}/test-validation", status_code=202)
def test_validation(request: Request, repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
                    proposal_id: UUID = Path(), identity: Principal = Depends(principal),
                    db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    parent, snapshot = _access(db, repository_id, job_id, identity, github, request, proposal_id=proposal_id)
    _enabled()
    task = _item(db, proposal_id, parent, identity, lock=True)
    if task.status in {"validation_pending", "validating"}:
        return _summary(task, db)
    if task.status not in {"static_validated", "tests_passed", "tests_failed"} or task.review_state == "rejected":
        raise HTTPException(409, "Proposal is not available for validation")
    try:
        verify_saved(task, assemble_context(db, parent, snapshot), parent.source_repository_name)
    except PatchError:
        raise HTTPException(409, "Proposal source or evidence is no longer valid") from None
    task.status, task.attempts, task.updated_at = "validation_pending", 0, now()
    task.test_result = {"status": "pending", "sandbox_used": False, "tests_run": []}
    outbox = db.get(PatchOutbox, task.id)
    if not outbox:
        raise HTTPException(409, "Proposal outbox unavailable")
    outbox.status, outbox.attempts, outbox.next_dispatch_at = "pending", 0, now()
    result = _summary(task, db)
    db.commit()
    return result


@router.post(ROOT + "/{proposal_id}/review")
def review(payload: ReviewDecision, request: Request, repository_id: int = Path(gt=0, lt=2**63),
           job_id: UUID = Path(), proposal_id: UUID = Path(), identity: Principal = Depends(principal),
           db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    parent, snapshot = _access(db, repository_id, job_id, identity, github, request, proposal_id=proposal_id)
    _enabled()
    task = _item(db, proposal_id, parent, identity, lock=True)
    if (task.review_state != "unreviewed" or task.status not in
            {"queued", "generating", "static_validated", "validation_pending", "validating", "tests_passed", "tests_failed"}
            or (payload.decision == "approved_for_review" and task.status not in {"static_validated", "tests_passed", "tests_failed"})):
        raise HTTPException(409, "Proposal is not available for review")
    if task.diff is not None:
        try:
            verify_saved(task, assemble_context(db, parent, snapshot), parent.source_repository_name)
        except PatchError:
            raise HTTPException(409, "Proposal source or evidence is no longer valid") from None
    elif payload.decision == "approved_for_review":
        raise HTTPException(409, "Proposal is not available for review")
    if payload.decision == "rejected" and task.status not in {"static_validated", "tests_passed", "tests_failed"}:
        task.status = "static_validated" if task.diff is not None else "failed"
        task.error_code = "reviewer_cancelled"
        task.lease_token = task.lease_expires_at = None
        if task.diff is not None:
            task.test_result = {"status": "cancelled", "sandbox_used": False, "tests_run": []}
        outbox = db.get(PatchOutbox, task.id)
        if outbox:
            outbox.status = "processed"
    task.review_state, task.reviewer_id, task.reviewed_at, task.updated_at = payload.decision, identity.user_id, now(), now()
    result = _summary(task, db, validated=task.diff is not None)
    db.commit()
    return result
