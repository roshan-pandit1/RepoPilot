"""Atomic publication of already-filtered code snapshots."""
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, Repository
from app.modules.ingestion.code_collect import Collection
from app.modules.ingestion.code_snapshot import SnapshotPlan


def publish_snapshot(db: Session, repository: Repository, plan: SnapshotPlan,
                     collection: Collection) -> CodeSnapshot:
    """Write and publish inside the caller's transaction after authorization recheck.

    The caller must hold the repository row lock. Any exception rolls back the new data and
    the old publication change together. Repository content must already be filtered.
    """
    previous = db.scalars(select(CodeSnapshot).where(
        CodeSnapshot.repository_id == repository.id, CodeSnapshot.tenant_id == repository.tenant_id,
        CodeSnapshot.published.is_(True)).with_for_update()).all()
    for snapshot in previous:
        snapshot.published = False
    db.flush()
    snapshot = CodeSnapshot(id=str(uuid4()), repository_id=repository.id,
                            tenant_id=repository.tenant_id, commit_sha=plan.commit_sha,
                            published=True, file_count=len(collection.files),
                            chunk_count=sum(len(item.chunks) for item in collection.files),
                            skipped_count=collection.skipped_files)
    db.add(snapshot)
    db.flush()
    for item in collection.files:
        file = IndexedFile(id=str(uuid4()), snapshot_id=snapshot.id, repository_id=repository.id,
                           tenant_id=repository.tenant_id, path=item.path, content_hash=item.content_hash)
        db.add(file)
        db.flush()
        for chunk in item.chunks:
            db.add(CodeChunk(id=str(uuid4()), file_id=file.id, repository_id=repository.id,
                             tenant_id=repository.tenant_id, symbol=chunk.symbol,
                             start_line=chunk.start_line, end_line=chunk.end_line,
                             source_text=chunk.text))
    db.flush()
    return snapshot
