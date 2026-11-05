"""Bounded, snapshot-fenced PostgreSQL keyword evidence retrieval."""
from dataclasses import dataclass
from hashlib import sha256
import json

from sqlalchemy import func, select, text

from app.domain.models import (CodeChunk, CodeSnapshot, IndexedFile, InvestigationEvidence,
                               InvestigationEvidenceManifest, SnapshotPublication, now)
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.keyword_search import keyword_statement
from app.modules.auth.session import utc


class SnapshotUnavailable(Exception):
    """The pinned snapshot is no longer published for this owner."""


class InvalidEvidence(Exception):
    """A returned chunk cannot be safely represented."""


@dataclass(frozen=True)
class Candidate:
    chunk_id: str
    file_id: str
    path: str
    symbol: str | None
    start_line: int
    end_line: int
    chunk_fingerprint: str
    query_id: str
    query_hash: str
    query_rank: int
    query_order: int



def fingerprint_chunk(chunk, file):
    """Detect later edits to the linked source or citation metadata, without storing source."""
    payload = [chunk.id, chunk.file_id, file.snapshot_id, file.path, file.content_hash,
               chunk.symbol, chunk.start_line, chunk.end_line, chunk.source_text]
    return sha256(json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()

def validate_snapshot(db, *, snapshot_id, repository_id, tenant_id, commit, lock=False):
    snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.id == snapshot_id,
        CodeSnapshot.repository_id == repository_id, CodeSnapshot.tenant_id == tenant_id,
        CodeSnapshot.commit_sha == commit, CodeSnapshot.published.is_(True)))
    if not snapshot:
        raise SnapshotUnavailable()
    stmt = select(SnapshotPublication).where(SnapshotPublication.snapshot_id == snapshot.id)
    publication = db.scalar(stmt.with_for_update() if lock else stmt)
    if publication and (publication.repository_id != repository_id or publication.tenant_id != tenant_id
                        or publication.commit_sha != commit or publication.revoked_at is not None
                        or publication.revocation_reason is not None
                        or (publication.file_count, publication.chunk_count, publication.skipped_count)
                        != (snapshot.file_count, snapshot.chunk_count, snapshot.skipped_count)):
        raise SnapshotUnavailable()
    return snapshot


def retrieve_candidates(factory, *, queries, snapshot_id, repository_id, tenant_id, commit,
                        full_name, per_query_limit, evidence_limit, ranking_context=None):
    """Run shared SQL against one snapshot; return IDs and metadata, never store source text."""
    if not 1 <= per_query_limit <= 20 or not 1 <= evidence_limit <= 30 or len(queries) > 3:
        raise ValueError("invalid_evidence_budget")
    if (ranking_context is not None and (not isinstance(ranking_context, tuple) or len(ranking_context) != 2
            or not all(isinstance(value, str) for value in ranking_context))):
        raise ValueError('invalid_ranking_context')
    best, baseline = {}, {}
    for order, query in enumerate(queries):
        with factory() as db:
            validate_snapshot(db, snapshot_id=snapshot_id, repository_id=repository_id,
                              tenant_id=tenant_id, commit=commit)
            if db.bind.dialect.name != "postgresql":
                raise InvalidEvidence("postgresql_required")
            db.execute(text("SET LOCAL statement_timeout = '3s'"))
            rows = db.execute(keyword_statement(repository_id=repository_id, tenant_id=tenant_id,
                snapshot_id=snapshot_id, query_text=query.text, limit=per_query_limit)).all()
            for rank, (chunk, file, _score) in enumerate(rows, 1):
                if (file.snapshot_id != snapshot_id or not chunk.source_text.strip()
                        or len(chunk.source_text.splitlines()) != chunk.end_line - chunk.start_line + 1):
                    raise InvalidEvidence("invalid_chunk")
                try:
                    github_citation(full_name, commit, file.path, chunk.start_line, chunk.end_line)
                except ValueError:
                    raise InvalidEvidence("invalid_citation") from None
                candidate = Candidate(chunk.id, file.id, file.path, chunk.symbol, chunk.start_line,
                    chunk.end_line, fingerprint_chunk(chunk, file), query.id,
                    sha256(query.text.encode()).hexdigest(), rank, order)
                previous = best.get(chunk.id)
                if previous is None or (rank, order) < (previous.query_rank, previous.query_order):
                    best[chunk.id] = candidate
                if ranking_context is not None and not query.id.startswith('body_'):
                    previous = baseline.get(chunk.id)
                    if previous is None or (rank, order) < (previous.query_rank, previous.query_order):
                        baseline[chunk.id] = candidate
    def ordered(values):
        return sorted(values, key=lambda c: (c.query_rank, c.query_order, c.path,
                                              c.start_line, c.chunk_id))[:evidence_limit]
    candidates = ordered(best.values())
    if ranking_context is None:
        return candidates
    from app.modules.investigation.ranking import protected_symbol_order
    original = ordered(baseline.values())
    def pairs(values):
        return [(candidate.chunk_id, candidate.symbol) for candidate in values]
    order = protected_symbol_order(*ranking_context, pairs(original), pairs(candidates), evidence_limit)
    lookup = {candidate.chunk_id: candidate for candidate in candidates}
    lookup.update({candidate.chunk_id: candidate for candidate in original[:min(4, evidence_limit)]})
    return [lookup[chunk_id] for chunk_id in order]


def load_verified_evidence(db, job, snapshot):
    """Load only complete, unchanged chunk references owned by the pinned snapshot."""
    rows = db.execute(select(InvestigationEvidence, CodeChunk, IndexedFile).join(CodeChunk,
        InvestigationEvidence.chunk_id == CodeChunk.id).join(IndexedFile,
        CodeChunk.file_id == IndexedFile.id).where(InvestigationEvidence.job_id == job.id,
        InvestigationEvidence.snapshot_id == snapshot.id, InvestigationEvidence.repository_id == job.repository_id,
        InvestigationEvidence.tenant_id == job.tenant_id, CodeChunk.repository_id == job.repository_id,
        CodeChunk.tenant_id == job.tenant_id, IndexedFile.repository_id == job.repository_id,
        IndexedFile.tenant_id == job.tenant_id, IndexedFile.snapshot_id == snapshot.id)
        .order_by(InvestigationEvidence.rank)).all()
    expected = db.scalar(select(func.count()).select_from(InvestigationEvidence).where(
        InvestigationEvidence.job_id == job.id))
    if (len(rows) != expected or expected > (job.evidence_limit or 0)
            or [item.rank for item, _, _ in rows] != list(range(1, len(rows) + 1))):
        raise InvalidEvidence("invalid_evidence")
    for item, chunk, file in rows:
        if (fingerprint_chunk(chunk, file) != item.chunk_fingerprint or chunk.start_line < 1
                or chunk.end_line < chunk.start_line
                or len(chunk.source_text.splitlines()) != chunk.end_line - chunk.start_line + 1):
            raise InvalidEvidence("invalid_evidence")
    manifest = db.get(InvestigationEvidenceManifest, job.id) if job.status == "completed" else None
    if manifest and (manifest.snapshot_id != snapshot.id or manifest.repository_id != job.repository_id
            or manifest.tenant_id != job.tenant_id or manifest.commit_sha != job.snapshot_commit_sha
            or manifest.version != "evidence-v1" or manifest.evidence_count != len(rows)
            or not job.completed_at or utc(manifest.recorded_at) > utc(job.completed_at)
            or manifest.digest != evidence_manifest_digest(job, rows)):
        raise InvalidEvidence("invalid_manifest")
    return rows


def evidence_manifest_digest(job, rows):
    """Hash a versioned, ordered and ownership-bound representation of saved evidence."""
    document = {"version": "evidence-v1", "job_id": job.id, "snapshot_id": job.snapshot_id,
                "repository_id": job.repository_id, "tenant_id": job.tenant_id,
                "commit_sha": job.snapshot_commit_sha,
                "items": [[item.id, item.chunk_id, item.rank, item.query_id, item.query_hash,
                           item.query_rank, item.method, item.chunk_fingerprint,
                           utc(item.created_at).isoformat(timespec="microseconds")]
                          for item, _, _ in rows]}
    return sha256(json.dumps(document, ensure_ascii=True, sort_keys=True,
                             separators=(",", ":")).encode("ascii")).hexdigest()


def record_evidence_manifest(db, job, snapshot):
    """Called once under the worker's job and snapshot locks, in its completion transaction."""
    db.flush()
    rows = load_verified_evidence(db, job, snapshot)
    db.add(InvestigationEvidenceManifest(job_id=job.id, snapshot_id=snapshot.id,
        repository_id=job.repository_id, tenant_id=job.tenant_id, commit_sha=snapshot.commit_sha,
        evidence_count=len(rows), digest=evidence_manifest_digest(job, rows), version="evidence-v1",
        recorded_at=now()))


def readable_snapshot(db, job, *, allow_historical=False, lock=False):
    """Require durable publication and a complete manifest for a superseded snapshot."""
    stmt = select(CodeSnapshot).where(CodeSnapshot.id == job.snapshot_id,
        CodeSnapshot.repository_id == job.repository_id, CodeSnapshot.tenant_id == job.tenant_id,
        CodeSnapshot.commit_sha == job.snapshot_commit_sha)
    snapshot = db.scalar(stmt.with_for_update() if lock else stmt)
    if not snapshot:
        raise SnapshotUnavailable()
    publication_stmt = select(SnapshotPublication).where(SnapshotPublication.snapshot_id == snapshot.id)
    publication = db.scalar(publication_stmt.with_for_update() if lock else publication_stmt)
    if publication and (publication.repository_id != job.repository_id or publication.tenant_id != job.tenant_id
                        or publication.commit_sha != job.snapshot_commit_sha or publication.revoked_at is not None
                        or publication.revocation_reason is not None
                        or (publication.file_count, publication.chunk_count, publication.skipped_count)
                        != (snapshot.file_count, snapshot.chunk_count, snapshot.skipped_count)):
        raise SnapshotUnavailable()
    historical = not snapshot.published
    if historical and (not allow_historical or job.status != "completed" or not publication
                       or utc(publication.published_at) > utc(job.created_at)):
        raise SnapshotUnavailable()
    manifest_stmt = select(InvestigationEvidenceManifest).where(InvestigationEvidenceManifest.job_id == job.id)
    manifest = db.scalar(manifest_stmt.with_for_update() if lock else manifest_stmt) if job.status == "completed" else None
    if historical and not manifest:
        raise SnapshotUnavailable()
    if manifest:
        load_verified_evidence(db, job, snapshot)
    return snapshot
