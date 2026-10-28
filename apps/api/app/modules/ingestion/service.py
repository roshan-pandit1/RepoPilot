import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Delivery, Installation, Outbox, Repository
from app.modules.github.schemas import IssueEvent, LifecycleEvent
from app.modules.github.guards import installation_guard, repository_guard


def accept(db: Session, delivery_id: str, event: str, raw: bytes, payload: dict) -> bool:
    digest = hashlib.sha256(raw).hexdigest()
    try:
        with db.begin():
            previous = db.get(Delivery, delivery_id)
            if previous:
                if previous.body_hash != digest or previous.event != event:
                    raise HTTPException(409, "Delivery identifier conflict")
                return False
            db.add(Delivery(id=delivery_id, body_hash=digest, event=event))
            db.flush()
            if event == "issues":
                message = IssueEvent.model_validate(payload)
                installation = db.scalar(select(Installation).where(
                    Installation.id == message.installation.id
                ).with_for_update())
                repo = db.scalar(select(Repository).where(
                    Repository.id == message.repository.id
                ).with_for_update())
                if (not installation or not installation.active or not repo or not repo.enabled
                    or repo.installation_id != installation.id or message.repository.private):
                    raise HTTPException(403, "Repository is not authorized")
                db.add(Outbox(id=delivery_id, repository_id=repo.id, tenant_id=repo.tenant_id,
                              payload=json.loads(message.issue.model_dump_json())))
            else:
                message = LifecycleEvent.model_validate(payload)
                revoke_installation = event == "installation" and message.action in {
                    "deleted", "suspend", "new_permissions_accepted"
                }
                remove_repos = event == "installation_repositories" and message.action == "removed"
                if revoke_installation:
                    installation_guard(db, message.installation.id).revoked = True
                installation = db.scalar(select(Installation).where(
                    Installation.id == message.installation.id
                ).with_for_update())
                if installation and revoke_installation:
                    installation.active = False
                if remove_repos:
                    ids = sorted({r.id for r in message.repositories_removed})
                    for repository_id in ids:
                        repository_guard(db, message.installation.id, repository_id).revoked = True
                    if installation:
                        repos = db.scalars(select(Repository).where(
                            Repository.installation_id == installation.id,
                            Repository.id.in_(ids),
                        ).with_for_update())
                        for repo in repos:
                            repo.enabled = False
        return True
    except IntegrityError:
        db.rollback()
        previous = db.get(Delivery, delivery_id)
        if previous and previous.body_hash == digest and previous.event == event:
            return False
        if previous:
            raise HTTPException(409, "Delivery identifier conflict") from None
        raise
