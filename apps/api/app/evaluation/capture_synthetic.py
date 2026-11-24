"""Capture fixture-only retrieval comparisons in a dedicated disposable PostgreSQL database.

The command accepts only the registered synthetic fixture and controlled vectors. It never
loads a model, contacts GitHub, or accepts an application database target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import sessionmaker

from app.domain.models import (Base, ChunkEmbedding, CodeChunk, CodeSnapshot, EmbeddingCache,
                               IndexedFile, Installation, Membership, Repository,
                               SnapshotPublication, Tenant, User)
from app.evaluation.issue_context_schema import (IssueContext, ShortText, StrictModel, context_digest,
                                                 normalized_context)
from app.evaluation.retrieval import citation_valid
from app.evaluation.retrieval_heldout import score_query
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.code_selection import (contains_sensitive_source, eligible_source_path,
                                                   incompatible_line_endings)
from app.modules.ingestion.embedding_store import cache_key, persist_embedding
from app.modules.ingestion.rank_fusion import reciprocal_rank_fusion
from app.modules.ingestion.semantic_search import search_vectors
from app.modules.investigation.query_builder import build_queries_for_version
from app.modules.investigation.retrieval import fingerprint_chunk, retrieve_candidates, validate_snapshot

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "evaluation/fixtures/synthetic-capture-v1.json"
FIXTURE_SHA256 = "bc3ce070215cac2353e4a63fae237036dc8318695f8eb105096633fe855de809"
CONTRACT = hashlib.sha256(b"synthetic-capture-controlled-v1").hexdigest()
DATABASE_MARKER = "repopilot-synthetic-capture-v1"
UUIDText = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]
SafeId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")]
class CaptureConfig(StrictModel):
    version: Literal["capture-config-v1"]
    query_version: Literal["terms-v2"]
    query_limit: Literal[3]
    query_body_limit: Literal[4000]
    per_query_limit: Literal[10]
    evidence_limit: Literal[20]
    semantic_candidate_pool: Literal[20]
    top_k: Literal[10]
    fusion_k: Literal[60]
    chunking_policy: Literal["fixture-explicit-inclusive-lines-v1"]
    semantic_representation: Literal["fixture-controlled-vector-v1"]
    semantic_query_policy: Literal["fixture-issue-title-v1"]
    missing_vectors: Literal["reject"]
    missing_results: Literal["empty"]


class Annotation(StrictModel):
    instructions: str = Field(min_length=1, max_length=1000)
    label_provenance: Literal["synthetic-fixture-authored"]
    adjudication_status: Literal["fixture-derived"]
    exclusion_criteria: list[ShortText] = Field(min_length=1, max_length=20)


class SourceFile(StrictModel):
    id: UUIDText
    path: str = Field(min_length=1, max_length=250)
    language: Literal["python", "typescript"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: str = Field(min_length=1, max_length=100000)

    @model_validator(mode="after")
    def source_identity(self):
        suffix = ".py" if self.language == "python" else ".ts"
        if (not eligible_source_path(self.path, exclude_generated=True) or not self.path.endswith(suffix)
                or len(self.source.encode("utf-8")) > 100000 or "\x00" in self.source
                or incompatible_line_endings(self.source)
                or contains_sensitive_source(self.source)
                or hashlib.sha256(self.source.encode("utf-8")).hexdigest() != self.sha256):
            raise ValueError("invalid_fixture_source")
        return self


def _unit_vector(vector: list[float]) -> None:
    if (len(vector) != 3 or any(not math.isfinite(value) for value in vector)
            or not math.isclose(math.hypot(*vector), 1.0, abs_tol=1e-6)):
        raise ValueError("invalid_controlled_vector")


class SourceChunk(StrictModel):
    id: UUIDText
    file_id: UUIDText
    symbol: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    start_line: int = Field(gt=0)
    end_line: int = Field(gt=0)
    vector: list[float] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def bounds_and_vector(self):
        if self.end_line < self.start_line:
            raise ValueError("invalid_chunk_range")
        _unit_vector(self.vector)
        return self


class Judgment(StrictModel):
    chunk_id: UUIDText
    path: str = Field(min_length=1, max_length=250)
    start_line: int = Field(gt=0)
    end_line: int = Field(gt=0)
    grade: int = Field(ge=0, le=3)


class Example(StrictModel):
    id: SafeId
    issue: IssueContext
    query_vector: list[float] = Field(min_length=3, max_length=3)
    adjudication: Literal["fixture-derived", "insufficient-evidence"]
    relevance: list[Judgment] = Field(max_length=100)

    @model_validator(mode="after")
    def judgments_and_vector(self):
        _unit_vector(self.query_vector)
        if self.adjudication == "insufficient-evidence":
            if self.relevance:
                raise ValueError("unexpected_insufficient_labels")
        elif not self.relevance or not any(item.grade > 0 for item in self.relevance):
            raise ValueError("incomplete_labels")
        if len({item.chunk_id for item in self.relevance}) != len(self.relevance):
            raise ValueError("duplicate_labels")
        return self


class SyntheticFixture(StrictModel):
    version: Literal["synthetic-capture-v1"]
    dataset_id: SafeId
    split: Literal["development", "held_out"]
    source_identity: Literal["synthetic-only-v1"]
    repository: Literal["synthetic-fixture/capture"]
    commit: Literal["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
    snapshot_id: UUIDText
    tenant_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    installation_id: int = Field(gt=0)
    repository_id: int = Field(gt=0)
    config: CaptureConfig
    annotation: Annotation
    files: list[SourceFile] = Field(min_length=1, max_length=100)
    chunks: list[SourceChunk] = Field(min_length=1, max_length=500)
    examples: list[Example] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def inventory_and_labels(self):
        files = {item.id: item for item in self.files}
        chunks = {item.id: item for item in self.chunks}
        if (len(files) != len(self.files) or len({item.path for item in self.files}) != len(files)
                or len(chunks) != len(self.chunks) or len({item.id for item in self.examples}) != len(self.examples)
                or len({item.issue.number for item in self.examples}) != len(self.examples)
                or len({item.issue.issue_id for item in self.examples}) != len(self.examples)):
            raise ValueError("duplicate_fixture_identity")
        for file in self.files:
            lines = file.source.splitlines(keepends=True)
            cursor = 1
            for chunk in sorted((item for item in self.chunks if item.file_id == file.id),
                                key=lambda item: (item.start_line, item.id)):
                if chunk.start_line != cursor or chunk.end_line > len(lines):
                    raise ValueError("incomplete_chunk_inventory")
                cursor = chunk.end_line + 1
            if cursor != len(lines) + 1:
                raise ValueError("incomplete_chunk_inventory")
        if any(item.file_id not in files for item in self.chunks):
            raise ValueError("unknown_chunk_file")
        for example in self.examples:
            for label in example.relevance:
                chunk = chunks.get(label.chunk_id)
                if (not chunk or files[chunk.file_id].path != label.path
                        or not chunk.start_line <= label.start_line <= label.end_line <= chunk.end_line):
                    raise ValueError("invalid_fixture_label")
        return self


class ControlledProvider:
    provider = "fake"
    model = "fixture-controlled"
    version = "fixture-v1"
    revision = "fixture-v1"
    dimensions = 3
    normalization = "l2"
    contract = CONTRACT


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                                     separators=(",", ":")).encode("ascii")).hexdigest()


def assert_split_separation(development: SyntheticFixture, held_out: SyntheticFixture) -> None:
    """Reject duplicated issue identities or contexts across evaluation splits."""
    if development.split != "development" or held_out.split != "held_out":
        raise ValueError("invalid_split_pair")
    left = {(development.repository, item.issue.number) for item in development.examples}
    right = {(held_out.repository, item.issue.number) for item in held_out.examples}
    def context_content(item):
        return _digest([" ".join(item.issue.title.split()).casefold(),
                        " ".join((item.issue.body or "").split()).casefold()])
    if ({item.id for item in development.examples} & {item.id for item in held_out.examples}
            or {item.issue.issue_id for item in development.examples} & {
                item.issue.issue_id for item in held_out.examples}
            or left & right or {context_content(item) for item in development.examples} & {
            context_content(item) for item in held_out.examples}):
        raise ValueError("split_leakage")


def load_registered_fixture(path: Path) -> SyntheticFixture:
    """Restrict the executable runner to one reviewed synthetic input artifact."""
    if path.is_symlink() or path.resolve() != FIXTURE_PATH.resolve():
        raise ValueError("unregistered_fixture")
    raw = path.read_bytes()
    if len(raw) > 500000 or hashlib.sha256(raw).hexdigest() != FIXTURE_SHA256:
        raise ValueError("fixture_identity_mismatch")
    fixture = SyntheticFixture.model_validate_json(raw)
    if fixture.split != "development":
        raise ValueError("synthetic_development_only")
    return fixture


def seed_synthetic_fixture(factory, fixture: SyntheticFixture) -> None:
    """Insert only fixture-defined synthetic rows into the caller's disposable test database."""
    if fixture.split != "development":
        raise ValueError("synthetic_development_only")
    with factory.begin() as db:
        if db.get(Tenant, fixture.tenant_id) or db.get(Repository, fixture.repository_id):
            raise ValueError("fixture_owner_exists")
        db.add_all([Tenant(id=fixture.tenant_id, name="synthetic fixture"),
                    User(id=fixture.user_id, github_user_id=fixture.user_id, login="synthetic-fixture")])
        db.flush()
        db.add_all([Membership(tenant_id=fixture.tenant_id, user_id=fixture.user_id),
                    Installation(id=fixture.installation_id, tenant_id=fixture.tenant_id, active=True)])
        db.flush()
        db.add(Repository(id=fixture.repository_id, tenant_id=fixture.tenant_id,
                          installation_id=fixture.installation_id, full_name=fixture.repository, enabled=True))
        db.flush()
        db.add(CodeSnapshot(id=fixture.snapshot_id, repository_id=fixture.repository_id,
                            tenant_id=fixture.tenant_id, commit_sha=fixture.commit, published=True,
                            file_count=len(fixture.files), chunk_count=len(fixture.chunks), skipped_count=0,
                            indexing_mode="multilingual", unsupported_count=0))
        db.flush()
        db.add(SnapshotPublication(snapshot_id=fixture.snapshot_id, repository_id=fixture.repository_id,
                                   tenant_id=fixture.tenant_id, commit_sha=fixture.commit,
                                   file_count=len(fixture.files), chunk_count=len(fixture.chunks), skipped_count=0))
        for file in fixture.files:
            db.add(IndexedFile(id=file.id, snapshot_id=fixture.snapshot_id, repository_id=fixture.repository_id,
                               tenant_id=fixture.tenant_id, path=file.path, content_hash=file.sha256,
                               language=file.language, parser_status="fixture", parser_version="fixture-v1",
                               import_ranges=[]))
        db.flush()
        files = {item.id: item for item in fixture.files}
        for item in fixture.chunks:
            lines = files[item.file_id].source.splitlines(keepends=True)
            db.add(CodeChunk(id=item.id, file_id=item.file_id, repository_id=fixture.repository_id,
                             tenant_id=fixture.tenant_id, symbol=item.symbol, symbol_kind="function",
                             start_line=item.start_line, end_line=item.end_line,
                             source_text="".join(lines[item.start_line - 1:item.end_line])))
        db.flush()
        for item in fixture.chunks:
            persist_embedding(db, db.get(CodeChunk, item.id), ControlledProvider(), item.vector)


def _verified_inventory(db, fixture: SyntheticFixture, tenant_id: int, user_id: int) -> dict:
    if (tenant_id, user_id) != (fixture.tenant_id, fixture.user_id):
        raise ValueError("fixture_access_denied")
    repo = db.get(Repository, fixture.repository_id)
    installation = db.get(Installation, fixture.installation_id)
    if (not db.get(Membership, (tenant_id, user_id)) or not repo or not repo.enabled
            or (repo.tenant_id, repo.installation_id, repo.full_name)
            != (tenant_id, fixture.installation_id, fixture.repository)
            or not installation or not installation.active or installation.tenant_id != tenant_id):
        raise ValueError("fixture_access_denied")
    snapshot = validate_snapshot(db, snapshot_id=fixture.snapshot_id, repository_id=fixture.repository_id,
                                 tenant_id=tenant_id, commit=fixture.commit)
    if (not db.get(SnapshotPublication, snapshot.id)
            or (snapshot.file_count, snapshot.chunk_count, snapshot.skipped_count)
            != (len(fixture.files), len(fixture.chunks), 0)):
        raise ValueError("fixture_snapshot_mismatch")
    files = {item.id: item for item in fixture.files}
    stored_files = db.scalars(select(IndexedFile).where(IndexedFile.snapshot_id == snapshot.id)).all()
    if {item.id for item in stored_files} != set(files):
        raise ValueError("fixture_file_inventory_mismatch")
    for item in stored_files:
        expected = files[item.id]
        if ((item.repository_id, item.tenant_id, item.path, item.language, item.content_hash)
                != (fixture.repository_id, tenant_id, expected.path, expected.language, expected.sha256)):
            raise ValueError("fixture_file_mismatch")
    expected_chunks = {item.id: item for item in fixture.chunks}
    rows = db.execute(select(CodeChunk, IndexedFile).join(IndexedFile, CodeChunk.file_id == IndexedFile.id)
                      .where(IndexedFile.snapshot_id == snapshot.id)).all()
    if len(rows) != len(expected_chunks) or {chunk.id for chunk, _ in rows} != set(expected_chunks):
        raise ValueError("fixture_chunk_inventory_mismatch")
    inventory = {}
    for chunk, file in rows:
        expected = expected_chunks[chunk.id]
        lines = files[expected.file_id].source.splitlines(keepends=True)
        if ((chunk.file_id, chunk.repository_id, chunk.tenant_id, chunk.symbol, chunk.start_line, chunk.end_line)
                != (expected.file_id, fixture.repository_id, tenant_id, expected.symbol,
                    expected.start_line, expected.end_line)
                or chunk.source_text != "".join(lines[expected.start_line - 1:expected.end_line])):
            raise ValueError("fixture_chunk_mismatch")
        citation = github_citation(fixture.repository, fixture.commit, file.path, chunk.start_line, chunk.end_line)
        item = {"chunk_id": chunk.id, "path": file.path, "symbol": chunk.symbol,
                "start_line": chunk.start_line, "end_line": chunk.end_line,
                "commit_sha": fixture.commit, "url": citation,
                "chunk_fingerprint": fingerprint_chunk(chunk, file)}
        if not citation_valid(item, fixture.repository, fixture.commit):
            raise ValueError("fixture_citation_invalid")
        inventory[chunk.id] = item
    links = db.execute(select(ChunkEmbedding, EmbeddingCache).join(
        EmbeddingCache, EmbeddingCache.id == ChunkEmbedding.cache_id)
        .where(ChunkEmbedding.chunk_id.in_(expected_chunks))).all()
    if len(links) != len(expected_chunks) or {link.chunk_id for link, _ in links} != set(expected_chunks):
        raise ValueError("fixture_vectors_incomplete")
    provider = ControlledProvider()
    for link, cached in links:
        expected = expected_chunks[link.chunk_id]
        source = files[expected.file_id].source.splitlines(keepends=True)
        expected_text = "".join(source[expected.start_line - 1:expected.end_line])
        if ((link.repository_id, link.tenant_id, cached.repository_id, cached.tenant_id,
             cached.provider, cached.model, cached.model_version, cached.model_revision,
             cached.representation_contract, cached.normalization, cached.dimensions, cached.status)
                != (fixture.repository_id, tenant_id, fixture.repository_id, tenant_id,
                    provider.provider, provider.model, provider.version, provider.revision,
                    provider.contract, provider.normalization, provider.dimensions, "ready")
                or link.chunk_fingerprint != inventory[link.chunk_id]["chunk_fingerprint"]
                or cached.content_hash != cache_key(expected_text) or len(cached.vector) != 3
                or any(not math.isclose(float(a), float(b), abs_tol=1e-6)
                       for a, b in zip(cached.vector, expected.vector, strict=True))):
            raise ValueError("fixture_vector_identity_mismatch")
    return inventory


def capture_fixture(factory, fixture: SyntheticFixture, *, tenant_id: int, user_id: int, clock=time.perf_counter):
    """Call production lexical, exact-vector and fusion paths on one fixture universe."""
    if fixture.split != "development":
        raise ValueError("synthetic_development_only")
    with factory() as db:
        inventory = _verified_inventory(db, fixture, tenant_id, user_id)
    universe_digest = _digest([[key, inventory[key]["chunk_fingerprint"]] for key in sorted(inventory)])
    stable = {"version": "synthetic-capture-output-v1", "dataset_id": fixture.dataset_id,
              "split": fixture.split, "source_identity": fixture.source_identity,
              "repository": fixture.repository, "commit_sha": fixture.commit,
              "snapshot_id": fixture.snapshot_id, "universe_count": len(inventory),
              "universe_digest": universe_digest, "config": fixture.config.model_dump(),
              "semantic_quality_status": "MECHANICAL_TEST_ONLY", "examples": []}
    records, observations = [], []
    provider = ControlledProvider()
    identity = {"provider": provider.provider, "model": provider.model, "revision": provider.revision,
                "representation_contract": provider.contract, "normalization": provider.normalization,
                "dimensions": provider.dimensions}
    for example in sorted(fixture.examples, key=lambda item: item.id):
        issue = example.issue
        body = (issue.body or "")[:fixture.config.query_body_limit]
        queries = build_queries_for_version(fixture.config.query_version, issue.title, body,
                                           issue.labels, fixture.config.query_limit)
        started = clock()
        candidates = retrieve_candidates(factory, queries=queries, snapshot_id=fixture.snapshot_id,
            repository_id=fixture.repository_id, tenant_id=tenant_id, commit=fixture.commit,
            full_name=fixture.repository, per_query_limit=fixture.config.per_query_limit,
            evidence_limit=fixture.config.evidence_limit, ranking_context=(issue.title, body))
        lexical_ms = (clock() - started) * 1000
        lexical = [item.chunk_id for item in candidates]
        if len(lexical) != len(set(lexical)) or any(item not in inventory for item in lexical):
            raise ValueError("fixture_lexical_universe_mismatch")
        for candidate in candidates:
            item = inventory[candidate.chunk_id]
            if (candidate.path, candidate.start_line, candidate.end_line, candidate.chunk_fingerprint) != (
                    item["path"], item["start_line"], item["end_line"], item["chunk_fingerprint"]):
                raise ValueError("fixture_lexical_integrity_mismatch")
        started = clock()
        with factory() as db:
            _verified_inventory(db, fixture, tenant_id, user_id)
            rows = search_vectors(db, repository_id=fixture.repository_id, tenant_id=tenant_id,
                snapshot_id=fixture.snapshot_id, provider=provider, query_vector=example.query_vector,
                limit=fixture.config.semantic_candidate_pool, expected_chunks=len(inventory))
        semantic_ms = (clock() - started) * 1000
        semantic = [chunk.id for chunk, _, _ in rows]
        if len(semantic) != len(set(semantic)) or any(item not in inventory for item in semantic):
            raise ValueError("fixture_semantic_universe_mismatch")
        started = clock()
        hybrid = [item for item, _ in reciprocal_rank_fusion([lexical, semantic], k=fixture.config.fusion_k)]
        hybrid_ms = lexical_ms + semantic_ms + (clock() - started) * 1000
        context = normalized_context(issue)
        query_info = [{"id": item.id, "text_sha256": hashlib.sha256(item.text.encode()).hexdigest()}
                      for item in queries]
        truncated = (len(issue.title) > 1024 or len(issue.body or "") > fixture.config.query_body_limit
                     or len(issue.labels) > 20 or any(len(label) > 100 for label in issue.labels[:20]))
        stable_example = {"id": example.id, "issue_id": issue.issue_id, "issue_number": issue.number,
                          "issue_state": issue.state, "issue_context_version": issue.version,
                          "context_sha256": context_digest(issue), "comment_order": [c["id"] for c in context["comments"]],
                          "comments_used_by_terms_v2": False, "query_version": fixture.config.query_version,
                          "query_input_truncated": truncated, "queries": query_info, "modes": {}}
        labels = [item.model_dump() for item in example.relevance]
        for mode, ids, elapsed in (("keyword", lexical, lexical_ms), ("semantic", semantic, semantic_ms),
                                   ("hybrid", hybrid, hybrid_ms)):
            if not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError("invalid_capture_time")
            items = [inventory[item] for item in ids[:fixture.config.top_k]]
            response = {"commit_sha": fixture.commit, "snapshot_id": fixture.snapshot_id, "mode": mode,
                        "lexical_strategy": "terms-v2" if mode in {"keyword", "hybrid"} else None,
                        "semantic_identity": identity if mode in {"semantic", "hybrid"} else None,
                        "semantic_quality_status": "MECHANICAL_TEST_ONLY",
                        "fallback_reason": None, "missing_embeddings": False, "items": items,
                        "context_sha256": stable_example["context_sha256"],
                        "issue_context_version": issue.version, "query_version": fixture.config.query_version,
                        "queries": query_info, "semantic_query_sha256": hashlib.sha256(issue.title.encode()).hexdigest(),
                        "retrieval_config": fixture.config.model_dump(),
                        "universe_digest": universe_digest, "citation_identity": "synthetic-fixture-only"}
            stable_example["modes"][mode] = {"items": items, "scores": score_query(labels, items)}
            records.append({"mode": mode, "query_id": example.id, "response": response, "latency_ms": elapsed})
            observations.append({"query_id": example.id, "mode": mode, "latency_ms": elapsed})
        stable["examples"].append(stable_example)
    with factory() as db:
        if _verified_inventory(db, fixture, tenant_id, user_id) != inventory:
            raise ValueError("fixture_changed_during_capture")
    return stable, records, {"kind": "synthetic-mechanical-timing-not-performance", "observations": observations}


def _disposable_url(value: str):
    try:
        url = make_url(value)
    except (ArgumentError, TypeError, ValueError):
        raise ValueError("disposable_database_required") from None
    if (url.drivername != "postgresql+psycopg" or url.host != "127.0.0.1" or not url.port
            or url.port <= 1024 or url.port == 5432 or url.username != "capture_fixture"
            or url.password or url.query
            or not re.fullmatch(r"repopilot_capture_disposable_[a-f0-9]{16}", url.database or "")):
        raise ValueError("disposable_database_required")
    return url


def verify_disposable_database(engine, url, *, require_empty: bool) -> None:
    """Confirm an explicitly marked synthetic database before any schema mutation."""
    with engine.connect() as connection:
        database, user, marker = connection.execute(text(
            "SELECT current_database(), current_user, shobj_description(oid, 'pg_database') "
            "FROM pg_database WHERE datname = current_database()")).one()
        if (database, user, marker) != (url.database, "capture_fixture", DATABASE_MARKER):
            raise ValueError("marked_disposable_database_required")
        if require_empty and connection.execute(text(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")).scalar_one():
            raise ValueError("empty_disposable_database_required")


def _write_json(directory: Path, name: str, value) -> None:
    fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, sort_keys=True)
        stream.write("\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    allowed_env = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "REPOPILOT_CAPTURE_DATABASE_URL",
                   "__PYVENV_LAUNCHER__", "__CF_USER_TEXT_ENCODING"}
    if set(os.environ) - allowed_env:
        raise SystemExit("clean_environment_required")
    fixture = load_registered_fixture(args.fixture)
    url = _disposable_url(os.environ.get("REPOPILOT_CAPTURE_DATABASE_URL", ""))
    output = args.output_dir
    project_root = FIXTURE_PATH.parents[4]
    output_parent = output.parent.resolve()
    if (not output.is_absolute() or output.exists() or output.is_symlink()
            or output_parent == project_root or project_root in output_parent.parents):
        raise SystemExit("new_output_directory_outside_project_required")
    engine = create_engine(url, hide_parameters=True)
    try:
        verify_disposable_database(engine, url, require_empty=True)
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        seed_synthetic_fixture(factory, fixture)
        stable, records, observations = capture_fixture(factory, fixture, tenant_id=fixture.tenant_id,
                                                        user_id=fixture.user_id)
        os.mkdir(output, 0o700)
        _write_json(output, "mechanical-report.json", stable)
        _write_json(output, "captures.json", records)
        _write_json(output, "observations.json", observations)
        print("Synthetic mechanical capture completed; no real model or repository was used.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
