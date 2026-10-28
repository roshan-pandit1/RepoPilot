from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import Installation, Repository, SyncJob
from app.infra.database import get_db
from app.modules.auth.session import Principal, principal, require_csrf
from app.modules.github.client import GitHubClient, GitHubFailure, get_github_client
from app.modules.github.guards import installation_guard, repository_guard

router = APIRouter(prefix="/v1/installations")


def verified_installations(identity: Principal, github: GitHubClient) -> list[dict]:
    if identity.demo or not identity.token or not identity.github_id:
        raise HTTPException(403, "GitHub session required")
    try:
        installations = github.installations(identity.token)
    except GitHubFailure:
        raise HTTPException(503, "GitHub verification unavailable") from None
    # Initial enrollment is limited to the user's own personal account; organization
    # admin verification will be a separate increment.
    return [entry for entry in installations if entry.get("app_id") == get_settings().github_app_id
            and isinstance(entry.get("id"), int) and not isinstance(entry["id"], bool)
            and 0 < entry["id"] < 2**63
            and isinstance(entry.get("account"), dict)
            and entry["account"].get("type") == "User"
            and entry["account"].get("id") == identity.github_id
            and "suspended_at" in entry and entry["suspended_at"] is None]


def visible_github_repositories(identity: Principal, github: GitHubClient,
                                installation_id: int) -> list[dict]:
    if not any(item["id"] == installation_id for item in verified_installations(identity, github)):
        raise HTTPException(403, "Installation is not authorized")
    try:
        repos = github.repositories(identity.token, installation_id)
    except GitHubFailure:
        raise HTTPException(503, "GitHub verification unavailable") from None
    return [repo for repo in repos if isinstance(repo.get("id"), int) and not isinstance(repo["id"], bool)
            and 0 < repo["id"] < 2**63
            and repo.get("private") is False and isinstance(repo.get("full_name"), str)
            and 0 < len(repo["full_name"]) <= 250]


@router.get("/available")
def available(identity: Principal = Depends(principal),
              github: GitHubClient = Depends(get_github_client)):
    return [{"id": str(item["id"]), "account": item["account"].get("login", "")}
            for item in verified_installations(identity, github)]


@router.post("/{installation_id}/enroll")
def enroll(installation_id: int, request: Request, identity: Principal = Depends(principal),
           db: Session = Depends(get_db), github: GitHubClient = Depends(get_github_client)):
    require_csrf(request, identity, db)
    if not 0 < installation_id < 2**63:
        raise HTTPException(400, "Invalid installation")
    guard = installation_guard(db, installation_id)
    if guard.revoked:
        raise HTTPException(409, "Installation requires reauthorization")
    # The guard serializes unknown-ID revocations with this authoritative check.
    repos = visible_github_repositories(identity, github, installation_id)
    installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
    if installation and installation.tenant_id != identity.tenant_id:
        raise HTTPException(409, "Installation cannot be enrolled")
    if installation and not installation.active:
        # Revocations are never silently undone; a reviewed reauthorization process is needed.
        raise HTTPException(409, "Installation requires reauthorization")
    if not installation:
        installation = Installation(id=installation_id, tenant_id=identity.tenant_id, active=True)
        db.add(installation)
        db.flush()
    db.commit()
    return {"installation_id": str(installation_id), "repositories": [
        {"id": str(r["id"]), "full_name": r["full_name"]} for r in repos]}


@router.post("/{installation_id}/repositories/{repository_id}/select")
def select_repository(installation_id: int, repository_id: int, request: Request,
                      identity: Principal = Depends(principal), db: Session = Depends(get_db),
                      github: GitHubClient = Depends(get_github_client)):
    require_csrf(request, identity, db)
    if not (0 < installation_id < 2**63 and 0 < repository_id < 2**63):
        raise HTTPException(400, "Invalid repository")
    installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
    if not installation or not installation.active or installation.tenant_id != identity.tenant_id:
        raise HTTPException(404, "Repository not available")
    guard = repository_guard(db, installation_id, repository_id)
    if guard.revoked:
        raise HTTPException(409, "Repository requires reauthorization")
    repos = visible_github_repositories(identity, github, installation_id)
    selected = next((r for r in repos if r["id"] == repository_id), None)
    if not selected:
        raise HTTPException(404, "Repository not available")
    repo = db.scalar(select(Repository).where(Repository.id == repository_id).with_for_update())
    if repo and (repo.tenant_id != identity.tenant_id or repo.installation_id != installation_id):
        raise HTTPException(409, "Repository cannot be selected")
    if repo and not repo.enabled:
        raise HTTPException(409, "Repository requires reauthorization")
    if not repo:
        repo = Repository(id=repository_id, tenant_id=identity.tenant_id, installation_id=installation_id,
                          full_name=selected["full_name"], enabled=True)
        db.add(repo)
    else:
        repo.full_name = selected["full_name"]
    db.flush()
    job = db.scalar(select(SyncJob).where(SyncJob.repository_id == repo.id,
                                         SyncJob.tenant_id == identity.tenant_id,
                                         SyncJob.status == "pending").with_for_update())
    if not job:
        job = SyncJob(id=str(uuid4()), repository_id=repo.id, tenant_id=identity.tenant_id,
                      session_hash=identity.session_hash)
        db.add(job)
    db.commit()
    return {"id": str(repo.id), "full_name": repo.full_name,
            "sync_status": "pending", "sync_job_id": job.id}


@router.get("/sync/{job_id}")
def sync_status(job_id: UUID, identity: Principal = Depends(principal), db: Session = Depends(get_db),
                github: GitHubClient = Depends(get_github_client)):
    job = db.get(SyncJob, str(job_id))
    if not job or job.tenant_id != identity.tenant_id:
        raise HTTPException(404, "Sync job not found")
    repo = db.get(Repository, job.repository_id)
    installation = db.get(Installation, repo.installation_id) if repo else None
    if not repo or not repo.enabled or not installation or not installation.active:
        raise HTTPException(404, "Sync job not found")
    allowed = visible_github_repositories(identity, github, installation.id)
    if not any(item["id"] == repo.id for item in allowed):
        raise HTTPException(404, "Sync job not found")
    return {"id": job.id, "status": job.status}
