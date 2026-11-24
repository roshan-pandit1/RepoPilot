"""Validate paired benchmark inputs against local Git objects; never fetch or run source.

This is an opt-in preflight for supplied captures. It cannot authenticate their
producer, prove independent annotation, or prove an inventory is complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Annotated, Literal

from pydantic import Field, ValidationError

from app.evaluation.git_source import GitSource
from app.evaluation.issue_context_schema import StrictModel
from app.evaluation.retrieval import citation_valid
from app.evaluation.retrieval_heldout import MODES, _issue_context, evaluate, validate_dataset
from app.modules.ingestion.code_selection import (
    contains_sensitive_source,
    eligible_source_path,
    incompatible_line_endings,
)
from app.modules.ingestion.language_analysis import LANGUAGES
from app.modules.investigation.retrieval import fingerprint_chunk

SHA1 = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
UUID = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]


class InventoryChunk(StrictModel):
    chunk_id: UUID
    file_id: UUID
    path: str = Field(min_length=1, max_length=250)
    language: str = Field(min_length=1, max_length=40)
    symbol: str | None = Field(max_length=256)
    start_line: int = Field(gt=0)
    end_line: int = Field(gt=0)
    git_blob_sha1: SHA1
    file_sha256: SHA256
    chunk_sha256: SHA256
    chunk_fingerprint: SHA256


class GitInventory(StrictModel):
    version: Literal["git-source-inventory-v1"]
    repository: str = Field(min_length=3, max_length=250)
    commit: SHA1
    tenant_id: int = Field(gt=0, lt=2**63)
    repository_id: int = Field(gt=0, lt=2**63)
    snapshot_id: UUID
    chunks: list[InventoryChunk] = Field(min_length=1, max_length=10000)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_object_id(kind: str, data: bytes) -> str:
    header = f"{kind} {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # Git SHA-1 object identity, not a trust signature.


def _digest(value) -> str:
    return _sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                              separators=(",", ":")).encode("ascii"))


def verify_git_inventory(data: dict, roots: dict[str, Path]) -> tuple[GitInventory, str, dict]:
    """Recompute blob, file, chunk and RepoPilot fingerprint identities from pinned Git."""
    try:
        inventory = GitInventory.model_validate(data)
    except (ValidationError, ValueError, TypeError):
        raise ValueError("invalid_inventory") from None
    if inventory.repository not in roots:
        raise ValueError("missing_repository_binding")
    try:
        source = GitSource(roots[inventory.repository], inventory.commit, inventory.repository)
        commit_data = source._git("cat-file", "commit", inventory.commit)
    except (OSError, subprocess.SubprocessError):
        raise ValueError("unverifiable_git_commit") from None
    if len(commit_data) > 1_000_000 or _git_object_id("commit", commit_data) != inventory.commit:
        raise ValueError("commit_object_mismatch")
    entries = {entry["path"]: entry for entry in source.entries}
    chunks, file_paths, path_ids, sources, ranges = {}, {}, {}, {}, {}
    for chunk in inventory.chunks:
        language = LANGUAGES.get(PurePosixPath(chunk.path).suffix.lower())
        if (chunk.chunk_id in chunks or not eligible_source_path(chunk.path, exclude_generated=True)
                or not language or chunk.language != language.name
                or chunk.end_line < chunk.start_line):
            raise ValueError("invalid_chunk_identity")
        if ((chunk.file_id in file_paths and file_paths[chunk.file_id] != chunk.path)
                or (chunk.path in path_ids and path_ids[chunk.path] != chunk.file_id)):
            raise ValueError("inconsistent_file_identity")
        file_paths[chunk.file_id], path_ids[chunk.path] = chunk.path, chunk.file_id
        entry = entries.get(chunk.path)
        if not entry or entry["sha"] != chunk.git_blob_sha1:
            raise ValueError("git_blob_mismatch")
        if chunk.path not in sources:
            try:
                raw = source.blob("", inventory.repository, entry["sha"], entry["size"])
            except (OSError, subprocess.SubprocessError):
                raise ValueError("unverifiable_git_blob") from None
            try:
                content = raw.decode("utf-8")
            except UnicodeError:
                raise ValueError("invalid_source") from None
            if (b"\0" in raw or incompatible_line_endings(content) or contains_sensitive_source(content)
                    or _git_object_id("blob", raw) != entry["sha"]):
                raise ValueError("invalid_source")
            sources[chunk.path] = (raw, content.splitlines(keepends=True))
        raw, lines = sources[chunk.path]
        if chunk.end_line > len(lines) or _sha256(raw) != chunk.file_sha256:
            raise ValueError("file_identity_or_range_mismatch")
        text = "".join(lines[chunk.start_line - 1:chunk.end_line])
        expected_fingerprint = fingerprint_chunk(
            SimpleNamespace(id=chunk.chunk_id, file_id=chunk.file_id, symbol=chunk.symbol,
                            start_line=chunk.start_line, end_line=chunk.end_line, source_text=text),
            SimpleNamespace(snapshot_id=inventory.snapshot_id, path=chunk.path, content_hash=chunk.file_sha256))
        if _sha256(text.encode("utf-8")) != chunk.chunk_sha256 or expected_fingerprint != chunk.chunk_fingerprint:
            raise ValueError("chunk_fingerprint_mismatch")
        chunks[chunk.chunk_id] = chunk
        ranges.setdefault(chunk.path, []).append((chunk.start_line, chunk.end_line))
    for intervals in ranges.values():
        ordered = sorted(intervals)
        if any(right[0] <= left[1] for left, right in zip(ordered, ordered[1:])):
            raise ValueError("overlapping_inventory_chunks")
    digest = _digest([[key, chunks[key].chunk_fingerprint] for key in sorted(chunks)])
    return inventory, digest, chunks


def _validate_annotation(query: dict) -> None:
    annotation = query.get("annotation_record")
    keys = {"annotators", "adjudicator", "uncertainty", "single_annotator_reason", "exclusion_reason"}
    if not isinstance(annotation, dict) or set(annotation) != keys:
        raise ValueError("invalid_annotation_record")
    annotators = annotation["annotators"]
    def valid_id(value):
        return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value))
    if (not isinstance(annotators, list) or not 1 <= len(annotators) <= 10
            or any(not valid_id(item) for item in annotators) or len(set(annotators)) != len(annotators)
            or not valid_id(annotation["adjudicator"])
            or not isinstance(annotation["uncertainty"], str) or not annotation["uncertainty"].strip()
            or len(annotation["uncertainty"]) > 1000
            or annotation["exclusion_reason"] is not None):
        raise ValueError("invalid_annotation_record")
    reason = annotation["single_annotator_reason"]
    if len(annotators) == 1:
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("single_annotator_reason_required")
    elif reason is not None:
        raise ValueError("unexpected_single_annotator_reason")


def _validate_split(dataset: dict, split: str) -> list[tuple]:
    if (not isinstance(dataset, dict) or dataset.get("version") != "heldout-v2"
            or dataset.get("split") != split or not isinstance(dataset.get("queries"), list)
            or not dataset["queries"] or len(dataset["queries"]) > 10000):
        raise ValueError("invalid_dataset_split")
    config = dataset.get("retrieval_config")
    if (not isinstance(config, dict) or not isinstance(config.get("semantic_query_policy"), str)
            or config["semantic_query_policy"] not in {"issue-title-v1", "issue-title-body-v1"}
            or type(config.get("query_body_limit")) is not int or not 1 <= config["query_body_limit"] <= 4000):
        raise ValueError("invalid_semantic_query_policy")
    identities = []
    for query in dataset["queries"]:
        if not isinstance(query, dict):
            raise ValueError("invalid_query")
        issue = _issue_context(query)
        if issue.comments != sorted(issue.comments, key=lambda c: (c.created_at, c.id)):
            raise ValueError("comment_order_mismatch")
        _validate_annotation(query)
        labels = query.get("relevance")
        if not isinstance(labels, list):
            raise ValueError("invalid_labels")
        intervals = {}
        for label in labels:
            if (not isinstance(label, dict) or not isinstance(label.get("path"), str)
                    or any(isinstance(label.get(k), bool) or not isinstance(label.get(k), int)
                           for k in ("start_line", "end_line", "grade"))):
                raise ValueError("invalid_label")
            intervals.setdefault(label["path"], []).append((label["start_line"], label["end_line"]))
        for ranges in intervals.values():
            ordered = sorted(ranges)
            if any(right[0] <= left[1] for left, right in zip(ordered, ordered[1:])):
                raise ValueError("conflicting_or_overlapping_labels")
        def normalized(text):
            return " ".join((text or "").split()).casefold()
        if any(not isinstance(query.get(k), str) or not query[k] for k in ("id", "repository", "query")):
            raise ValueError("invalid_query")
        expected_query = issue.title
        body = (issue.body or "")[:config["query_body_limit"]]
        if config["semantic_query_policy"] == "issue-title-body-v1" and body:
            expected_query += "\n\n" + body
        if query["query"] != expected_query:
            raise ValueError("semantic_query_policy_mismatch")
        identities.append((query["id"], issue.issue_id, (query["repository"], issue.number),
                           _digest([normalized(issue.title), normalized(issue.body)]),
                           normalized(query["query"])))
    return identities


def _split_separation(development: dict, heldout: dict) -> None:
    identities = _validate_split(development, "development") + _validate_split(heldout, "held_out")
    for index in range(5):
        values = [item[index] for item in identities]
        if len(set(values)) != len(values):
            raise ValueError("duplicate_issue_or_split_leakage")


def _semantic_identity(identity: object) -> tuple:
    keys = ("provider", "model", "revision", "tokenizer_revision", "representation_contract",
            "normalization", "dimensions", "pooling", "query_prefix", "document_prefix")
    if (not isinstance(identity, dict) or set(identity) != set(keys)
            or not isinstance(identity["provider"], str) or identity["provider"] not in {"fake", "local-onnx"}
            or any(not isinstance(identity[key], str) or not 1 <= len(identity[key]) <= 250
                   for key in ("model", "revision", "tokenizer_revision", "representation_contract",
                               "normalization", "pooling"))
            or any(not isinstance(identity[key], str) or len(identity[key]) > 500
                   for key in ("query_prefix", "document_prefix"))
            or isinstance(identity["dimensions"], bool) or not isinstance(identity["dimensions"], int)
            or not 1 <= identity["dimensions"] <= 4096
            or not re.fullmatch(r"[0-9a-f]{64}", identity["representation_contract"])):
        raise ValueError("invalid_semantic_identity")
    if identity["provider"] == "local-onnx" and any(
            not re.fullmatch(r"[0-9a-f]{40}", identity[key]) for key in ("revision", "tokenizer_revision")):
        raise ValueError("unpinned_model_revision")
    if identity["provider"] == "local-onnx" and (
            identity["model"], identity["dimensions"], identity["normalization"], identity["pooling"],
            identity["query_prefix"], identity["document_prefix"]) != (
                "nomic-ai/CodeRankEmbed", 768, "l2", "cls",
                "Represent this query for searching relevant code: ", ""):
        raise ValueError("coderankembed_contract_mismatch")
    return tuple(identity[key] for key in keys)


def validate_and_evaluate(development: dict, heldout: dict, inventories: list[dict],
                          captures: dict[tuple[str, str], tuple[dict, float]], *, roots: dict[str, Path]) -> dict:
    """Require Git-derived identities and non-overlapping splits before existing scoring."""
    _split_separation(development, heldout)
    if development.get("retrieval_config") != heldout.get("retrieval_config"):
        raise ValueError("split_configuration_mismatch")
    if development.get("semantic_identity") != heldout.get("semantic_identity"):
        raise ValueError("split_semantic_identity_mismatch")
    declared_identity = _semantic_identity(heldout.get("semantic_identity"))
    # Reuse the held-out validator without scoring the development set.
    try:
        validate_dataset({**development, "split": "held_out"}, roots)
        validate_dataset(heldout, roots)
    except (OSError, subprocess.SubprocessError):
        raise ValueError("unverifiable_git_reference") from None
    if not isinstance(inventories, list) or not 1 <= len(inventories) <= 100:
        raise ValueError("invalid_inventories")
    verified, seen_chunks, seen_snapshots = {}, set(), set()
    for data in inventories:
        inventory, digest, chunks = verify_git_inventory(data, roots)
        key = (inventory.repository, inventory.commit)
        if key in verified or inventory.snapshot_id in seen_snapshots or seen_chunks.intersection(chunks):
            raise ValueError("duplicate_inventory")
        verified[key] = (inventory, digest, chunks)
        seen_chunks.update(chunks)
        seen_snapshots.add(inventory.snapshot_id)
    for dataset in (development, heldout):
        for query in dataset["queries"]:
            entry = verified.get((query["repository"], query["commit"]))
            if entry is None:
                raise ValueError("missing_inventory")
            for label in query["relevance"]:
                if not any(chunk.path == label["path"] and chunk.start_line <= label["start_line"]
                           and label["end_line"] <= chunk.end_line for chunk in entry[2].values()):
                    raise ValueError("label_outside_inventory")
    expected = {(mode, query["id"]) for mode in MODES for query in heldout["queries"]}
    if set(captures) != expected:
        raise ValueError("capture_set_mismatch")
    identities = set()
    for query in heldout["queries"]:
        inventory, digest, chunks = verified[(query["repository"], query["commit"])]
        for mode in MODES:
            response, _ = captures[(mode, query["id"])]
            if (not isinstance(response, dict)
                    or type(response.get("tenant_id")) is not int or type(response.get("repository_id")) is not int
                    or (response.get("repository"), response.get("tenant_id"), response.get("repository_id"),
                        response.get("snapshot_id"), response.get("commit_sha"), response.get("universe_digest"))
                    != (inventory.repository, inventory.tenant_id, inventory.repository_id,
                        inventory.snapshot_id, inventory.commit, digest)):
                raise ValueError("capture_inventory_mismatch")
            if mode in {"semantic", "hybrid"}:
                identities.add(_semantic_identity(response.get("semantic_identity")))
            items = response.get("items")
            if not isinstance(items, list) or len(items) > heldout["retrieval_config"]["top_k"]:
                raise ValueError("invalid_capture_items")
            seen = set()
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("invalid_capture_item")
                chunk = chunks.get(item.get("chunk_id"))
                if (not chunk or chunk.chunk_id in seen
                        or (item.get("path"), item.get("start_line"), item.get("end_line"),
                            item.get("chunk_fingerprint"))
                        != (chunk.path, chunk.start_line, chunk.end_line, chunk.chunk_fingerprint)
                        or ("symbol" in item and item["symbol"] != chunk.symbol)
                        or (item.get("snippet") is not None and (not isinstance(item["snippet"], str)
                            or _sha256(item["snippet"].encode("utf-8")) != chunk.chunk_sha256))
                        or not citation_valid(item, inventory.repository, inventory.commit)):
                    raise ValueError("capture_citation_or_chunk_mismatch")
                seen.add(chunk.chunk_id)
    if identities != {declared_identity}:
        raise ValueError("embedding_space_mismatch")
    result = evaluate(heldout, captures, roots=roots)
    result["provenance_validation"] = {"version": "git-source-inventory-v1", "inventories": len(verified),
        "development_queries": len(development["queries"]), "heldout_queries": len(heldout["queries"]),
        "semantic_identity": heldout["semantic_identity"],
        "status": "CONSISTENCY_CHECKED_CAPTURE_ORIGIN_UNAUTHENTICATED"}
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("development", "heldout", "inventories", "captures", "output"):
        parser.add_argument(f"--{option}", required=True, type=Path)
    parser.add_argument("--repository", action="append", required=True, metavar="OWNER/REPO=PATH")
    args = parser.parse_args(argv)
    roots = {}
    for binding in args.repository:
        name, separator, path = binding.partition("=")
        if not separator or not name or not path or name in roots or not Path(path).is_dir():
            raise ValueError("invalid_repository_binding")
        roots[name] = Path(path)
    parent = args.output.parent.resolve()
    if any(parent == root.resolve() or root.resolve() in parent.parents for root in roots.values()):
        raise ValueError("output_inside_source_repository")
    values = []
    for path in (args.development, args.heldout, args.inventories, args.captures):
        if path.stat().st_size > 8_000_000:
            raise ValueError("evaluation_input_too_large")
        values.append(json.loads(path.read_text(encoding="utf-8")))
    development, heldout, inventories, records = values
    if not isinstance(records, list):
        raise ValueError("invalid_captures")
    captures = {}
    for record in records:
        if (not isinstance(record, dict) or record.get("mode") not in MODES
                or not isinstance(record.get("query_id"), str) or not isinstance(record.get("response"), dict)):
            raise ValueError("invalid_capture")
        key = (record["mode"], record["query_id"])
        if key in captures:
            raise ValueError("duplicate_capture")
        captures[key] = (record["response"], record.get("latency_ms"))
    result = validate_and_evaluate(development, heldout, inventories, captures, roots=roots)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
