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


def process_sync(job_id: str, factory=None, github=None):
    """Apply a bounded GitHub issue snapshot after rechecking all authorization."""
    from cryptography.fernet import InvalidToken
    from fastapi import HTTPException
    from pydantic import ValidationError

    from app.domain.models import AuthSession, Membership, SyncJob, User
    from app.modules.auth.session import Principal, cipher, utc
    from app.modules.github.client import GitHubFailure, get_github_client
    from app.modules.github.enrollment import visible_github_repositories
    from app.modules.github.schemas import IssuePayload

    factory = factory or get_session_factory()
    github = github or get_github_client()
    with factory.begin() as db:
        job = db.scalar(select(SyncJob).where(SyncJob.id == job_id).with_for_update())
        if not job or job.status != "pending":
            return
        session = db.scalar(select(AuthSession).where(
            AuthSession.id_hash == job.session_hash).with_for_update())
        if (not session or session.revoked_at is not None or session.tenant_id != job.tenant_id
                or utc(session.expires_at) <= now()
                or not db.get(Membership, (job.tenant_id, session.user_id))):
            job.status, job.processed_at = "ignored", now()
            return
        user = db.get(User, session.user_id)
        installation_id = db.scalar(select(Repository.installation_id).where(Repository.id == job.repository_id))
        installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
        repo = db.scalar(select(Repository).where(Repository.id == job.repository_id).with_for_update())
        if not user or not installation or not installation.active or not repo or not repo.enabled:
            job.status, job.processed_at = "ignored", now()
            return
        try:
            token = cipher().decrypt(session.github_token_ciphertext.encode()).decode()
        except (InvalidToken, UnicodeError, ValueError):
            job.status, job.processed_at = "failed", now()
            return
        identity = Principal(user.id, job.tenant_id, user.github_user_id, token, session.id_hash)
        try:
            allowed = visible_github_repositories(identity, github, installation.id)
            authoritative = next((item for item in allowed if item["id"] == repo.id), None)
            if not authoritative:
                job.status, job.processed_at = "ignored", now()
                return
            raw_issues = github.issues(token, authoritative["full_name"])
            # A repository can become private or move while the request is in flight.
            # Recheck authoritative access immediately before applying any fetched data.
            after = visible_github_repositories(identity, github, installation.id)
            if not any(item["id"] == repo.id and item["full_name"] == authoritative["full_name"]
                       for item in after):
                job.status, job.processed_at = "ignored", now()
                return
            issues = [IssuePayload.model_validate(item) for item in raw_issues if "pull_request" not in item]
        except HTTPException as exc:
            if exc.status_code == 403:
                job.status, job.processed_at = "ignored", now()
                return
            raise TransientIngestionError("github_verification_unavailable") from None
        except GitHubFailure:
            raise TransientIngestionError("github_sync_unavailable") from None
        except ValidationError:
            job.status, job.processed_at = "failed", now()
            return
        for data in issues:
            issue = db.scalar(select(Issue).where(Issue.repository_id == repo.id, Issue.number == data.number))
            previous = utc(issue.source_updated_at) if issue else None
            if issue is None:
                issue = Issue(id=data.id, repository_id=repo.id, tenant_id=repo.tenant_id, number=data.number)
                db.add(issue)
            if previous is None or data.updated_at > previous:
                issue.title, issue.body, issue.state, issue.source_updated_at = (
                    data.title, data.body, data.state, data.updated_at)
        job.status = "partial" if len(raw_issues) >= 100 else "processed"
        job.processed_at = now()


@celery.task(name="sync_repository", autoretry_for=(TransientIngestionError,),
             retry_backoff=True, retry_jitter=True, retry_backoff_max=60, max_retries=5)
def sync_repository(job_id: str):
    try:
        process_sync(job_id)
    except OperationalError:
        raise TransientIngestionError("database_temporarily_unavailable") from None
    except SQLAlchemyError:
        raise IngestionError("database_operation_failed") from None
