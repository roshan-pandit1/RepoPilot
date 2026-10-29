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
                   worker_prefetch_multiplier=1, broker_connection_retry_on_startup=True,
                   worker_redirect_stdouts=False)


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


def process_index(job_id: str, factory=None, github=None, source=None, task_id=None):
    """Claim briefly, fetch without locks, then publish under a fenced lease."""
    from datetime import timedelta
    from uuid import uuid4

    from cryptography.fernet import InvalidToken
    from fastapi import HTTPException

    from app.domain.models import AuthSession, IndexJob, Membership, User
    from app.core.index_logging import index_event
    from app.modules.auth.session import Principal, cipher, utc
    from app.modules.github.client import GitHubFailure, get_github_client
    from app.modules.github.enrollment import visible_github_repositories
    from app.modules.github.source_client import GitHubSourceClient
    from app.modules.ingestion.code_collect import CollectionError, collect_source
    from app.modules.ingestion.code_persistence import publish_snapshot
    from app.modules.ingestion.code_snapshot import SnapshotError, plan_snapshot

    factory = factory or get_session_factory()
    github = github or get_github_client()
    source = source or GitHubSourceClient()
    lease = str(uuid4())
    with factory.begin() as db:
        job = db.scalar(select(IndexJob).where(IndexJob.id == job_id).with_for_update())
        if not job or (job.status != "pending" and not (
            job.status == "running" and (not job.lease_expires_at or utc(job.lease_expires_at) <= now())
        )):
            return
        session = db.scalar(select(AuthSession).where(AuthSession.id_hash == job.session_hash).with_for_update())
        if (not session or session.tenant_id != job.tenant_id or session.revoked_at is not None
                or utc(session.expires_at) <= now() or not db.get(Membership, (job.tenant_id, session.user_id))):
            job.status, job.error_code, job.completed_at = "cancelled", "session_unavailable", now()
            index_event("index_authorization_revoked", job_id=job_id, repository_id=job.repository_id, task_id=task_id)
            return
        user = db.get(User, session.user_id)
        installation_id = db.scalar(select(Repository.installation_id).where(
            Repository.id == job.repository_id, Repository.tenant_id == job.tenant_id))
        installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
        repo = db.scalar(select(Repository).where(Repository.id == job.repository_id,
                                                 Repository.tenant_id == job.tenant_id).with_for_update())
        if not user or not installation or not installation.active or not repo or not repo.enabled:
            job.status, job.error_code, job.completed_at = "cancelled", "repository_unavailable", now()
            index_event("index_authorization_revoked", job_id=job_id, repository_id=job.repository_id, task_id=task_id)
            return
        try:
            token = cipher().decrypt(session.github_token_ciphertext.encode()).decode()
        except (InvalidToken, UnicodeError, ValueError):
            job.status, job.error_code, job.completed_at = "failed", "invalid_session_or_source", now()
            index_event("index_job_failed", job_id=job_id, repository_id=job.repository_id, task_id=task_id)
            return
        identity = Principal(user.id, job.tenant_id, user.github_user_id, token, session.id_hash)
        repo_id, repo_name, installation_id = repo.id, repo.full_name, installation.id
        job.status, job.lease_token = "running", lease
        job.lease_expires_at = now() + timedelta(seconds=240)
        job.error_code = None

    index_event("index_job_claimed", job_id=job_id, repository_id=repo_id, task_id=task_id)

    def finish(status, error):
        updated = False
        with factory.begin() as db:
            current = db.scalar(select(IndexJob).where(IndexJob.id == job_id).with_for_update())
            if current and current.status == "running" and current.lease_token == lease:
                current.status, current.error_code = status, error
                current.lease_token, current.lease_expires_at = None, None
                current.completed_at = None if status == "pending" else now()
                updated = True
        if updated:
            event = {"cancelled": "index_job_cancelled", "pending": "index_job_retry",
                     "failed": "index_job_failed"}.get(status, "index_job_finished")
            if status == "cancelled" and error == "repository_unavailable":
                event = "index_authorization_revoked"
            index_event(event, job_id=job_id, repository_id=repo_id, task_id=task_id)

    try:
        index_event("index_source_started", job_id=job_id, repository_id=repo_id, task_id=task_id)
        allowed = visible_github_repositories(identity, github, installation_id)
        if not any(item["id"] == repo_id and item["full_name"] == repo_name for item in allowed):
            finish("cancelled", "repository_unavailable")
            return
        plan = plan_snapshot(source, token, repo_name)
        collection = collect_source(source, token, repo_name, plan)
        index_event("index_source_collected", job_id=job_id, repository_id=repo_id, task_id=task_id)
        allowed = visible_github_repositories(identity, github, installation_id)
        if not any(item["id"] == repo_id and item["full_name"] == repo_name for item in allowed):
            finish("cancelled", "repository_unavailable")
            return
        latest = source.repository(token, repo_name)
        branch = latest.get("default_branch")
        if (latest.get("private") is not False or latest.get("full_name") != repo_name
                or not isinstance(branch, str) or not branch):
            finish("cancelled", "repository_unavailable")
            return
        if source.commit(token, repo_name, branch).get("sha") != plan.commit_sha:
            finish("cancelled", "repository_changed")
            return
    except HTTPException as exc:
        if exc.status_code == 403:
            finish("cancelled", "repository_unavailable")
            return
        finish("pending", "github_verification_unavailable")
        raise TransientIngestionError("github_verification_unavailable") from None
    except GitHubFailure as exc:
        if str(exc) in {"github_request_budget_exceeded", "github_response_too_large",
                        "github_time_budget_exceeded", "github_blob_invalid", "github_commit_invalid"}:
            finish("failed", str(exc))
            return
        finish("pending", "github_source_unavailable")
        raise TransientIngestionError("github_source_unavailable") from None
    except (SnapshotError, CollectionError) as exc:
        finish("failed", str(exc)[:80])
        return
    except (UnicodeError, ValueError):
        finish("failed", "invalid_session_or_source")
        return

    index_event("index_publication_started", job_id=job_id, repository_id=repo_id, task_id=task_id)
    with factory.begin() as db:
        job = db.scalar(select(IndexJob).where(IndexJob.id == job_id).with_for_update())
        if (not job or job.status != "running" or job.lease_token != lease or not job.lease_expires_at
                or utc(job.lease_expires_at) <= now()):
            return
        session = db.scalar(select(AuthSession).where(AuthSession.id_hash == job.session_hash).with_for_update())
        installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
        repo = db.scalar(select(Repository).where(Repository.id == repo_id,
                         Repository.tenant_id == job.tenant_id).with_for_update())
        if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
                or session.user_id != identity.user_id or session.tenant_id != identity.tenant_id
                or not db.get(Membership, (job.tenant_id, session.user_id)) or not installation
                or not installation.active or installation.tenant_id != job.tenant_id or not repo
                or not repo.enabled or repo.full_name != repo_name or repo.installation_id != installation_id):
            job.status, job.error_code, job.completed_at = "cancelled", "repository_unavailable", now()
            job.lease_token, job.lease_expires_at = None, None
            index_event("index_authorization_revoked", job_id=job_id, repository_id=repo_id, task_id=task_id)
            return
        snapshot = publish_snapshot(db, repo, plan, collection)
        job.commit_sha = snapshot.commit_sha
        job.file_count, job.chunk_count, job.skipped_count = (
            snapshot.file_count, snapshot.chunk_count, snapshot.skipped_count)
        job.status = "partial" if collection.skipped_files else "completed"
        job.completed_at = now()
        job.lease_token, job.lease_expires_at = None, None
        snapshot_id = snapshot.id
    index_event("index_snapshot_published", job_id=job_id, repository_id=repo_id, task_id=task_id, snapshot_id=snapshot_id)
    index_event("index_job_completed", job_id=job_id, repository_id=repo_id, task_id=task_id, snapshot_id=snapshot_id)


@celery.task(name="index_repository", autoretry_for=(TransientIngestionError,), retry_backoff=True,
             retry_jitter=True, retry_backoff_max=60, max_retries=5,
             soft_time_limit=180, time_limit=200)
def index_repository(job_id: str):
    try:
        process_index(job_id, task_id=index_repository.request.id)
    except OperationalError:
        from app.core.index_logging import index_event
        index_event("index_job_retry", job_id=job_id, task_id=index_repository.request.id)
        raise TransientIngestionError("database_temporarily_unavailable") from None
    except SQLAlchemyError:
        from app.core.index_logging import index_event
        index_event("index_job_failed", job_id=job_id, task_id=index_repository.request.id)
        raise IngestionError("database_operation_failed") from None


def process_embedding(job_id: str, factory=None, github=None, provider=None):
    """Process bounded batches under a fenced lease; provider calls hold no DB locks."""
    from datetime import timedelta
    from uuid import uuid4
    from cryptography.fernet import InvalidToken
    from fastapi import HTTPException
    from app.domain.models import AuthSession, CodeChunk, CodeSnapshot, EmbeddingCache, EmbeddingJob, IndexedFile, Membership, User
    from app.modules.auth.session import Principal, cipher, utc
    from app.modules.github.client import get_github_client
    from app.modules.github.enrollment import visible_github_repositories
    from app.modules.ingestion.embedding_store import cache_key, persist_embedding
    from app.modules.ingestion.embeddings import EmbeddingError, configured_provider

    factory, github = factory or get_session_factory(), github or get_github_client()
    if provider is None:
        try:
            provider = configured_provider()
        except EmbeddingError:
            with factory.begin() as db:
                job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.id == job_id).with_for_update())
                if job and (job.status == "pending" or (job.status == "running" and
                        (not job.lease_expires_at or utc(job.lease_expires_at) <= now()))):
                    job.status, job.error_code, job.completed_at = "failed", "embedding_provider_disabled", now()
                    job.lease_token, job.lease_expires_at = None, None
            return
    lease = str(uuid4())
    with factory.begin() as db:
        job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.id == job_id).with_for_update())
        if not job or (job.status != "pending" and not (job.status == "running" and
                (not job.lease_expires_at or utc(job.lease_expires_at) <= now()))):
            return
        if (job.provider, job.model, job.model_version, job.dimensions) != (
                provider.provider, provider.model, provider.version, provider.dimensions):
            job.status, job.error_code, job.completed_at = "failed", "embedding_configuration_changed", now()
            return
        if provider.provider != "fake":
            # Paid generation stays disabled until explicit approval and cost-budget review.
            job.status, job.error_code, job.completed_at = "failed", "paid_generation_not_enabled", now()
            return
        session = db.scalar(select(AuthSession).where(AuthSession.id_hash == job.session_hash).with_for_update())
        if (not session or session.tenant_id != job.tenant_id or session.revoked_at is not None
                or utc(session.expires_at) <= now() or not db.get(Membership, (job.tenant_id, session.user_id))):
            job.status, job.error_code, job.completed_at = "cancelled", "session_unavailable", now()
            return
        user = db.get(User, session.user_id)
        repo = db.get(Repository, job.repository_id)
        installation = db.get(Installation, repo.installation_id) if repo else None
        snapshot = db.get(CodeSnapshot, job.snapshot_id)
        if (not user or not repo or repo.tenant_id != job.tenant_id or not repo.enabled or not installation
                or not installation.active or not snapshot or not snapshot.published):
            job.status, job.error_code, job.completed_at = "cancelled", "repository_unavailable", now()
            return
        try:
            token = cipher().decrypt(session.github_token_ciphertext.encode()).decode()
        except (InvalidToken, UnicodeError, ValueError):
            job.status, job.error_code, job.completed_at = "failed", "invalid_session", now()
            return
        identity = Principal(user.id, job.tenant_id, user.github_user_id, token, session.id_hash)
        repo_id, repo_name, installation_id, snapshot_id = repo.id, repo.full_name, installation.id, snapshot.id
        job.status, job.lease_token, job.lease_expires_at = "running", lease, now() + timedelta(seconds=240)

    def finish(status, code):
        with factory.begin() as db:
            row = db.scalar(select(EmbeddingJob).where(EmbeddingJob.id == job_id).with_for_update())
            if row and row.status == "running" and row.lease_token == lease:
                row.status, row.error_code = status, code
                row.lease_token, row.lease_expires_at = None, None
                row.completed_at = None if status == "pending" else now()

    try:
        allowed = visible_github_repositories(identity, github, installation_id)
        if not any(item["id"] == repo_id and item["full_name"] == repo_name for item in allowed):
            finish("cancelled", "repository_unavailable")
            return
        with factory() as db:
            chunks = db.execute(select(CodeChunk.id, CodeChunk.source_text).join(IndexedFile,
                CodeChunk.file_id == IndexedFile.id).where(IndexedFile.snapshot_id == snapshot_id,
                CodeChunk.repository_id == repo_id, CodeChunk.tenant_id == identity.tenant_id)
                .order_by(CodeChunk.id).limit(10_001)).all()
        if len(chunks) > 10_000 or sum(len(c.source_text.encode()) for c in chunks) > 5_000_000:
            finish("failed", "embedding_budget_exceeded")
            return
        chunks = [chunk for chunk in chunks if chunk.source_text.strip()]
        if any(len(chunk.source_text) > 20_000 for chunk in chunks):
            finish("failed", "embedding_input_limit")
            return
        for offset in range(0, len(chunks), 32):
            batch = chunks[offset:offset + 32]
            unique = {cache_key(item.source_text): item.source_text for item in batch}
            with factory() as db:
                existing = db.scalars(select(EmbeddingCache).where(
                    EmbeddingCache.repository_id == repo_id, EmbeddingCache.tenant_id == identity.tenant_id,
                    EmbeddingCache.content_hash.in_(list(unique)), EmbeddingCache.provider == provider.provider,
                    EmbeddingCache.model == provider.model, EmbeddingCache.model_version == provider.version,
                    EmbeddingCache.dimensions == provider.dimensions, EmbeddingCache.status == "ready")).all()
                vectors = {item.content_hash: item.vector for item in existing}
            missing = [key for key in unique if key not in vectors]
            generated = provider.embed([unique[key] for key in missing]) if missing else None
            if generated:
                vectors.update(zip(missing, generated.vectors, strict=True))
            allowed = visible_github_repositories(identity, github, installation_id)
            if not any(item["id"] == repo_id and item["full_name"] == repo_name for item in allowed):
                finish("cancelled", "repository_unavailable")
                return
            with factory.begin() as db:
                job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.id == job_id).with_for_update())
                if (not job or job.status != "running" or job.lease_token != lease or
                        not job.lease_expires_at or utc(job.lease_expires_at) <= now()):
                    return
                session = db.scalar(select(AuthSession).where(AuthSession.id_hash == job.session_hash).with_for_update())
                installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
                repo = db.scalar(select(Repository).where(Repository.id == repo_id).with_for_update())
                snapshot = db.get(CodeSnapshot, snapshot_id)
                if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
                        or session.user_id != identity.user_id or session.tenant_id != identity.tenant_id
                        or not db.get(Membership, (identity.tenant_id, identity.user_id)) or not installation
                        or not installation.active or installation.tenant_id != identity.tenant_id or not repo
                        or not repo.enabled or repo.tenant_id != identity.tenant_id or repo.full_name != repo_name
                        or repo.installation_id != installation_id or not snapshot or not snapshot.published):
                    job.status, job.error_code, job.completed_at = "cancelled", "repository_unavailable", now()
                    job.lease_token, job.lease_expires_at = None, None
                    return
                for item in batch:
                    chunk = db.get(CodeChunk, item.id)
                    indexed_file = db.get(IndexedFile, chunk.file_id) if chunk else None
                    if (not chunk or chunk.repository_id != repo_id or chunk.tenant_id != identity.tenant_id
                            or not indexed_file or indexed_file.snapshot_id != snapshot_id
                            or cache_key(chunk.source_text) != cache_key(item.source_text)):
                        raise ValueError("chunk_unavailable")
                    persist_embedding(db, chunk, provider, vectors[cache_key(item.source_text)])
                job.total_chunks, job.completed_chunks = len(chunks), offset + len(batch)
                job.token_usage += generated.tokens if generated else 0
                job.lease_expires_at = now() + timedelta(seconds=240)
        allowed = visible_github_repositories(identity, github, installation_id)
        if not any(item["id"] == repo_id and item["full_name"] == repo_name for item in allowed):
            finish("cancelled", "repository_unavailable")
            return
        with factory.begin() as db:
            job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.id == job_id).with_for_update())
            if not job or job.status != "running" or job.lease_token != lease or not job.lease_expires_at or utc(job.lease_expires_at) <= now():
                return
            session = db.scalar(select(AuthSession).where(AuthSession.id_hash == job.session_hash).with_for_update())
            installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
            repo = db.scalar(select(Repository).where(Repository.id == repo_id).with_for_update())
            snapshot = db.get(CodeSnapshot, snapshot_id)
            if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
                    or session.user_id != identity.user_id or session.tenant_id != identity.tenant_id
                    or not db.get(Membership, (identity.tenant_id, identity.user_id)) or not installation
                    or not installation.active or installation.tenant_id != identity.tenant_id or not repo
                    or not repo.enabled or repo.tenant_id != identity.tenant_id or repo.full_name != repo_name
                    or repo.installation_id != installation_id or not snapshot or not snapshot.published):
                job.status, job.error_code, job.completed_at = "cancelled", "repository_unavailable", now()
            else:
                job.status, job.total_chunks, job.completed_chunks, job.completed_at = "completed", len(chunks), len(chunks), now()
            job.lease_token, job.lease_expires_at = None, None
    except HTTPException as exc:
        if exc.status_code == 403:
            finish("cancelled", "repository_unavailable")
            return
        finish("pending", "github_verification_unavailable")
        raise TransientIngestionError("github_verification_unavailable") from None
    except EmbeddingError as exc:
        if str(exc) == "embedding_provider_failed":
            finish("pending", "embedding_provider_unavailable")
            raise TransientIngestionError("embedding_provider_unavailable") from None
        finish("failed", "embedding_invalid")
    except ValueError:
        finish("failed", "embedding_invalid")


@celery.task(name="embed_repository", autoretry_for=(TransientIngestionError,), retry_backoff=True,
             retry_jitter=True, retry_backoff_max=60, max_retries=5, soft_time_limit=180, time_limit=200)
def embed_repository(job_id: str):
    from app.core.index_logging import index_event
    index_event("embedding_task_received", job_id=job_id, task_id=embed_repository.request.id)
    try:
        process_embedding(job_id)
        index_event("embedding_task_finished", job_id=job_id, task_id=embed_repository.request.id)
    except OperationalError:
        raise TransientIngestionError("database_temporarily_unavailable") from None
    except SQLAlchemyError:
        raise IngestionError("database_operation_failed") from None
