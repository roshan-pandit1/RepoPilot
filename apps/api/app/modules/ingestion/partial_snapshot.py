"""Identity-bound manifests for explicitly incomplete source inventories.

A manifest is not a publication or authorization. Callers must separately verify
that each planned blob came from the pinned repository commit and bind the manifest
to the authorized investigation. No source text is included in the manifest.
"""
from hashlib import sha1, sha256
import json
import re

from app.modules.ingestion.code_collect import Collection
from app.modules.ingestion.code_selection import contains_sensitive_source, eligible_source_path, incompatible_line_endings
from app.modules.ingestion.code_snapshot import Candidate, SnapshotPlan

MANIFEST_VERSION = "partial-source-manifest-v1"
PARTIAL_INVENTORY = "PARTIAL_INVENTORY"
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class PartialSnapshotError(ValueError):
    """Sanitized reason why a partial inventory cannot be trusted."""


def plan_pinned_partial(client, token: str, *, repository_id: int, repository_full_name: str,
                        commit_sha: str, paths: tuple[str, ...], expected_branch: str = "main") -> SnapshotPlan:
    """Resolve only explicit regular files beneath a verified pinned commit tree.

    The caller must authenticate the tenant and target repository before and after the
    remote calls. We verify public metadata, stable repository ID and branch ancestry;
    the resulting scope is deliberately partial and is not a published snapshot.
    """
    if (type(repository_id) is not int or repository_id <= 0 or not isinstance(repository_full_name, str)
            or not _REPO.fullmatch(repository_full_name) or not isinstance(commit_sha, str)
            or not _SHA1.fullmatch(commit_sha) or not isinstance(expected_branch, str)
            or not expected_branch or len(expected_branch) > 255 or not isinstance(paths, tuple)
            or not 1 <= len(paths) <= 5 or not all(isinstance(path, str) for path in paths)
            or len(set(paths)) != len(paths)
            or any(not eligible_source_path(path, multilingual=True,
                   exclude_generated=True) for path in paths)):
        raise PartialSnapshotError("partial_inventory_invalid")
    metadata = client.repository(token, repository_full_name)
    if (not isinstance(metadata, dict) or metadata.get("private") is not False
            or metadata.get("full_name") != repository_full_name or type(metadata.get("id")) is not int
            or metadata["id"] != repository_id or metadata.get("default_branch") != expected_branch):
        raise PartialSnapshotError("partial_repository_identity_mismatch")
    head = client.commit(token, repository_full_name, expected_branch)
    pinned = client.commit(token, repository_full_name, commit_sha)
    head_sha = head.get("sha") if isinstance(head, dict) else None
    if (not isinstance(head_sha, str) or not _SHA1.fullmatch(head_sha)
            or not isinstance(pinned, dict) or pinned.get("sha") != commit_sha
            or client.is_ancestor(token, repository_full_name, commit_sha, head_sha) is not True):
        raise PartialSnapshotError("partial_commit_not_in_branch")
    files = []
    for path in sorted(paths):
        entry = client.tree_file(token, repository_full_name, commit_sha, path)
        if (not isinstance(entry, dict) or entry.get("path") != path
                or not isinstance(entry.get("sha"), str) or not _SHA1.fullmatch(entry["sha"])
                or type(entry.get("size")) is not int or not 0 < entry["size"] <= 100_000):
            raise PartialSnapshotError("partial_file_unavailable")
        files.append(Candidate(path, entry["sha"], entry["size"]))
    return SnapshotPlan(commit_sha, tuple(files), multilingual=True)


def build_partial_manifest(*, repository_id: int, tenant_id: int, repository_full_name: str,
                           plan: SnapshotPlan, collection: Collection) -> tuple[dict, str]:
    """Reconstruct every complete allowed file, then bind its bytes and Git identity.

    ``plan`` is an exact, independently commit-resolved allowlist, not a complete
    repository enumeration. A rejected/missing item invalidates this entire scope.
    """
    if (type(repository_id) is not int or repository_id <= 0 or type(tenant_id) is not int or tenant_id <= 0
            or not isinstance(repository_full_name, str) or not _REPO.fullmatch(repository_full_name)
            or not isinstance(plan, SnapshotPlan) or not _SHA1.fullmatch(str(plan.commit_sha))
            or not plan.multilingual or plan.skipped_files != 0 or plan.unsupported_files != 0
            or not isinstance(collection, Collection) or collection.skipped_files != 0
            or not 1 <= len(plan.files) <= 5 or len(plan.files) != len(collection.files)):
        raise PartialSnapshotError("partial_inventory_invalid")
    candidates = {}
    for candidate in plan.files:
        if (not isinstance(candidate.path, str) or candidate.path in candidates
                or not eligible_source_path(candidate.path, multilingual=True, exclude_generated=True)
                or not isinstance(candidate.blob_sha, str) or not _SHA1.fullmatch(candidate.blob_sha)
                or type(candidate.size) is not int or not 0 < candidate.size <= 100_000):
            raise PartialSnapshotError("partial_inventory_invalid")
        candidates[candidate.path] = candidate
    seen, files, total = set(), [], 0
    for item in collection.files:
        candidate = candidates.get(item.path)
        if (candidate is None or item.path in seen or item.source_coverage != "COMPLETE_FILE"
                or type(item.source_byte_length) is not int or item.source_byte_length != candidate.size
                or item.source_encoding != "utf-8" or item.source_normalization != "identity"
                or not isinstance(item.content_hash, str) or not _SHA256.fullmatch(item.content_hash)
                or not item.chunks):
            raise PartialSnapshotError("partial_source_identity_invalid")
        seen.add(item.path)
        next_line, parts = 1, []
        for chunk in item.chunks:
            if (type(chunk.start_line) is not int or type(chunk.end_line) is not int
                    or chunk.start_line != next_line or chunk.end_line < chunk.start_line
                    or not isinstance(chunk.text, str) or chunk.text.count("\n") != chunk.end_line - chunk.start_line + 1):
                raise PartialSnapshotError("partial_source_identity_invalid")
            parts.append(chunk.text)
            next_line = chunk.end_line + 1
        try:
            source = "".join(parts)
            raw = source.encode("utf-8", errors="strict")
        except UnicodeError:
            raise PartialSnapshotError("partial_source_identity_invalid") from None
        git_blob = sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if (not raw.endswith(b"\n") or b"\0" in raw or b"\r" in raw
                or incompatible_line_endings(source) or contains_sensitive_source(source)
                or len(raw) != candidate.size or sha256(raw).hexdigest() != item.content_hash
                or git_blob != candidate.blob_sha):
            raise PartialSnapshotError("partial_source_identity_invalid")
        total += len(raw)
        files.append({"path": item.path, "git_blob_sha1": candidate.blob_sha,
                      "byte_length": len(raw), "sha256": item.content_hash,
                      "encoding": "utf-8", "normalization": "identity", "coverage": "COMPLETE_FILE"})
    if seen != set(candidates) or total != collection.fetched_bytes or total > 256 * 1024:
        raise PartialSnapshotError("partial_inventory_invalid")
    manifest = {"version": MANIFEST_VERSION, "repository_id": repository_id, "tenant_id": tenant_id,
                "repository_full_name": repository_full_name, "commit_sha": plan.commit_sha,
                "inventory_coverage": PARTIAL_INVENTORY, "files": sorted(files, key=lambda item: item["path"])}
    encoded = json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    return manifest, sha256(encoded).hexdigest()


def verify_partial_manifest(*, expected_manifest: dict, expected_sha256: str, **kwargs) -> None:
    """Fail closed if the stored manifest differs from current reconstructed bytes."""
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        raise PartialSnapshotError("partial_manifest_mismatch")
    actual, digest = build_partial_manifest(**kwargs)
    if expected_manifest != actual or expected_sha256 != digest:
        raise PartialSnapshotError("partial_manifest_mismatch")
