import logging
import time
from datetime import timedelta

from sqlalchemy import and_, or_, select

from app.domain.models import EmbeddingJob, IndexJob, InvestigationOutbox, InvestigationReportOutbox, Outbox, SyncJob, now
from app.core.index_logging import index_event
from app.infra.database import get_session_factory
from app.workers.tasks import embed_repository, generate_mock_report, index_repository, ingest_issue, investigate_issue, sync_repository

logger = logging.getLogger("repopilot.dispatcher")


def dispatch_once(factory=None, publish=None, publish_sync=None, publish_index=None, publish_embedding=None, publish_investigation=None, publish_report=None):
    factory = factory or get_session_factory()
    publish = publish or (lambda event_id: ingest_issue.apply_async(
        args=[event_id], task_id=event_id, retry=False))
    publish_sync = publish_sync or (lambda job_id: sync_repository.apply_async(
        args=[job_id], task_id=job_id, retry=False))
    publish_index = publish_index or (lambda job_id: index_repository.apply_async(
        args=[job_id], task_id=job_id, retry=False))
    publish_embedding = publish_embedding or (lambda job_id: embed_repository.apply_async(
        args=[job_id], task_id=job_id, retry=False))
    publish_investigation = publish_investigation or (lambda job_id: investigate_issue.apply_async(
        args=[job_id], task_id=job_id, retry=False))
    publish_report = publish_report or (lambda job_id: generate_mock_report.apply_async(
        args=[job_id], task_id=job_id, retry=False))
    dispatched = []
    dispatched_embeddings = []
    dispatched_investigations = []
    dispatched_reports = []
    with factory.begin() as db:
        events = db.scalars(select(Outbox).where(
            Outbox.status == "pending", Outbox.next_dispatch_at <= now()
        ).order_by(Outbox.next_dispatch_at).limit(50).with_for_update(skip_locked=True))
        for event in events:
            if event.attempts >= 20:
                event.status = "failed"
                continue
            event.attempts += 1
            event.next_dispatch_at = now() + timedelta(seconds=min(300, 2 ** event.attempts))
            try:
                publish(event.id)
            except Exception:
                logger.warning("outbox_publish_failed")
            # Remains pending until worker commits. Republish also repairs broker loss.
        jobs = db.scalars(select(SyncJob).where(
            SyncJob.status == "pending", SyncJob.next_dispatch_at <= now()
        ).order_by(SyncJob.next_dispatch_at).limit(50).with_for_update(skip_locked=True))
        for job in jobs:
            if job.attempts >= 20:
                job.status = "failed"
                continue
            job.attempts += 1
            job.next_dispatch_at = now() + timedelta(seconds=min(300, 2 ** job.attempts))
            try:
                publish_sync(job.id)
            except Exception:
                logger.warning("sync_publish_failed")
        index_jobs = db.scalars(select(IndexJob).where(
            IndexJob.next_dispatch_at <= now(),
            or_(IndexJob.status == "pending", and_(IndexJob.status == "running",
                or_(IndexJob.lease_expires_at.is_(None), IndexJob.lease_expires_at <= now())))
        ).order_by(IndexJob.next_dispatch_at).limit(10).with_for_update(skip_locked=True))
        for job in index_jobs:
            if job.attempts >= 20:
                job.status = "failed"
                job.error_code = "dispatch_exhausted"
                job.completed_at = now()
                continue
            job.attempts += 1
            job.next_dispatch_at = now() + timedelta(seconds=min(300, 2 ** job.attempts))
            try:
                publish_index(job.id)
                dispatched.append((job.id, job.repository_id))
            except Exception:
                logger.warning("index_publish_failed")
        embedding_jobs = db.scalars(select(EmbeddingJob).where(
            EmbeddingJob.next_dispatch_at <= now(),
            or_(EmbeddingJob.status == "pending", and_(EmbeddingJob.status == "running",
                or_(EmbeddingJob.lease_expires_at.is_(None), EmbeddingJob.lease_expires_at <= now())))
        ).order_by(EmbeddingJob.next_dispatch_at).limit(10).with_for_update(skip_locked=True))
        for job in embedding_jobs:
            if job.attempts >= 20:
                job.status, job.error_code, job.completed_at = "failed", "dispatch_exhausted", now()
                continue
            job.attempts += 1
            job.next_dispatch_at = now() + timedelta(seconds=min(300, 2 ** job.attempts))
            try:
                publish_embedding(job.id)
                dispatched_embeddings.append((job.id, job.repository_id))
            except Exception:
                logger.warning("embedding_publish_failed")
        events = db.scalars(select(InvestigationOutbox).where(
            InvestigationOutbox.status == "pending", InvestigationOutbox.next_dispatch_at <= now()
        ).order_by(InvestigationOutbox.next_dispatch_at).limit(10).with_for_update(skip_locked=True))
        for event in events:
            event.attempts += 1
            event.next_dispatch_at = now() + timedelta(seconds=min(300, 2 ** min(event.attempts, 9)))
            try:
                publish_investigation(event.job_id)
                dispatched_investigations.append((event.job_id, event.repository_id))
            except Exception:
                logger.warning("investigation_publish_failed")
        reports = db.scalars(select(InvestigationReportOutbox).where(
            InvestigationReportOutbox.status == "pending", InvestigationReportOutbox.next_dispatch_at <= now()
        ).order_by(InvestigationReportOutbox.next_dispatch_at).limit(10).with_for_update(skip_locked=True))
        for event in reports:
            event.attempts += 1
            event.next_dispatch_at = now() + timedelta(seconds=min(300, 2 ** min(event.attempts, 9)))
            try:
                publish_report(event.job_id)
                dispatched_reports.append((event.job_id, event.repository_id))
            except Exception:
                logger.warning("report_publish_failed")
    for job_id, repo_id in dispatched_reports:
        index_event("report_job_dispatched", job_id=job_id, repository_id=repo_id, task_id=job_id)
    for job_id, repo_id in dispatched_investigations:
        index_event("investigation_job_dispatched", job_id=job_id, repository_id=repo_id, task_id=job_id)
    for job_id, repo_id in dispatched:
        index_event("index_job_dispatched", job_id=job_id, repository_id=repo_id, task_id=job_id)
    for job_id, repo_id in dispatched_embeddings:
        index_event("embedding_job_dispatched", job_id=job_id, repository_id=repo_id, task_id=job_id)


def main():
    logging.basicConfig(level=logging.INFO,
                        format='{"level":"%(levelname)s","event":"%(message)s"}')
    while True:
        try:
            dispatch_once()
        except Exception:
            logger.error("outbox_dispatch_failed")
        time.sleep(2)


if __name__ == "__main__":
    main()
