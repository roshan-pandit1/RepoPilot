"""Tenant-authorized read-only pull-request review requests and feedback."""
import re
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import PRFindingFeedback, PRReview, PRReviewFinding, PRReviewOutbox, Repository, now
from app.infra.database import get_db
from app.modules.auth.session import Principal, principal, require_csrf, utc
from app.modules.github.client import GitHubClient, GitHubFailure, HttpGitHubClient, get_github_client
from app.modules.github.issue_context import authorize_review as authorize
from app.modules.github.installation_token import invalidate_review_token, review_token
from app.modules.investigation.report_routes import lock_report_read_access
from app.modules.pr_review.core import identity_tuple, review_identity, active_policy_hash, PullClient, pull_identity

router = APIRouter(prefix="/v1/repositories")
ROOT = "/{repository_id}/pr-reviews"
_URL = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)\Z")


class CreateReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=1024)


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["useful", "false_positive", "acknowledged"]
    reason: str | None = Field(default=None, max_length=500)


def parse_url(url: str, repository: str) -> int:
    match = _URL.fullmatch(url)
    if not match or f"{match[1]}/{match[2]}" != repository:
        raise HTTPException(422, "Invalid pull request URL for this repository")
    number = int(match[3])
    if number >= 2**31:
        raise HTTPException(422, "Invalid pull request URL for this repository")
    return number


def _enabled():
    if not get_settings().pr_reviews_enabled:
        raise HTTPException(503, "Pull request reviews are disabled")


def _access(db, repo_id, identity, github, request=None, *, lock=True):
    _enabled()
    if request is not None:
        require_csrf(request, identity, db)
        db.rollback()
    name = authorize(repo_id, identity, db, github)
    if request is not None:
        require_csrf(request, identity, db)
    if lock:
        lock_report_read_access(db, repo_id, identity, name)
    return name


def _item(db, repo_id, review_id, identity, *, lock=False):
    query = select(PRReview).where(PRReview.id == str(review_id), PRReview.repository_id == repo_id,
                                   PRReview.tenant_id == identity.tenant_id)
    item = db.scalar(query.with_for_update() if lock else query)
    if not item:
        raise HTTPException(404, "Review not found")
    return item


def _stale(item, name, identity, github, db):
    if item.status != "completed":
        return item.status == "stale"
    client = PullClient(4) if type(github) is HttpGitHubClient else github
    try:
        repo = db.get(Repository, item.repository_id)
        if not repo or repo.tenant_id != identity.tenant_id:
            raise GitHubFailure("authorization_revoked")
        token = review_token(identity, repo.installation_id, repo.id)
        data = pull_identity(client.pull(token, name, item.number), item.repository_id, name, item.number)
    except GitHubFailure as exc:
        if repo and str(exc) in {"github_authentication_failed", "github_permission_denied", "github_not_found"}:
            try:
                invalidate_review_token(repo.installation_id, repo.id)
            except GitHubFailure:
                pass
        raise HTTPException(503, "Pull request state cannot be verified") from None
    except (AttributeError, TypeError, ValueError):
        raise HTTPException(503, "Pull request state cannot be verified") from None
    return identity_tuple(data) != review_identity(item, name)


def _summary(item):
    return {"id": item.id, "repository_id": str(item.repository_id), "number": item.number,
            "status": item.status, "title": item.title, "base_sha": item.base_sha,
            "head_sha": item.head_sha, "head_repository_id": str(item.head_repository_id) if item.head_repository_id else None,
            "head_repository_name": item.head_repository_name, "coverage": item.coverage, "error_code": item.error_code,
            "next_retry_at": item.next_retry_at,
            "created_at": item.created_at, "updated_at": item.updated_at}


@router.post(ROOT, status_code=202)
def create_review(payload: CreateReview, request: Request, repository_id: int = Path(gt=0, lt=2**63),
                  identity: Principal = Depends(principal), db: Session = Depends(get_db),
                  github: GitHubClient = Depends(get_github_client)):
    name = _access(db, repository_id, identity, github, request, lock=False)
    number = parse_url(payload.url, name)
    # The selected repository was authorized above; do not accept an installation ID from the client.
    repo = db.get(Repository, repository_id)
    if not repo or repo.tenant_id != identity.tenant_id:
        raise HTTPException(404, "Repository not found")
    installation_id = repo.installation_id
    # Release transaction locks before GitHub I/O, then reauthorize before writing.
    db.rollback()
    client = PullClient(4) if type(github) is HttpGitHubClient else github
    try:
        token = review_token(identity, installation_id, repository_id)
        pinned = pull_identity(client.pull(token, name, number), repository_id, name, number)
    except GitHubFailure as exc:
        if str(exc) in {"github_authentication_failed", "github_permission_denied", "github_not_found"}:
            try:
                invalidate_review_token(installation_id, repository_id)
            except GitHubFailure:
                pass
        errors = {
            "github_authentication_failed": (401, "GitHub authorization expired or is invalid"),
            "github_permission_denied": (403, "GitHub permission is insufficient"),
            "github_not_found": (404, "Pull request not found"),
            "github_rate_limited": (503, "GitHub rate limit reached"),
            "github_secondary_rate_limited": (503, "GitHub rate limit reached"),
            "github_temporarily_unavailable": (503, "GitHub is temporarily unavailable"),
        }
        status, detail = errors.get(str(exc), (503, "Pull request identity could not be verified"))
        raise HTTPException(status, detail) from None
    except (AttributeError, TypeError, ValueError):
        raise HTTPException(503, "Pull request identity could not be verified") from None
    if _access(db, repository_id, identity, github, request) != name:
        raise HTTPException(404, "Repository not found")
    # The repository lock acquired by _access serializes duplicate requests.
    existing = db.scalar(select(PRReview).where(PRReview.repository_id == repository_id,
        PRReview.tenant_id == identity.tenant_id, PRReview.user_id == identity.user_id,
        PRReview.number == number, PRReview.github_pr_id == pinned["id"],
        PRReview.base_sha == pinned["base_sha"], PRReview.head_sha == pinned["head_sha"],
        or_(and_(PRReview.head_repository_id == pinned["head_repository_id"],
                 PRReview.head_repository_name == pinned["head_repository_name"]),
            and_(PRReview.head_repository_id.is_(None), PRReview.head_repository_name.is_(None),
                 pinned["head_repository_id"] == repository_id, pinned["head_repository_name"] == name)),
        PRReview.status.in_(("queued", "running"))).limit(1))
    if existing:
        return _summary(existing)
    review = PRReview(id=str(uuid4()), repository_id=repository_id, tenant_id=identity.tenant_id,
        user_id=identity.user_id, session_hash=identity.session_hash, request_key=str(uuid4()),
        number=number, status="queued", attempts=0, policy_sha256=active_policy_hash(),
        github_pr_id=pinned["id"], base_sha=pinned["base_sha"], head_sha=pinned["head_sha"],
        title=pinned["title"], author=pinned["author"],
        head_repository_id=pinned["head_repository_id"], head_repository_name=pinned["head_repository_name"])
    db.add(review)
    db.flush()
    db.add(PRReviewOutbox(review_id=review.id, repository_id=repository_id,
                          tenant_id=identity.tenant_id, status="pending", attempts=0))
    result = _summary(review)
    db.commit()
    return result


@router.get(ROOT)
def list_reviews(repository_id: int = Path(gt=0, lt=2**63), identity: Principal = Depends(principal),
                 db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    _access(db, repository_id, identity, github)
    items = db.scalars(select(PRReview).where(PRReview.repository_id == repository_id,
        PRReview.tenant_id == identity.tenant_id).order_by(PRReview.created_at.desc()).limit(100)).all()
    return {"items": [_summary(item) for item in items]}


@router.get(ROOT + "/{review_id}")
def review_detail(repository_id: int = Path(gt=0, lt=2**63), review_id: UUID = Path(),
                  identity: Principal = Depends(principal), db: Session = Depends(get_db),
                  github: GitHubClient = Depends(get_github_client)):
    name = _access(db, repository_id, identity, github, lock=False)
    item = _item(db, repository_id, review_id, identity)
    stale = _stale(item, name, identity, github, db)
    if authorize(repository_id, identity, db, github) != name:
        raise HTTPException(404, "Repository not found")
    lock_report_read_access(db, repository_id, identity, name)
    item = _item(db, repository_id, review_id, identity)
    findings = db.scalars(select(PRReviewFinding).where(PRReviewFinding.review_id == item.id,
        PRReviewFinding.repository_id == repository_id, PRReviewFinding.tenant_id == identity.tenant_id)
        .order_by(PRReviewFinding.path, PRReviewFinding.start_line).limit(500)).all()
    result = []
    for finding in findings:
        feedback = db.get(PRFindingFeedback, (finding.id, identity.user_id))
        result.append({"id": finding.id, "rule_id": finding.rule_id, "category": finding.category,
            "severity": finding.severity, "confidence": finding.confidence, "path": finding.path,
            "start_line": finding.start_line, "end_line": finding.end_line,
            "explanation": finding.explanation, "recommendation": finding.recommendation,
            "evidence": finding.evidence, "feedback_state": feedback.state if feedback else None,
            "feedback_reason": feedback.reason if feedback else None})
    files = item.files if isinstance(item.files, list) else []
    checked = sum(isinstance(entry, dict) and entry.get("coverage") == "complete" for entry in files)
    elapsed = (max(0.0, (utc(item.updated_at) - utc(item.created_at)).total_seconds())
               if item.status in {"completed", "failed"} else None)
    # Aggregate only data already authorized for this user; no source or prompts in metrics.
    metrics = {"status": item.status, "time_to_result_seconds": elapsed,
               "recorded_files_checked": checked, "recorded_files_not_fully_checked": len(files) - checked,
               "findings_returned": len(result),
               "useful_feedback": sum(entry["feedback_state"] == "useful" for entry in result),
               "dismissed_feedback": sum(entry["feedback_state"] == "false_positive" for entry in result),
               "findings_opened": None, "patches_opened": None,
               "model_invocations": None, "compute_cost": None}
    return {**_summary(item), "stale": stale, "files": files,
            "limitations": item.limitations or [], "findings": result, "pilot_metrics": metrics}


@router.post(ROOT + "/{review_id}/findings/{finding_id}/feedback")
def feedback(payload: Feedback, request: Request, repository_id: int = Path(gt=0, lt=2**63),
             review_id: UUID = Path(), finding_id: UUID = Path(), identity: Principal = Depends(principal),
             db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    _enabled()
    require_csrf(request, identity, db)
    db.rollback()
    name = authorize(repository_id, identity, db, github)
    preview = _item(db, repository_id, review_id, identity)
    if preview.status != "completed" or _stale(preview, name, identity, github, db):
        raise HTTPException(409, "Review is not current")
    checked = review_identity(preview, name)
    if authorize(repository_id, identity, db, github) != name:
        raise HTTPException(404, "Repository not found")
    # Match the worker lock order, and never hold locks across GitHub requests.
    item = _item(db, repository_id, review_id, identity, lock=True)
    require_csrf(request, identity, db)
    lock_report_read_access(db, repository_id, identity, name)
    if item.status != "completed" or review_identity(item, name) != checked:
        raise HTTPException(409, "Review is not current")
    finding = db.scalar(select(PRReviewFinding).where(PRReviewFinding.id == str(finding_id),
        PRReviewFinding.review_id == item.id, PRReviewFinding.repository_id == repository_id,
        PRReviewFinding.tenant_id == identity.tenant_id))
    if not finding:
        raise HTTPException(404, "Finding not found")
    entry = db.get(PRFindingFeedback, (finding.id, identity.user_id))
    if not entry:
        entry = PRFindingFeedback(finding_id=finding.id, user_id=identity.user_id, review_id=item.id,
                                  repository_id=repository_id, tenant_id=identity.tenant_id,
                                  state=payload.state)
        db.add(entry)
    entry.state, entry.reason, entry.updated_at = payload.state, payload.reason, now()
    db.commit()
    return {"state": payload.state}
