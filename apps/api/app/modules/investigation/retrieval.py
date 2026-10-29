"""Bounded, snapshot-fenced PostgreSQL keyword evidence retrieval."""
from dataclasses import dataclass
from hashlib import sha256
import json

from sqlalchemy import func, select, text

from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, InvestigationEvidence
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.keyword_search import keyword_statement


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

def validate_snapshot(db, *, snapshot_id, repository_id, tenant_id, commit):
    snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.id == snapshot_id,
        CodeSnapshot.repository_id == repository_id, CodeSnapshot.tenant_id == tenant_id,
        CodeSnapshot.commit_sha == commit, CodeSnapshot.published.is_(True)))
    if not snapshot:
        raise SnapshotUnavailable()
    return snapshot


def retrieve_candidates(factory, *, queries, snapshot_id, repository_id, tenant_id, commit,
                        full_name, per_query_limit, evidence_limit):
    """Run shared SQL against one snapshot; return IDs and metadata, never store source text."""
    if not 1 <= per_query_limit <= 20 or not 1 <= evidence_limit <= 30 or len(queries) > 3:
        raise ValueError("invalid_evidence_budget")
    best = {}
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
    return sorted(best.values(), key=lambda c: (c.query_rank, c.query_order, c.path,
                                                  c.start_line, c.chunk_id))[:evidence_limit]


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
    return rows
