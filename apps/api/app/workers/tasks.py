from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import get_settings
from app.domain.models import Installation, Issue, Outbox, Repository, now
from app.infra.database import get_session_factory

celery = Celery("repopilot", broker=get_settings().redis_url)
celery.conf.update(task_serializer="json", accept_content=["json"], task_ignore_result=True,
                   task_acks_late=True, task_reject_on_worker_lost=True,
                   worker_prefetch_multiplier=1, broker_connection_retry_on_startup=True)


def process_event(event_id: str, factory=None):
    factory = factory or get_session_factory()
    with factory.begin() as db:
        event = db.scalar(select(Outbox).where(Outbox.id == event_id).with_for_update())
        if not event or event.status != "pending":
            return
        # Lock installation then repository, consistently with ingress/revocation.
        installation_id = db.scalar(select(Repository.installation_id).where(
            Repository.id == event.repository_id))
        installation = db.scalar(select(Installation).where(
            Installation.id == installation_id).with_for_update())
        repo = db.scalar(select(Repository).where(
            Repository.id == event.repository_id).with_for_update())
        if not installation.active or not repo.enabled or repo.tenant_id != event.tenant_id:
            event.status = "ignored"
            event.processed_at = now()
            return
        data = event.payload
        timestamp = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        issue = db.scalar(select(Issue).where(
            Issue.repository_id == repo.id, Issue.number == data["number"]))
        previous = issue.source_updated_at if issue else None
        if previous and previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        if issue is None:
            issue = Issue(id=data["id"], repository_id=repo.id, tenant_id=repo.tenant_id,
                          number=data["number"])
            db.add(issue)
        if previous is None or timestamp > previous:
            issue.title = data["title"]
            issue.body = data["body"]
            issue.state = data["state"]
            issue.source_updated_at = timestamp
        event.status = "processed"
        event.processed_at = now()


class TransientIngestionError(Exception):
    """Safe retry reason: never expose driver messages or payload parameters."""


class IngestionError(Exception):
    """Safe terminal reason; the outbox remains available for operator review."""


@celery.task(name="ingest_issue", autoretry_for=(TransientIngestionError,),
             retry_backoff=True, retry_jitter=True, retry_backoff_max=60,
             max_retries=5)
def ingest_issue(event_id: str):
    try:
        process_event(event_id)
    except OperationalError:
        raise TransientIngestionError("database_temporarily_unavailable") from None
    except SQLAlchemyError:
        raise IngestionError("database_operation_failed") from None
