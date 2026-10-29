"""Bounded, fail-closed snapshot planning over an injectable GitHub source client."""
from dataclasses import dataclass
from typing import Protocol

from app.modules.ingestion.code_selection import eligible_python_path


class SnapshotError(Exception):
    """A snapshot cannot safely be represented as complete."""


class SourceClient(Protocol):
    def repository(self, token: str, full_name: str) -> dict: ...
    def commit(self, token: str, full_name: str, branch: str) -> dict: ...
    def tree(self, token: str, full_name: str, sha: str) -> dict: ...


@dataclass(frozen=True)
class Candidate:
    path: str
    blob_sha: str
    size: int


@dataclass(frozen=True)
class SnapshotPlan:
    commit_sha: str
    files: tuple[Candidate, ...]
    skipped_files: int = 0


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value)


def plan_snapshot(client: SourceClient, token: str, full_name: str, *,
                  max_entries: int = 10000, max_files: int = 1000,
                  max_file_bytes: int = 100_000) -> SnapshotPlan:
    """Resolve a public default-branch commit and reject incomplete or oversized trees.

    The client tree method must request a recursive tree. This function does not perform
    authorization itself: its caller must revalidate tenant, session, installation and
    public repository access before discovery and before publishing a snapshot.
    """
    if min(max_entries, max_files, max_file_bytes) <= 0:
        raise ValueError("snapshot limits must be positive")
    metadata = client.repository(token, full_name)
    if metadata.get("private") is not False or metadata.get("full_name") != full_name:
        raise SnapshotError("repository_not_public_or_moved")
    branch = metadata.get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise SnapshotError("default_branch_unavailable")
    commit = client.commit(token, full_name, branch)
    sha = commit.get("sha")
    if not _sha(sha):
        raise SnapshotError("invalid_commit")
    tree = client.tree(token, full_name, sha)
    entries = tree.get("tree")
    if tree.get("truncated") is not False or not isinstance(entries, list):
        raise SnapshotError("incomplete_tree")
    if len(entries) > max_entries:
        raise SnapshotError("tree_limit_exceeded")
    candidates = []
    seen = set()
    skipped = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise SnapshotError("invalid_tree_entry")
        if entry.get("type") != "blob" or entry.get("mode") not in {"100644", "100755"}:
            continue
        path, size, blob_sha = entry.get("path"), entry.get("size"), entry.get("sha")
        if not isinstance(path, str) or not eligible_python_path(path):
            continue
        if path in seen or not _sha(blob_sha) or not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise SnapshotError("invalid_tree_entry")
        seen.add(path)
        if size <= max_file_bytes:
            candidates.append(Candidate(path, blob_sha, size))
            if len(candidates) > max_files:
                raise SnapshotError("file_limit_exceeded")
        else:
            skipped += 1
    return SnapshotPlan(sha, tuple(sorted(candidates, key=lambda item: item.path)), skipped)
