"""Describe only source coverage supported by a trusted, pinned file record."""
from hashlib import sha256
import re
from uuid import UUID

from app.modules.patches.validation import PatchError, PinnedFileIdentity, safe_path


COVERAGE_VERSION = "source-coverage-v1"
COMPLETE_FILE = "COMPLETE_FILE"
BOUNDED_EXCERPT = "BOUNDED_EXCERPT"
UNKNOWN_COVERAGE = "UNKNOWN_COVERAGE"

_NOTICES = {
    COMPLETE_FILE: "This is the complete content of the supplied file. No additional source lines from this file are omitted.",
    BOUNDED_EXCERPT: "This is an excerpt. Other lines from the file may be omitted.",
    UNKNOWN_COVERAGE: "Source coverage is unknown. Other lines from the file may or may not be omitted.",
}


def _uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def verified_identity(identity, *, snapshot_id, commit_sha, repository_id, tenant_id,
                      file_id, path, digest, source):
    """Check an internally supplied record against its pinned context and actual bytes.

    The record is trusted only when supplied by an authenticated inventory. Existing
    IndexedFile records lack independently retained lengths, so their identity is absent.
    """
    if identity is None:
        return False
    if not isinstance(identity, PinnedFileIdentity) or type(identity.file_record_complete) is not bool:
        raise PatchError("invalid_provider_request")
    if not identity.file_record_complete:
        return False
    if (not isinstance(source, bytes) or not _uuid(snapshot_id) or not _uuid(file_id)
            or not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha)
            or type(repository_id) is not int or repository_id <= 0
            or type(tenant_id) is not int or tenant_id <= 0 or not safe_path(path)
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or type(identity.byte_length) is not int or identity.byte_length < 0
            or identity.snapshot_id != snapshot_id or identity.commit_sha != commit_sha
            or identity.repository_id != repository_id or identity.tenant_id != tenant_id
            or identity.file_id != file_id or identity.path != path or identity.sha256 != digest
            or identity.byte_length != len(source) or sha256(source).hexdigest() != digest):
        raise PatchError("invalid_provider_request")
    return True


def describe_coverage(*, identity, snapshot_id, commit_sha, repository_id, tenant_id, file_id,
                      path, digest, source, start_line, end_line, start_byte, end_byte, snippet):
    """Validate LF line and UTF-8 byte ranges before describing their extent.

    Byte offsets are zero-based and end-exclusive. Unknown full-file boundaries are never
    emitted merely because a snippet reaches the end of a visible reconstruction.
    """
    if (not isinstance(source, bytes) or not isinstance(snippet, bytes) or not source
            or b"\0" in source or b"\r" in source or not source.endswith(b"\n")
            or not isinstance(digest, str) or sha256(source).hexdigest() != digest
            or any(type(value) is not int for value in (start_line, end_line, start_byte, end_byte))):
        raise PatchError("invalid_provider_request")
    try:
        source.decode("utf-8")
        snippet.decode("utf-8")
    except UnicodeDecodeError:
        raise PatchError("invalid_provider_request") from None
    lines = [part + b"\n" for part in source.split(b"\n")[:-1]]
    if not (1 <= start_line <= end_line <= len(lines)):
        raise PatchError("invalid_provider_request")
    expected_start = sum(map(len, lines[:start_line - 1]))
    expected_end = sum(map(len, lines[:end_line]))
    if (start_byte != expected_start or end_byte != expected_end or not 0 <= start_byte < end_byte <= len(source)
            or source[start_byte:end_byte] != snippet):
        raise PatchError("invalid_provider_request")
    verified = verified_identity(identity, snapshot_id=snapshot_id, commit_sha=commit_sha,
        repository_id=repository_id, tenant_id=tenant_id, file_id=file_id, path=path, digest=digest, source=source)
    if not verified:
        classification = UNKNOWN_COVERAGE
    elif start_byte == 0 and end_byte == len(source):
        classification = COMPLETE_FILE
    else:
        classification = BOUNDED_EXCERPT
    return {
        "version": COVERAGE_VERSION,
        "classification": classification,
        "verification_status": "PINNED_FILE_IDENTITY_VERIFIED" if verified else "FULL_FILE_IDENTITY_UNAVAILABLE",
        "provided_byte_count": len(snippet),
        "provided_start_line": start_line,
        "provided_end_line": end_line,
        "provided_start_byte": start_byte if verified else None,
        "provided_end_byte_exclusive": end_byte if verified else None,
        "full_file_byte_count": len(source) if verified else None,
        "full_file_line_count": len(lines) if verified else None,
        "full_file_sha256": digest if verified else None,
        "notice": _NOTICES[classification],
    }
