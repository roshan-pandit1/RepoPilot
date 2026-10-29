"""Read-only, bounded issue context; all GitHub text is untrusted data."""
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import AwareDatetime, BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.v1.routes import visible_repos
from app.core.config import get_settings
from app.domain.models import AuthSession, Membership, Repository, now
from app.infra.database import get_db
from app.modules.auth.session import Principal, principal, utc
from app.modules.github.client import GitHubClient, GitHubFailure, HttpGitHubClient, get_github_client
from app.modules.github.enrollment import visible_github_repositories
from app.modules.github.issue_context_client import IssueContextClient

router = APIRouter(prefix="/v1/repositories")


class IssueData(BaseModel):
    id: int = Field(strict=True, gt=0, lt=2**63)
    number: int = Field(strict=True, gt=0, lt=2**31)
    title: str = Field(max_length=100_000)
    body: str | None = Field(default=None, max_length=900_000)
    state: Literal["open", "closed"]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    comments: int = Field(strict=True, ge=0)
    labels: list[dict] = Field(max_length=1000)


class CommentData(BaseModel):
    id: int = Field(strict=True, gt=0, lt=2**63)
    body: str | None = Field(default=None, max_length=900_000)
    created_at: AwareDatetime
    updated_at: AwareDatetime



class ContextComment(BaseModel):
    id: str
    body: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
    truncated: bool


class ContextTruncation(BaseModel):
    title: bool
    body: bool
    labels: bool
    comments: bool
    total: bool


class IssueContextResponse(BaseModel):
    repository_id: str
    issue_id: str
    number: int
    title: str
    body: str
    state: Literal["open", "closed"]
    labels: list[str]
    comments: list[ContextComment]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    retrieved_at: AwareDatetime
    url: str
    truncation: ContextTruncation

def authorize(repo_id, identity, db, github):
    if identity.demo or not identity.session_hash:
        raise HTTPException(404, "Repository not found")
    db.expire_all()
    session = db.get(AuthSession, identity.session_hash)
    if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
            or session.tenant_id != identity.tenant_id or session.user_id != identity.user_id
            or not db.get(Membership, (identity.tenant_id, identity.user_id))):
        raise HTTPException(401, "Authentication required")
    repo = db.scalar(visible_repos(identity.tenant_id).where(
        Repository.id == repo_id).execution_options(populate_existing=True))
    if not repo:
        raise HTTPException(404, "Repository not found")
    name, installation = repo.full_name, repo.installation_id
    try:
        visible = visible_github_repositories(identity, github, installation)
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(404, "Repository not found") from None
        raise
    if not any(item["id"] == repo_id and item["full_name"] == name for item in visible):
        raise HTTPException(404, "Repository not found")
    db.expire_all()
    repo = db.scalar(visible_repos(identity.tenant_id).where(
        Repository.id == repo_id).execution_options(populate_existing=True))
    if not repo or repo.full_name != name or repo.installation_id != installation:
        raise HTTPException(404, "Repository not found")
    session = db.get(AuthSession, identity.session_hash)
    if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
            or session.tenant_id != identity.tenant_id or session.user_id != identity.user_id
            or not db.get(Membership, (identity.tenant_id, identity.user_id))):
        raise HTTPException(401, "Authentication required")
    return name


def build_context(data, raw_comments, repository_id, name, number, config):
    if not isinstance(data, dict) or "pull_request" in data:
        raise HTTPException(404, "Issue not found")
    try:
        issue = IssueData.model_validate(data)
        comments = [CommentData.model_validate(x) for x in raw_comments]
        if issue.number != number or any(not isinstance(x.get("name"), str) for x in issue.labels):
            raise ValueError("invalid issue")
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(502, "Invalid GitHub issue response") from None
    comments.sort(key=lambda c: (c.created_at, c.id))
    remaining = config.issue_context_total_chars
    total_truncated = False

    def bounded(value, limit):
        nonlocal remaining, total_truncated
        value = value or ""
        clipped = value[:min(limit, remaining)]
        total_truncated |= len(value[:limit]) > len(clipped)
        remaining -= len(clipped)
        return clipped, len(clipped) < len(value)

    title, title_cut = bounded(issue.title, 1024)
    body, body_cut = bounded(issue.body, config.issue_context_body_chars)
    labels = []
    labels_cut = len(issue.labels) > 20
    for label in issue.labels[:20]:
        value, cut = bounded(label["name"], 100)
        labels.append(value)
        labels_cut |= cut
    result_comments, comments_cut = [], issue.comments > config.issue_context_comment_count
    for comment in comments[:config.issue_context_comment_count]:
        value, cut = bounded(comment.body, config.issue_context_comment_chars)
        result_comments.append({"id": str(comment.id), "body": value, "created_at": comment.created_at,
                                "updated_at": comment.updated_at, "truncated": cut})
        comments_cut |= cut
    comments_cut |= len(comments) > config.issue_context_comment_count or issue.comments > len(result_comments)
    path = "/".join(quote(part, safe="") for part in name.split("/"))
    return {"repository_id": str(repository_id), "issue_id": str(issue.id), "number": number,
            "title": title, "body": body, "state": issue.state, "labels": labels,
            "comments": result_comments, "created_at": issue.created_at, "updated_at": issue.updated_at,
            "retrieved_at": datetime.now(timezone.utc), "url": f"https://github.com/{path}/issues/{number}",
            "truncation": {"title": title_cut, "body": body_cut, "labels": labels_cut,
                           "comments": comments_cut, "total": total_truncated}}


@router.get("/{repository_id}/issues/{issue_number}/context", response_model=IssueContextResponse)
def issue_context(repository_id: int = Path(gt=0, lt=2**63),
                  issue_number: int = Path(gt=0, lt=2**31), identity: Principal = Depends(principal),
                  db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    config = get_settings()
    # The operation shares one request budget across both authorization checks and content reads.
    client = IssueContextClient(config.issue_context_max_requests) if type(github) is HttpGitHubClient else github
    name = authorize(repository_id, identity, db, client)
    try:
        issue = client.issue(identity.token, name, issue_number)
        if not isinstance(issue, dict) or "pull_request" in issue:
            raise HTTPException(404, "Issue not found")
        comments = client.issue_comments(identity.token, name, issue_number, config.issue_context_comment_count)
    except GitHubFailure as exc:
        if str(exc) == "github_not_found":
            raise HTTPException(404, "Issue not found") from None
        if str(exc) == "github_rate_limited":
            raise HTTPException(503, "GitHub rate limit reached") from None
        raise HTTPException(503, "GitHub issue unavailable") from None
    context = build_context(issue, comments, repository_id, name, issue_number, config)
    if authorize(repository_id, identity, db, client) != name:
        raise HTTPException(404, "Repository not found")
    return context
