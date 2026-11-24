"""Reconstruct bounded, evidence-backed source from the pinned index."""
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select

from app.domain.models import CodeChunk, InvestigationEvidenceManifest
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.code_selection import contains_sensitive_source
from app.modules.investigation.retrieval import InvalidEvidence, load_verified_evidence
from app.modules.patches.validation import PatchError, PinnedFileIdentity, SourceFile, safe_path


@dataclass(frozen=True)
class Evidence:
    id: str
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    fingerprint: str
    citation: str


@dataclass(frozen=True, repr=False)
class PatchContext:
    investigation_id: str
    snapshot_id: str
    commit_sha: str
    issue_id: int
    title: str
    body: str
    files: tuple[SourceFile, ...]
    evidence: tuple[Evidence, ...]
    repository_id: int
    repository_full_name: str
    tenant_id: int


def assemble_context(db, parent, snapshot, *, title="", body="") -> PatchContext:
    """Fail closed on missing manifests, source gaps, and hash mismatch."""
    if (parent.status != "completed" or parent.operation != "code_evidence"
            or parent.snapshot_id != snapshot.id or parent.snapshot_commit_sha != snapshot.commit_sha
            or parent.repository_id != snapshot.repository_id or parent.tenant_id != snapshot.tenant_id
            or not db.get(InvestigationEvidenceManifest, parent.id)):
        raise PatchError("invalid_snapshot_or_manifest")
    try:
        rows = load_verified_evidence(db, parent, snapshot)
    except InvalidEvidence:
        raise PatchError("invalid_evidence") from None
    selected = {}
    refs = []
    for ev, chunk, file in rows:
        if not safe_path(file.path):
            continue
        if file.id not in selected and len(selected) >= 5:
            continue
        selected.setdefault(file.id, [file, []])[1].append(ev.id)
        refs.append(Evidence(ev.id, chunk.id, file.path, chunk.start_line, chunk.end_line,
            ev.chunk_fingerprint, github_citation(parent.source_repository_name, snapshot.commit_sha,
                                                  file.path, chunk.start_line, chunk.end_line)))
    if not selected:
        raise PatchError("no_eligible_evidence")
    files = []
    total = 0
    for file, evidence_ids in selected.values():
        chunks = db.scalars(select(CodeChunk).where(CodeChunk.file_id == file.id,
            CodeChunk.repository_id == parent.repository_id, CodeChunk.tenant_id == parent.tenant_id)
            .order_by(CodeChunk.start_line).limit(5001)).all()
        if not chunks or len(chunks) > 5000:
            raise PatchError("incomplete_source")
        position, parts = 1, []
        for chunk in chunks:
            if (chunk.start_line != position or chunk.end_line < position
                    or len(chunk.source_text.splitlines()) != chunk.end_line - position + 1):
                raise PatchError("incomplete_source")
            parts.append(chunk.source_text)
            position = chunk.end_line + 1
        try:
            source = "".join(parts)
            content = source.encode("utf-8")
        except UnicodeEncodeError:
            raise PatchError("invalid_source_encoding") from None
        total += len(content)
        if (len(content) > 128 * 1024 or total > 256 * 1024
                or sha256(content).hexdigest() != file.content_hash):
            raise PatchError("source_identity_or_size")
        if contains_sensitive_source(source):
            raise PatchError("sensitive_source")
        identity = None
        if file.source_coverage == "COMPLETE_FILE":
            # A claimed complete-file identity must match the reconstructed bytes.
            # Historical UNKNOWN_COVERAGE records remain eligible as unknown.
            if (type(file.source_byte_length) is not int or file.source_byte_length != len(content)
                    or file.source_encoding != "utf-8" or file.source_normalization != "identity"):
                raise PatchError("source_identity_or_size")
            identity = PinnedFileIdentity(snapshot.id, snapshot.commit_sha, parent.repository_id, parent.tenant_id,
                                          file.id, file.path, file.content_hash, file.source_byte_length, True)
        files.append(SourceFile(file.path, content, file.content_hash, file.id, tuple(evidence_ids), identity))
    return PatchContext(parent.id, snapshot.id, snapshot.commit_sha, parent.issue_id,
                        title[:1024], body[:16000], tuple(files), tuple(refs),
                        parent.repository_id, parent.source_repository_name, parent.tenant_id)
