"""Atomic publication of already-filtered code snapshots."""
from uuid import uuid4
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import (CodeChunk, CodeSnapshot, IndexedFile, PartialSnapshotScope,
                               Repository, SnapshotPublication, now)
from app.modules.ingestion.code_collect import Collection
from app.modules.ingestion.code_snapshot import SnapshotPlan


def publish_snapshot(db: Session, repository: Repository, plan: SnapshotPlan,
                     collection: Collection) -> CodeSnapshot:
    """Write and publish inside the caller's transaction after authorization recheck.

    The caller must hold the repository row lock. Any exception rolls back the new data and
    the old publication change together. Repository content must already be filtered.
    """
    provenance = []
    for item in collection.files:
        complete = item.source_coverage == "COMPLETE_FILE"
        if complete:
            if (type(item.source_byte_length) is not int or item.source_byte_length < 0
                    or item.source_encoding != "utf-8" or item.source_normalization != "identity"):
                raise ValueError("source_provenance_metadata_invalid")
            try:
                reconstructed = "".join(chunk.text for chunk in item.chunks).encode("utf-8")
            except (AttributeError, UnicodeEncodeError):
                raise ValueError("source_provenance_source_invalid") from None
            if (len(reconstructed) != item.source_byte_length
                    or sha256(reconstructed).hexdigest() != item.content_hash):
                raise ValueError("source_provenance_identity_mismatch")
        provenance.append(complete)

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
                            skipped_count=collection.skipped_files,
                            indexing_mode="multilingual" if plan.multilingual else "python",
                            unsupported_count=plan.unsupported_files)
    db.add(snapshot)
    db.flush()
    db.add(SnapshotPublication(snapshot_id=snapshot.id, repository_id=repository.id,
                               tenant_id=repository.tenant_id, commit_sha=snapshot.commit_sha,
                               file_count=snapshot.file_count, chunk_count=snapshot.chunk_count,
                               skipped_count=snapshot.skipped_count))
    _persist_snapshot_files(db, repository, snapshot, collection, provenance)
    return snapshot


def _persist_snapshot_files(db, repository, snapshot, collection, provenance):
    for item, complete in zip(collection.files, provenance, strict=True):
        file = IndexedFile(id=str(uuid4()), snapshot_id=snapshot.id, repository_id=repository.id,
                           tenant_id=repository.tenant_id, path=item.path, content_hash=item.content_hash,
                           language=item.language, parser_version=item.parser_version,
                           parser_status=item.parser_status, import_ranges=item.import_ranges,
                           source_byte_length=item.source_byte_length if complete else None,
                           source_encoding=item.source_encoding if complete else None,
                           source_normalization=item.source_normalization if complete else None,
                           source_coverage="COMPLETE_FILE" if complete else "UNKNOWN_COVERAGE")
        db.add(file)
        db.flush()
        for chunk in item.chunks:
            db.add(CodeChunk(id=str(uuid4()), file_id=file.id, repository_id=repository.id,
                             tenant_id=repository.tenant_id, symbol=chunk.symbol,
                             symbol_kind=chunk.symbol_kind,
                             start_line=chunk.start_line, end_line=chunk.end_line,
                             source_text=chunk.text))
    db.flush()



def persist_partial_snapshot(db: Session, repository: Repository, plan: SnapshotPlan,
                             collection: Collection) -> CodeSnapshot:
    """Persist a bounded inventory without changing any repository-wide publication.

    The caller must lock/re-authorize the repository, use an independently verified
    commit-resolved plan, and bind this snapshot to one job in the same transaction.
    This function does not authorize input or create an investigation on its own.
    """
    from app.modules.ingestion.partial_snapshot import build_partial_manifest
    manifest, digest = build_partial_manifest(repository_id=repository.id, tenant_id=repository.tenant_id,
        repository_full_name=repository.full_name, plan=plan, collection=collection)
    snapshot = CodeSnapshot(id=str(uuid4()), repository_id=repository.id, tenant_id=repository.tenant_id,
        commit_sha=plan.commit_sha, published=False, file_count=len(collection.files),
        chunk_count=sum(len(item.chunks) for item in collection.files), skipped_count=0,
        indexing_mode="multilingual", unsupported_count=0, inventory_coverage="PARTIAL_INVENTORY",
        inventory_manifest=manifest, inventory_manifest_sha256=digest)
    db.add(snapshot)
    db.flush()
    # This record provides the existing revocation fence; the snapshot remains
    # unpublished globally and is readable only through its investigation scope.
    db.add(SnapshotPublication(snapshot_id=snapshot.id, repository_id=repository.id,
        tenant_id=repository.tenant_id, commit_sha=snapshot.commit_sha, file_count=snapshot.file_count,
        chunk_count=snapshot.chunk_count, skipped_count=snapshot.skipped_count))
    _persist_snapshot_files(db, repository, snapshot, collection, [True] * len(collection.files))
    return snapshot


def bind_partial_snapshot(db: Session, job, snapshot: CodeSnapshot) -> None:
    """Bind a partial inventory to one same-owner investigation in the caller transaction."""
    if (snapshot.inventory_coverage != "PARTIAL_INVENTORY" or snapshot.published
            or job.snapshot_id != snapshot.id or job.repository_id != snapshot.repository_id
            or job.tenant_id != snapshot.tenant_id or job.snapshot_commit_sha != snapshot.commit_sha
            or not snapshot.inventory_manifest_sha256):
        raise ValueError("partial_snapshot_scope_invalid")
    db.add(PartialSnapshotScope(job_id=job.id, snapshot_id=snapshot.id, repository_id=snapshot.repository_id,
        tenant_id=snapshot.tenant_id, manifest_sha256=snapshot.inventory_manifest_sha256))
    db.flush()
    from app.modules.investigation.retrieval import validate_snapshot
    validate_snapshot(db, snapshot_id=snapshot.id, repository_id=snapshot.repository_id,
        tenant_id=snapshot.tenant_id, commit=snapshot.commit_sha, job_id=job.id, lock=True)



def revoke_snapshot(db: Session, repository: Repository, snapshot_id: str, reason: str) -> None:
    """Revoke a recorded publication under the caller's repository lock; no public mutation API."""
    if reason not in {"security", "integrity"}:
        raise ValueError("invalid_snapshot_revocation_reason")
    snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.id == snapshot_id,
        CodeSnapshot.repository_id == repository.id, CodeSnapshot.tenant_id == repository.tenant_id).with_for_update())
    publication = db.scalar(select(SnapshotPublication).where(
        SnapshotPublication.snapshot_id == snapshot_id, SnapshotPublication.repository_id == repository.id,
        SnapshotPublication.tenant_id == repository.tenant_id).with_for_update())
    if not snapshot or not publication or publication.commit_sha != snapshot.commit_sha:
        raise ValueError("snapshot_publication_unavailable")
    if publication.revoked_at is None:
        publication.revoked_at, publication.revocation_reason = now(), reason
