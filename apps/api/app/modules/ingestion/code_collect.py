"""Build bounded in-memory candidate data; nothing is persisted by this module."""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from typing import Protocol
from uuid import uuid4

from app.modules.ingestion.code_chunking import SourceChunk, chunk_multilingual, chunk_python
from app.modules.ingestion.code_selection import (contains_sensitive_source, decode_source,
    eligible_source_path, incompatible_line_endings)
from app.modules.ingestion.code_snapshot import SnapshotPlan
from app.modules.ingestion.language_analysis import LANGUAGES, SyntaxAnalysis, analyze_source


class BlobClient(Protocol):
    def blob(self, token: str, full_name: str, sha: str, expected_size: int) -> bytes: ...


class CollectionError(Exception):
    """Safe collection failure without raw source content."""


@dataclass(frozen=True)
class CollectedFile:
    path: str
    content_hash: str
    chunks: tuple[SourceChunk, ...]
    language: str | None = None
    parser_version: str | None = None
    parser_status: str | None = None
    import_ranges: tuple[tuple[int, int], ...] | None = None
    source_byte_length: int | None = None
    source_encoding: str | None = None
    source_normalization: str | None = None
    source_coverage: str = "UNKNOWN_COVERAGE"


@dataclass(frozen=True)
class Collection:
    files: tuple[CollectedFile, ...]
    skipped_files: int
    fetched_bytes: int


def collect_source(client: BlobClient, token: str, full_name: str, plan: SnapshotPlan, *,
                   max_file_bytes: int = 100_000, max_total_bytes: int = 5_000_000,
                   max_chunks: int = 10_000, supervised: bool = False, text_only: bool = False) -> Collection:
    """Reject a whole file when a recognizable credential is found, without logging it.

    Callers must recheck repository authorization before fetching and publishing. Pattern
    checks do not catch all secrets. The byte budget covers rejected files as well.
    """
    if min(max_file_bytes, max_total_bytes, max_chunks) <= 0:
        raise ValueError("collection limits must be positive")
    if type(text_only) is not bool or (text_only and supervised):
        raise ValueError("invalid_text_only_mode")
    if supervised and plan.multilingual:
        from app.modules.ingestion import supervised_parser

        if not supervised_parser.isolation_available():
            raise CollectionError("supervised_parser_isolation_unavailable")
        if not isinstance(plan.commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", plan.commit_sha):
            raise CollectionError("supervised_parser_snapshot_invalid")
    files = []
    skipped = plan.skipped_files
    fetched = 0
    chunks = 0
    for candidate in plan.files:
        if not eligible_source_path(candidate.path, multilingual=plan.multilingual,
                                    exclude_generated=plan.multilingual):
            raise CollectionError("invalid_source_path")
        if candidate.size > max_file_bytes or fetched + candidate.size > max_total_bytes:
            raise CollectionError("source_byte_limit_exceeded")
        raw = client.blob(token, full_name, candidate.blob_sha, candidate.size)
        if len(raw) != candidate.size:
            raise CollectionError("source_size_mismatch")
        fetched += len(raw)
        source = decode_source(raw, max_file_bytes)
        if (source is None or contains_sensitive_source(source)
                or (plan.multilingual and incompatible_line_endings(source))):
            skipped += 1
            continue
        content_hash = sha256(raw).hexdigest()
        if text_only:
            spec = LANGUAGES.get(PurePosixPath(candidate.path).suffix.lower())
            if spec is None:
                raise CollectionError("invalid_source_path")
            analysis = SyntaxAnalysis(spec.name, "text-only-v1", (), (), "explicit_text_only")
            parsed = tuple(chunk_multilingual(source, analysis))
            file_language = analysis.language
            parser_version = analysis.parser_version
            parser_status = analysis.fallback_reason
            imports = analysis.import_lines
        elif supervised and plan.multilingual:
            if not isinstance(candidate.blob_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", candidate.blob_sha):
                raise CollectionError("supervised_parser_snapshot_invalid")
            language = LANGUAGES[PurePosixPath(candidate.path).suffix.lower()].name
            # The opaque request token binds the response to this collection's
            # pinned commit, blob, repository and source without exposing them
            # to the child. The nonce prevents reuse across deliveries.
            binding = [full_name, plan.commit_sha, candidate.blob_sha, candidate.path,
                       content_hash, uuid4().hex]
            request_id = sha256(json.dumps(binding, ensure_ascii=True,
                                           separators=(",", ":")).encode()).hexdigest()[:32]
            outcome = supervised_parser.run(raw, path=candidate.path, language=language,
                                            request_id=request_id, expected_sha256=content_hash)
            if not isinstance(outcome, supervised_parser.Outcome) or not isinstance(
                    outcome.status, supervised_parser.Status):
                raise CollectionError("supervised_parser_output_rejected")
            if outcome.status not in {supervised_parser.Status.PARSED, supervised_parser.Status.FALLBACK,
                                      supervised_parser.Status.UNAVAILABLE}:
                if (outcome.status == supervised_parser.Status.WORKER_EXITED
                        and type(outcome.exit_code) is int and -128 <= outcome.exit_code < 0):
                    raise CollectionError(f"supervised_parser_worker_signal_{-outcome.exit_code}")
                raise CollectionError("supervised_parser_" + outcome.status.value)
            if outcome.response is None:
                raise CollectionError("supervised_parser_output_rejected")
            response = outcome.response
            # Recheck the complete response against this exact collection request
            # before constructing any publishable chunks.
            try:
                request = supervised_parser._request(raw, candidate.path, language, request_id, 120, content_hash)
                encoded = (json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
                if len(encoded) > supervised_parser.MAX_RESPONSE or type(response.get("worker_pid")) is not int:
                    raise ValueError("invalid_response")
                checked = supervised_parser._validate(encoded, request, raw, response["worker_pid"])
                if checked.status != outcome.status or checked.response is None:
                    raise ValueError("invalid_response")
            except (KeyError, AttributeError, TypeError, ValueError, UnicodeError):
                raise CollectionError("supervised_parser_output_rejected") from None
            parsed = tuple(SourceChunk(chunk["start_line"], chunk["end_line"], chunk["symbol"],
                                       raw[chunk["start_byte"]:chunk["end_byte"]].decode("utf-8"),
                                       chunk["symbol_kind"]) for chunk in response["chunks"])
            file_language = response["language"]
            parser_version = response["parser_version"]
            parser_status = response["fallback_reason"] or "parsed"
            imports = tuple(tuple(item) for item in response["imports"])
        else:
            analysis = analyze_source(candidate.path, source, max_bytes=max_file_bytes)
            if analysis.language == "python":
                parsed = tuple(chunk_python(source))
            else:
                parsed = tuple(chunk_multilingual(source, analysis))
            file_language = analysis.language
            parser_version = analysis.parser_version
            parser_status = analysis.fallback_reason or "parsed"
            imports = analysis.import_lines
        chunks += len(parsed)
        if chunks > max_chunks:
            raise CollectionError("source_chunk_limit_exceeded")
        files.append(CollectedFile(candidate.path, content_hash, parsed, file_language,
                                   parser_version, parser_status, imports, len(raw), "utf-8", "identity",
                                   "COMPLETE_FILE"))
    return Collection(tuple(files), skipped, fetched)
