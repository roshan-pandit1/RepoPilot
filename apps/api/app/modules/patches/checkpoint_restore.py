"""Verify an owner-only capture and re-submit it through the existing authorized API.

This module never grants approval, invokes Ollama, or inserts application records.
A restoration creates new investigation/evidence identities; the old request is
therefore never an authorization for the regenerated request.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
from uuid import UUID

import httpx

from app.modules.ingestion.citations import github_citation
from app.modules.investigation.report_model import sanitize_issue_text
from app.modules.investigation.retrieval import fingerprint_chunk
from app.modules.patches.context import Evidence, PatchContext
from app.modules.patches.generation import build_candidate_request
from app.modules.patches.ollama_provider import OllamaPatchProvider
from app.modules.patches.validation import PatchError, PinnedFileIdentity, SourceFile


class CheckpointError(ValueError):
    """A bounded checkpoint cannot safely be used to start restoration."""


@dataclass(frozen=True)
class ExpectedFile:
    path: str
    byte_length: int
    sha256: str
    git_blob_sha1: str


@dataclass(frozen=True)
class ExpectedPilot:
    target_repository_id: int
    target_repository_name: str
    origin_repository_id: int
    origin_repository_name: str
    issue_id: int
    issue_number: int
    issue_title: str
    issue_body_sha256: str
    commit_sha: str
    original_snapshot_id: str
    original_investigation_id: str
    original_manifest_sha256: str
    original_request_sha256: str
    original_request_bytes: int
    model: str
    model_sha256: str
    files: tuple[ExpectedFile, ...]


@dataclass(frozen=True, repr=False)
class VerifiedCheckpoint:
    expected: ExpectedPilot
    context: PatchContext
    old_request: bytes
    # No caller may assume these UUIDs represent records in the current DB.


def _json_no_duplicates(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise CheckpointError("checkpoint_invalid") from None
    if not isinstance(value, dict):
        raise CheckpointError("checkpoint_invalid")
    return value


def _private_directory(path):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(os.fspath(path), flags)
        st = os.fstat(fd)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid()
                or stat.S_IMODE(st.st_mode) != 0o700):
            os.close(fd)
            raise CheckpointError("checkpoint_permissions_invalid")
        return fd
    except OSError:
        raise CheckpointError("checkpoint_unavailable") from None


def _read_at(directory_fd, name, limit):
    if name not in {"context.json", "manifest.json", "metadata.json", "request.json", "issue-body.txt"}:
        raise CheckpointError("checkpoint_invalid")
    try:
        fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory_fd)
        try:
            st = os.fstat(fd)
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1
                    or stat.S_IMODE(st.st_mode) != 0o600 or st.st_size > limit):
                raise CheckpointError("checkpoint_permissions_invalid")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                data = stream.read(limit + 1)
            if len(data) != st.st_size or len(data) > limit:
                raise CheckpointError("checkpoint_invalid")
            return data
        finally:
            os.close(fd)
    except OSError:
        raise CheckpointError("checkpoint_unavailable") from None


class _BodyStream(httpx.AsyncByteStream):
    def __init__(self, content):
        self.content = content

    async def __aiter__(self):
        yield self.content


def capture_request(context: PatchContext, *, model: str, digest: str) -> bytes:
    """Capture the production adapter's HTTP body through a no-network mock only."""
    observed = []
    def handler(request):
        if request.url.host != "127.0.0.1" or request.url.port != 11434:
            raise CheckpointError("capture_unexpected_endpoint")
        if request.url.path == "/api/status":
            payload = {"cloud": {"disabled": True}}
        elif request.url.path == "/api/tags":
            payload = {"models": [{"name": model, "digest": digest, "size": 1,
                                   "details": {"format": "gguf"}}]}
        elif request.url.path == "/api/show":
            payload = {"details": {"format": "gguf"}, "capabilities": ["completion"]}
        elif request.url.path == "/api/chat":
            observed.append(request.content)
            # A failed synthetic response terminates the adapter before output parsing.
            return httpx.Response(503, stream=_BodyStream(b""))
        else:
            raise CheckpointError("capture_unexpected_endpoint")
        return httpx.Response(200, stream=_BodyStream(json.dumps(payload).encode("utf-8")))

    adapter = OllamaPatchProvider(model, digest, "http://127.0.0.1:11434",
                                  strategy="source_edits", transport=httpx.MockTransport(handler))
    try:
        adapter.generate(build_candidate_request(context), timeout_seconds=30)
    except PatchError as exc:
        if str(exc) != "local_provider_request_failed" or len(observed) != 1:
            raise CheckpointError("request_capture_failed") from None
    if len(observed) != 1:
        raise CheckpointError("request_capture_failed")
    return observed[0]


def load_checkpoint(root: Path, expected: ExpectedPilot) -> VerifiedCheckpoint:
    """Verify an original capture against independently supplied expected identities."""
    return _load_checkpoint(root, expected, predecessor=None)


def load_restored_checkpoint(root: Path, expected: ExpectedPilot, *,
                             predecessor: VerifiedCheckpoint) -> VerifiedCheckpoint:
    """Verify a restored capture against an already verified predecessor and new IDs.

    The predecessor and expected values must be established by a trusted caller;
    this offline check does not establish that any current database records exist.
    A restored capture never inherits the old request's approval.
    """
    if not isinstance(expected, ExpectedPilot) or not isinstance(predecessor, VerifiedCheckpoint):
        raise CheckpointError("checkpoint_expectations_required")
    previous = predecessor.expected
    baseline = replace(expected, original_snapshot_id=previous.original_snapshot_id,
        original_investigation_id=previous.original_investigation_id,
        original_request_sha256=previous.original_request_sha256,
        original_request_bytes=previous.original_request_bytes)
    if (baseline != previous or expected.original_snapshot_id == previous.original_snapshot_id
            or expected.original_investigation_id == previous.original_investigation_id
            or expected.original_request_sha256 == previous.original_request_sha256):
        raise CheckpointError("checkpoint_expectations_invalid")
    return _load_checkpoint(root, expected, predecessor=predecessor)


def _load_checkpoint(root: Path, expected: ExpectedPilot, *,
                     predecessor: VerifiedCheckpoint | None) -> VerifiedCheckpoint:
    """Recheck private bytes; in-directory hashes are never a trust anchor."""
    if not isinstance(expected, ExpectedPilot):
        raise CheckpointError("checkpoint_expectations_required")
    fd = _private_directory(root)
    parent_fd = _private_directory(Path(root).parent)
    try:
        metadata = _json_no_duplicates(_read_at(fd, "metadata.json", 8192))
        if predecessor is not None:
            if (metadata.get("run") != "p192_restored" or metadata.get("old_request_transferred") is not False
                    or type(metadata.get("actual_model_inference")) is not int
                    or metadata["actual_model_inference"] != 0
                    or type(metadata.get("source_provider_network_calls")) is not int
                    or metadata["source_provider_network_calls"] != 0):
                raise CheckpointError("checkpoint_invalid")
            # The restored writer omitted these repeated fields.  They may only be
            # inherited from a separately validated predecessor, never from the file.
            inherited = {"issue_body_sha256": expected.issue_body_sha256,
                         "origin_repository_id": expected.origin_repository_id,
                         "issue_id": expected.issue_id, "model": expected.model,
                         "model_sha256": expected.model_sha256}
            for key, value in inherited.items():
                if key in metadata and metadata[key] != value:
                    raise CheckpointError("checkpoint_identity_mismatch")
                metadata[key] = value
        manifest = _json_no_duplicates(_read_at(fd, "manifest.json", 16384))
        data = _json_no_duplicates(_read_at(fd, "context.json", 524288))
        wire = _read_at(fd, "request.json", 524288)
        issue_body = _read_at(parent_fd, "issue-body.txt", 64000)
        source_metadata = _json_no_duplicates(_read_at(parent_fd, "metadata.json", 8192))
    finally:
        os.close(fd)
        os.close(parent_fd)
    try:
        body = issue_body.decode("utf-8", errors="strict")
        if (source_metadata.get("repository") != expected.target_repository_name
                or source_metadata.get("repository_id") != expected.target_repository_id
                or source_metadata.get("parent") != expected.origin_repository_name
                or source_metadata.get("private") is not False
                or source_metadata.get("pinned_commit") != expected.commit_sha
                or source_metadata.get("issue_number") != expected.issue_number
                or source_metadata.get("issue_title") != expected.issue_title
                or source_metadata.get("issue_url") != f"https://github.com/{expected.origin_repository_name}/issues/{expected.issue_number}"
                or source_metadata.get("issue_body_sha256") != expected.issue_body_sha256
                or sha256(issue_body).hexdigest() != expected.issue_body_sha256
                or metadata["issue_body_sha256"] != expected.issue_body_sha256
                or metadata["origin_repository_id"] != expected.origin_repository_id
                or metadata["issue_id"] != expected.issue_id or metadata["model"] != expected.model
                or metadata["model_sha256"] != expected.model_sha256
                or metadata["snapshot_id"] != expected.original_snapshot_id
                or metadata["job_id"] != expected.original_investigation_id
                or metadata["request_sha256"] != expected.original_request_sha256
                or metadata["request_bytes"] != expected.original_request_bytes
                or len(wire) != expected.original_request_bytes
                or sha256(wire).hexdigest() != expected.original_request_sha256
                or metadata["manifest_sha256"] != expected.original_manifest_sha256
                or data["repository_id"] != expected.target_repository_id
                or data["repository_full_name"] != expected.target_repository_name
                or data["issue_id"] != expected.issue_id or data["commit_sha"] != expected.commit_sha
                or data["investigation_id"] != expected.original_investigation_id
                or data["snapshot_id"] != expected.original_snapshot_id
                or data["title"] != sanitize_issue_text(expected.issue_title, 1024)
                or data["body"] != sanitize_issue_text(body, 16000)):
            raise CheckpointError("checkpoint_identity_mismatch")
        encoded = json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
        if (sha256(encoded).hexdigest() != expected.original_manifest_sha256
                or manifest["version"] != "partial-source-manifest-v1"
                or manifest["inventory_coverage"] != "PARTIAL_INVENTORY"
                or manifest["repository_id"] != expected.target_repository_id
                or manifest["repository_full_name"] != expected.target_repository_name
                or manifest["tenant_id"] != data["tenant_id"] or manifest["commit_sha"] != expected.commit_sha):
            raise CheckpointError("checkpoint_manifest_mismatch")
        expected_files = {item.path: item for item in expected.files}
        if len(expected_files) != len(expected.files) or not 1 <= len(expected_files) <= 5:
            raise CheckpointError("checkpoint_expectations_invalid")
        entries = manifest["files"]
        if not isinstance(entries, list) or [item["path"] for item in entries] != sorted(expected_files):
            raise CheckpointError("checkpoint_manifest_mismatch")
        files = []
        for record in data["files"]:
            spec = expected_files[record["path"]]
            raw = base64.b64decode(record["content"]["base64"], validate=True)
            if (len(raw) != spec.byte_length or sha256(raw).hexdigest() != spec.sha256
                    or sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest() != spec.git_blob_sha1
                    or record["sha256"] != spec.sha256):
                raise CheckpointError("checkpoint_source_mismatch")
            ident = PinnedFileIdentity(**record["pinned_identity"])
            files.append(SourceFile(record["path"], raw, record["sha256"], record["file_id"],
                                    tuple(record["evidence_ids"]), ident))
        if set(f.path for f in files) != set(expected_files) or len(files) != len(expected_files):
            raise CheckpointError("checkpoint_source_mismatch")
        for entry in entries:
            spec = expected_files[entry["path"]]
            if entry != {"path": spec.path, "byte_length": spec.byte_length, "sha256": spec.sha256,
                         "git_blob_sha1": spec.git_blob_sha1, "encoding": "utf-8",
                         "normalization": "identity", "coverage": "COMPLETE_FILE"}:
                raise CheckpointError("checkpoint_manifest_mismatch")
        evidence = tuple(Evidence(**row) for row in data["evidence"])
        file_map = {file.path: file for file in files}
        for ref in evidence:
            file = file_map[ref.path]
            lines = file.content.decode("utf-8", errors="strict").splitlines(keepends=True)
            if not 1 <= ref.start_line <= ref.end_line <= len(lines):
                raise CheckpointError("checkpoint_evidence_mismatch")
            chunk = SimpleNamespace(id=ref.chunk_id, file_id=file.file_id, symbol=None,
                start_line=ref.start_line, end_line=ref.end_line,
                source_text="".join(lines[ref.start_line - 1:ref.end_line]))
            indexed_file = SimpleNamespace(snapshot_id=data["snapshot_id"], path=file.path,
                                            content_hash=file.sha256)
            if (fingerprint_chunk(chunk, indexed_file) != ref.fingerprint
                    or github_citation(expected.target_repository_name, expected.commit_sha, ref.path,
                                       ref.start_line, ref.end_line) != ref.citation):
                raise CheckpointError("checkpoint_evidence_mismatch")
        if metadata["evidence_ids"] != [item.id for item in evidence]:
            raise CheckpointError("checkpoint_evidence_mismatch")
        context = PatchContext(data["investigation_id"], data["snapshot_id"], data["commit_sha"],
            data["issue_id"], data["title"], data["body"], tuple(files), evidence,
            data["repository_id"], data["repository_full_name"], data["tenant_id"])
        if capture_request(context, model=expected.model, digest=expected.model_sha256) != wire:
            raise CheckpointError("checkpoint_request_mismatch")
        if predecessor is not None:
            previous_ranges = sorted((e.path, e.start_line, e.end_line) for e in predecessor.context.evidence)
            current_ranges = sorted((e.path, e.start_line, e.end_line) for e in context.evidence)
            if (previous_ranges != current_ranges
                    or {f.path: f.sha256 for f in predecessor.context.files}
                       != {f.path: f.sha256 for f in context.files}):
                raise CheckpointError("checkpoint_evidence_mismatch")
        return VerifiedCheckpoint(expected, context, wire)
    except CheckpointError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError, AttributeError, OverflowError):
        raise CheckpointError("checkpoint_invalid") from None


def submit_restoration(client, checkpoint: VerifiedCheckpoint, *, csrf_headers: dict) -> str:
    """Re-enter through authenticated existing API; do not insert trusted records directly.

    The endpoint rechecks the live GitHub direct-parent, issue, commit and blob
    identities and creates a new job and scoped snapshot. An existing worker must
    later complete the investigation; this helper never calls a provider.
    """
    if not isinstance(checkpoint, VerifiedCheckpoint) or not isinstance(csrf_headers, dict):
        raise CheckpointError("checkpoint_invalid")
    expected = checkpoint.expected
    payload = {"parent_repository_id": expected.origin_repository_id, "issue_id": expected.issue_id,
               "issue_body_sha256": expected.issue_body_sha256, "commit_sha": expected.commit_sha,
               "branch": "main", "files": [{"path": f.path, "byte_length": f.byte_length,
               "sha256": f.sha256, "git_blob_sha1": f.git_blob_sha1} for f in expected.files]}
    response = client.post(f"/v1/repositories/{expected.target_repository_id}/upstream-issues/"
                           f"{expected.issue_number}/investigations", json=payload, headers=csrf_headers)
    if response.status_code != 202:
        raise CheckpointError("restoration_submission_failed")
    try:
        job_id = response.json()["job_id"]
        if str(UUID(job_id)) != job_id:
            raise ValueError("invalid job")
        return job_id
    except (ValueError, TypeError, KeyError, AttributeError):
        raise CheckpointError("restoration_submission_failed") from None


def verify_restored_context(db, job_id: str, checkpoint: VerifiedCheckpoint, *, identity, github) -> PatchContext:
    """Reauthorize and independently revalidate a newly persisted investigation.

    No old UUID is inserted or assumed valid. Evidence ranges must match the
    validated checkpoint semantically, while fresh application UUIDs and tenant
    ownership come from the actual authenticated investigation. Remote issue
    and repository authorization are checked again; no provider is called.
    """
    from sqlalchemy import select
    from app.domain.models import InvestigationIssueOrigin, InvestigationJob
    from app.modules.github.issue_context import authorize
    from app.modules.investigation.report_routes import lock_report_read_access
    from app.modules.investigation.routes import _refresh_upstream, _saved_upstream
    from app.modules.investigation.retrieval import readable_snapshot
    from app.modules.patches.context import assemble_context

    if not isinstance(checkpoint, VerifiedCheckpoint):
        raise CheckpointError("checkpoint_invalid")
    expected = checkpoint.expected
    try:
        if str(UUID(job_id)) != job_id:
            raise CheckpointError("restored_identity_mismatch")
        name = authorize(expected.target_repository_id, identity, db, github)
        if name != expected.target_repository_name:
            raise CheckpointError("restored_identity_mismatch")
        job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == job_id,
            InvestigationJob.repository_id == expected.target_repository_id,
            InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id))
        if not job or job.status != "completed" or job.operation != "code_evidence":
            raise CheckpointError("restored_investigation_incomplete")
        saved = _saved_upstream(job, db.get(InvestigationIssueOrigin, job.id), name)
        if (not saved or saved.origin_repository_id != expected.origin_repository_id
                or saved.origin_repository_name != expected.origin_repository_name
                or saved.issue_id != expected.issue_id or saved.issue_number != expected.issue_number
                or saved.issue_title != expected.issue_title or saved.issue_body_sha256 != expected.issue_body_sha256
                or job.snapshot_commit_sha != expected.commit_sha):
            raise CheckpointError("restored_identity_mismatch")
        db.rollback()
        _refresh_upstream(saved, identity, github)
        if authorize(expected.target_repository_id, identity, db, github) != name:
            raise CheckpointError("restored_identity_mismatch")
        lock_report_read_access(db, expected.target_repository_id, identity, name)
        job = db.scalar(select(InvestigationJob).where(InvestigationJob.id == job_id,
            InvestigationJob.repository_id == expected.target_repository_id,
            InvestigationJob.tenant_id == identity.tenant_id, InvestigationJob.user_id == identity.user_id)
            .execution_options(populate_existing=True))
        if (not job or job.status != "completed"
                or _saved_upstream(job, db.get(InvestigationIssueOrigin, job.id), name) != saved):
            raise CheckpointError("restored_identity_mismatch")
        snapshot = readable_snapshot(db, job, lock=True)
        if snapshot.inventory_coverage != "PARTIAL_INVENTORY" or snapshot.published:
            raise CheckpointError("restored_identity_mismatch")
        entries = snapshot.inventory_manifest.get("files")
        wanted = [{"path": f.path, "byte_length": f.byte_length, "sha256": f.sha256,
                   "git_blob_sha1": f.git_blob_sha1, "encoding": "utf-8", "normalization": "identity",
                   "coverage": "COMPLETE_FILE"} for f in sorted(expected.files, key=lambda f: f.path)]
        if entries != wanted:
            raise CheckpointError("restored_source_mismatch")
        context = assemble_context(db, job, snapshot, title=checkpoint.context.title, body=checkpoint.context.body)
        original_ranges = sorted((e.path, e.start_line, e.end_line) for e in checkpoint.context.evidence)
        restored_ranges = sorted((e.path, e.start_line, e.end_line) for e in context.evidence)
        if (restored_ranges != original_ranges or len(restored_ranges) != len(set(restored_ranges))
                or {f.path: f.sha256 for f in context.files} != {f.path: f.sha256 for f in expected.files}
                or any(f.pinned_identity is None for f in context.files)):
            raise CheckpointError("restored_evidence_mismatch")
        build_candidate_request(context)
        return context
    except CheckpointError:
        raise
    except Exception:
        # Do not leak credentials, issue text, source or internal storage paths.
        raise CheckpointError("restoration_verification_failed") from None
