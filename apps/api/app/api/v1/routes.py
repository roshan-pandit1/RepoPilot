import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.github.security import valid_signature
from app.domain.models import Installation, Issue, Outbox, Repository
from app.infra.database import get_db
from app.modules.github.schemas import IssueEvent, LifecycleEvent
from app.modules.ingestion.service import accept
from app.modules.tenancy.auth import tenant_identity

router = APIRouter(prefix="/v1")
LIMIT = 1024 * 1024


@router.post("/webhooks/github")
async def webhook(request: Request, db: Session = Depends(get_db)):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > LIMIT:
            raise HTTPException(413, "Payload too large")
        raw.extend(chunk)
    raw = bytes(raw)
    signature = request.headers.get("x-hub-signature-256", "")
    if not valid_signature(raw, signature, get_settings().github_webhook_secret.get_secret_value()):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        delivery_id = str(UUID(request.headers.get("x-github-delivery", "")))
    except ValueError:
        raise HTTPException(400, "Valid delivery identifier required") from None
    event = request.headers.get("x-github-event")
    if event not in {"issues", "installation", "installation_repositories"}:
        raise HTTPException(400, "Unsupported webhook event")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "JSON content type required")
    try:
        payload = json.loads(raw)
        if event == "issues":
            IssueEvent.model_validate(payload)
        else:
            message = LifecycleEvent.model_validate(payload)
            allowed = ({"created", "deleted", "suspend", "unsuspend", "new_permissions_accepted"}
                       if event == "installation" else {"added", "removed"})
            if message.action not in allowed:
                raise ValueError()
    except (ValueError, ValidationError, RecursionError):
        raise HTTPException(400, "Malformed or unsupported webhook payload") from None
    inserted = accept(db, delivery_id, event, raw, payload)
    return JSONResponse({"delivery_id": delivery_id,
                         "status": "accepted" if inserted else "duplicate"},
                        status_code=202 if inserted else 200)


def visible_repos(tenant: int):
    return select(Repository).join(Installation, Repository.installation_id == Installation.id).where(
        Repository.tenant_id == tenant, Repository.enabled.is_(True), Installation.active.is_(True)
    )


@router.get("/repositories")
def repositories(tenant: int = Depends(tenant_identity), db: Session = Depends(get_db)):
    rows = db.scalars(visible_repos(tenant).order_by(Repository.full_name).limit(100))
    return [{"id": str(r.id), "full_name": r.full_name, "enabled": r.enabled} for r in rows]


@router.get("/repositories/{repository_id}/issues")
def issues(repository_id: int, tenant: int = Depends(tenant_identity),
           db: Session = Depends(get_db), offset: int = 0):
    if offset < 0 or offset > 1_000_000 or not 0 < repository_id < 2**63:
        raise HTTPException(400, "Invalid offset")
    repo = db.scalar(visible_repos(tenant).where(Repository.id == repository_id))
    if not repo:
        raise HTTPException(404, "Repository not found")
    rows = db.scalars(select(Issue).where(Issue.repository_id == repo.id, Issue.tenant_id == tenant)
                      .order_by(Issue.source_updated_at.desc(), Issue.id).offset(offset).limit(100))
    statuses = dict(db.execute(select(Outbox.status, func.count()).where(
        Outbox.repository_id == repo.id, Outbox.tenant_id == tenant
    ).group_by(Outbox.status)).all())
    return {"items": [{"id": str(i.id), "number": i.number, "title": i.title, "state": i.state,
                       "updated_at": i.source_updated_at.isoformat(), "ingestion_status": "processed"}
                      for i in rows],
            "ingestion": {s: statuses.get(s, 0) for s in ("pending", "processed", "ignored", "failed")}}
