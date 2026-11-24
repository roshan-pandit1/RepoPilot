"""Conservative, non-executing validation and application of unified diffs.

This module accepts only regular text files reconstructed and verified by the
caller. It never opens a repository path or invokes a shell or patch command.
"""
from dataclasses import dataclass
from hashlib import sha256
import re


class PatchError(ValueError):
    """A stable, safe-to-report failure code, without source or model output."""


@dataclass(frozen=True)
class Limits:
    files: int = 5
    changed_lines: int = 300
    patch_bytes: int = 256 * 1024
    hunks: int = 100
    file_bytes: int = 1024 * 1024

    def __post_init__(self):
        if not (1 <= self.files <= 5 and 1 <= self.changed_lines <= 300
                and 1 <= self.patch_bytes <= 256 * 1024 and 1 <= self.hunks <= 100
                and 1 <= self.file_bytes <= 1024 * 1024):
            raise ValueError("invalid_patch_limits")


@dataclass(frozen=True)
class PinnedFileIdentity:
    """Internal inventory record; callers must obtain it from a trusted pinned source.

    This object is not accepted from API clients or model output. The present indexed-file
    schema does not retain an independent byte length, so existing DB contexts do not
    construct this record.
    """
    snapshot_id: str
    commit_sha: str
    repository_id: int
    tenant_id: int
    file_id: str
    path: str
    sha256: str
    byte_length: int
    file_record_complete: bool


@dataclass(frozen=True)
class SourceFile:
    path: str
    content: bytes
    sha256: str
    file_id: str
    evidence_ids: tuple[str, ...]
    pinned_identity: PinnedFileIdentity | None = None


@dataclass(frozen=True)
class ChangedFile:
    path: str
    file_id: str
    before_sha256: str
    after_sha256: str
    content: bytes
    evidence_ids: tuple[str, ...]


_PATH = re.compile(r"[A-Za-z0-9_./-]{1,512}\Z")
_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: [^\n]*)?\n\Z")
_SENSITIVE = re.compile(r"(?:^|[._-])(secrets?|credentials?|passwords?|tokens?|private[_-]?keys?)(?:$|[._-])", re.I)


def safe_path(path: str) -> bool:
    """Accept a deliberately narrow portable relative source path."""
    if not isinstance(path, str) or not _PATH.fullmatch(path):
        return False
    parts = path.split("/")
    if any(not p or p in {".", ".."} or p.startswith(".") for p in parts):
        return False
    leaf = parts[-1].lower()
    return not (any(_SENSITIVE.search(part) for part in parts) or leaf in {"id_rsa", "id_dsa", "id_ed25519"}
                or leaf.endswith((".pem", ".key", ".p12", ".pfx", ".keystore")))


def validate_patch(diff: str, files: tuple[SourceFile, ...], limits: Limits = Limits()) -> tuple[ChangedFile, ...]:
    """Check identities, parse and apply supported hunks in memory, or fail closed.

    No new files, deletions, renames, symlinks, binary diffs or no-newline
    markers are accepted. Each file must already be evidence-backed. Requiring
    LF-terminated text avoids ambiguous newline transformations.
    """
    if not isinstance(diff, str):
        raise PatchError("invalid_patch")
    try:
        raw = diff.encode("utf-8")
    except UnicodeEncodeError:
        raise PatchError("invalid_patch") from None
    if not raw or len(raw) > limits.patch_bytes or b"\r" in raw or not raw.endswith(b"\n"):
        raise PatchError("invalid_patch_size_or_encoding")
    allowed = {}
    for item in files:
        if (not safe_path(item.path) or item.path in allowed or not item.evidence_ids
                or len(item.content) > limits.file_bytes or b"\x00" in item.content
                or sha256(item.content).hexdigest() != item.sha256):
            raise PatchError("invalid_source_identity")
        try:
            source = item.content.decode("utf-8")
        except UnicodeDecodeError:
            raise PatchError("invalid_source_encoding") from None
        if "\r" in source or (source and not source.endswith("\n")):
            raise PatchError("unsupported_source_newline")
        allowed[item.path] = (item, [line + "\n" for line in source.split("\n")[:-1]])
    lines = [line + "\n" for line in diff.split("\n")[:-1]]
    i = 0
    changed = []
    seen = set()
    change_count = hunk_count = 0
    while i < len(lines):
        if not lines[i].startswith("--- a/") or i + 1 >= len(lines) or not lines[i + 1].startswith("+++ b/"):
            raise PatchError("invalid_diff_header")
        path = lines[i][6:-1]
        new_path = lines[i + 1][6:-1]
        if not safe_path(path) or path != new_path or path not in allowed or path in seen:
            raise PatchError("unauthorized_or_duplicate_path")
        seen.add(path)
        if len(seen) > limits.files:
            raise PatchError("too_many_files")
        item, original = allowed[path]
        result: list[str] = []
        position = 0
        file_changed = False
        file_hunks = 0
        i += 2
        while i < len(lines) and lines[i].startswith("@@ "):
            match = _HUNK.fullmatch(lines[i])
            if not match:
                raise PatchError("invalid_hunk")
            old_start, old_count, new_start, new_count = (int(match.group(1)), int(match.group(2) or 1),
                                                          int(match.group(3)), int(match.group(4) or 1))
            old_target = old_start - 1 if old_count else old_start
            new_target = new_start - 1 if new_count else new_start
            if (old_target < position or old_target > len(original) or old_target < 0 or new_target < 0):
                raise PatchError("invalid_hunk_range")
            result.extend(original[position:old_target])
            position = old_target
            if len(result) != new_target:
                raise PatchError("invalid_hunk_range")
            i += 1
            old_used = new_used = 0
            while old_used < old_count or new_used < new_count:
                if i >= len(lines) or lines[i][0:1] not in {" ", "+", "-"}:
                    raise PatchError("invalid_hunk_body")
                kind, value = lines[i][0], lines[i][1:]
                if kind in {" ", "-"}:
                    if position >= len(original) or original[position] != value:
                        raise PatchError("source_mismatch")
                    position += 1
                    old_used += 1
                if kind in {" ", "+"}:
                    result.append(value)
                    new_used += 1
                if kind in {"+", "-"}:
                    change_count += 1
                    file_changed = True
                if old_used > old_count or new_used > new_count or change_count > limits.changed_lines:
                    raise PatchError("hunk_or_change_limit")
                i += 1
            hunk_count += 1
            file_hunks += 1
            if hunk_count > limits.hunks:
                raise PatchError("too_many_hunks")
        if not file_hunks or not file_changed:
            raise PatchError("empty_change")
        result.extend(original[position:])
        content = "".join(result).encode("utf-8")
        if len(content) > limits.file_bytes or content == item.content or b"\x00" in content:
            raise PatchError("invalid_result")
        changed.append(ChangedFile(path, item.file_id, item.sha256, sha256(content).hexdigest(),
                                   content, item.evidence_ids))
    if not changed:
        raise PatchError("empty_change")
    return tuple(changed)
