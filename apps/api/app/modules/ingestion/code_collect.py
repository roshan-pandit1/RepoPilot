"""Build bounded in-memory candidate data; nothing is persisted by this module."""
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from app.modules.ingestion.code_chunking import SourceChunk, chunk_python
from app.modules.ingestion.code_selection import contains_sensitive_source, decode_source
from app.modules.ingestion.code_snapshot import SnapshotPlan


class BlobClient(Protocol):
    def blob(self, token: str, full_name: str, sha: str, expected_size: int) -> bytes: ...


class CollectionError(Exception):
    """Safe collection failure without raw source content."""


@dataclass(frozen=True)
class CollectedFile:
    path: str
    content_hash: str
    chunks: tuple[SourceChunk, ...]


@dataclass(frozen=True)
class Collection:
    files: tuple[CollectedFile, ...]
    skipped_files: int
    fetched_bytes: int


def collect_source(client: BlobClient, token: str, full_name: str, plan: SnapshotPlan, *,
                   max_file_bytes: int = 100_000, max_total_bytes: int = 5_000_000,
                   max_chunks: int = 10_000) -> Collection:
    """Reject a whole file when a recognizable credential is found, without logging it.

    Callers must recheck repository authorization before fetching and publishing. Pattern
    checks do not catch all secrets. The byte budget covers rejected files as well.
    """
    if min(max_file_bytes, max_total_bytes, max_chunks) <= 0:
        raise ValueError("collection limits must be positive")
    files = []
    skipped = plan.skipped_files
    fetched = 0
    chunks = 0
    for candidate in plan.files:
        if candidate.size > max_file_bytes or fetched + candidate.size > max_total_bytes:
            raise CollectionError("source_byte_limit_exceeded")
        raw = client.blob(token, full_name, candidate.blob_sha, candidate.size)
        if len(raw) != candidate.size:
            raise CollectionError("source_size_mismatch")
        fetched += len(raw)
        source = decode_source(raw, max_file_bytes)
        if source is None or contains_sensitive_source(source):
            skipped += 1
            continue
        parsed = tuple(chunk_python(source))
        chunks += len(parsed)
        if chunks > max_chunks:
            raise CollectionError("source_chunk_limit_exceeded")
        files.append(CollectedFile(candidate.path, sha256(raw).hexdigest(), parsed))
    return Collection(tuple(files), skipped, fetched)
