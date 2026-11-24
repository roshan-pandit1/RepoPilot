"""Fixture-only capture tests; PostgreSQL tests require an explicitly disposable target."""
import builtins
import copy
import hashlib
import json
import os
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, delete, select

from app.domain.models import (ChunkEmbedding, CodeChunk, CodeSnapshot, EmbeddingCache, Installation,
                               Membership, Repository, SnapshotPublication, now)
from app.evaluation import capture_synthetic as capture
from app.evaluation import retrieval_heldout
from app.modules.ingestion.rank_fusion import reciprocal_rank_fusion
from app.modules.investigation.retrieval import SnapshotUnavailable


@pytest.fixture
def fixture_data():
    return capture.load_registered_fixture(capture.FIXTURE_PATH)


@pytest.fixture
def synthetic_pg(request, fixture_data):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("dedicated disposable PostgreSQL is required")
    # conftest's factory drops tables; reject any other target before requesting it.
    parsed = capture._disposable_url(url)
    engine = create_engine(parsed, hide_parameters=True)
    try:
        capture.verify_disposable_database(engine, parsed, require_empty=True)
    finally:
        engine.dispose()
    factory = request.getfixturevalue("factory")
    capture.seed_synthetic_fixture(factory, fixture_data)
    return factory


def test_fixture_preserves_complete_context_and_orders_comments(fixture_data):
    issue = fixture_data.examples[0].issue
    assert "src/arithmetic.py" in issue.body and "add_numbers" in issue.body
    assert issue.labels == ["bug", "arithmetic"] and issue.comment_count == 2
    normalized = capture.normalized_context(issue)
    assert [item["id"] for item in normalized["comments"]] == [83001, 83002]
    assert [item["body"] for item in normalized["comments"]] == [
        "The arithmetic path is involved.", "The ledger total is also involved."]
    reversed_issue = issue.model_copy(update={"comments": list(reversed(issue.comments))})
    assert capture.normalized_context(reversed_issue) == normalized


def test_fixture_inventory_is_multilingual_and_labels_are_explicit(fixture_data):
    assert {item.language for item in fixture_data.files} == {"python", "typescript"}
    assert {"add_numbers", "add_number_label", "calculateTotal", "calculateTax"} <= {
        item.symbol for item in fixture_data.chunks}
    assert "Traceback" in fixture_data.examples[0].issue.body
    assert len(fixture_data.examples[0].relevance) == 2
    assert fixture_data.examples[1].adjudication == "insufficient-evidence"
    assert fixture_data.examples[1].relevance == []


@pytest.mark.parametrize("mutation", ["missing_title", "missing_state", "invalid_issue_time", "missing_labels", "missing_comments", "comment_count",
                                       "duplicate_comment", "bad_comment_time", "missing_labels_for_judged",
                                       "unexpected_insufficient_labels", "bad_label_range", "sensitive_context", "unknown_field"])
def test_malformed_context_and_incomplete_labels_are_rejected(fixture_data, mutation):
    data = fixture_data.model_dump(mode="json")
    example = data["examples"][0]
    issue = example["issue"]
    if mutation == "missing_title":
        del issue["title"]
    elif mutation == "missing_state":
        del issue["state"]
    elif mutation == "invalid_issue_time":
        issue["updated_at"] = "2025-01-01T00:00:00Z"
    elif mutation == "missing_labels":
        del issue["labels"]
    elif mutation == "missing_comments":
        del issue["comments"]
    elif mutation == "comment_count":
        issue["comment_count"] = 3
    elif mutation == "duplicate_comment":
        issue["comments"][1]["id"] = issue["comments"][0]["id"]
    elif mutation == "bad_comment_time":
        issue["comments"][0]["created_at"] = "not-a-time"
    elif mutation == "missing_labels_for_judged":
        example["relevance"] = []
    elif mutation == "unexpected_insufficient_labels":
        example["adjudication"] = "insufficient-evidence"
    elif mutation == "bad_label_range":
        example["relevance"][0]["end_line"] = 99
    elif mutation == "sensitive_context":
        issue["comments"][0]["body"] = "ghp_" + "a" * 36
    else:
        issue["unreviewed"] = True
    with pytest.raises(ValidationError):
        capture.SyntheticFixture.model_validate(data)


@pytest.mark.parametrize("mutation", ["duplicate_chunk", "missing_chunk", "source_hash", "foreign_file",
                                       "unsafe_path", "invalid_vector", "mixed_source_identity"])
def test_inventory_and_identity_reject_malformed_data(fixture_data, mutation):
    data = fixture_data.model_dump(mode="json")
    if mutation == "duplicate_chunk":
        data["chunks"].append(copy.deepcopy(data["chunks"][0]))
    elif mutation == "missing_chunk":
        data["chunks"].pop()
    elif mutation == "source_hash":
        data["files"][0]["source"] += "tampered\n"
    elif mutation == "foreign_file":
        data["chunks"][0]["file_id"] = "f0000000-0000-4000-8000-000000000001"
    elif mutation == "unsafe_path":
        data["files"][0]["path"] = "../arithmetic.py"
    elif mutation == "invalid_vector":
        data["chunks"][0]["vector"] = [0.0, 0.0, 0.0]
    else:
        data["source_identity"] = "real-repository"
    with pytest.raises(ValidationError):
        capture.SyntheticFixture.model_validate(data)


def test_registered_fixture_and_development_heldout_separation(fixture_data, tmp_path):
    copied = tmp_path / "fixture.json"
    copied.write_text(capture.FIXTURE_PATH.read_text())
    with pytest.raises(ValueError, match="unregistered_fixture"):
        capture.load_registered_fixture(copied)
    data = fixture_data.model_dump(mode="json")
    data["split"] = "held_out"
    data["dataset_id"] = "heldout-fixture"
    held = capture.SyntheticFixture.model_validate(data)
    with pytest.raises(ValueError, match="split_leakage"):
        capture.assert_split_separation(fixture_data, held)
    for index, item in enumerate(data["examples"]):
        item["id"] = f"heldout-issue-{index}"
        item["issue"]["number"] += 100
        item["issue"]["issue_id"] += 100
        if index:
            item["issue"]["title"] = f"Independent synthetic question {index}"
            item["issue"]["body"] = "Distinct context"
    data["examples"][0]["issue"]["title"] = "  CALCULATE   TOTAL ADDITION FAILS  "
    with pytest.raises(ValueError, match="split_leakage"):
        capture.assert_split_separation(fixture_data, capture.SyntheticFixture.model_validate(data))
    for index, item in enumerate(data["examples"]):
        item["issue"]["title"] = f"Independent synthetic question {index}"
        item["issue"]["body"] = "Distinct context"
    capture.assert_split_separation(fixture_data, capture.SyntheticFixture.model_validate(data))


def test_registered_fixture_hash_rejects_tampering(fixture_data, tmp_path, monkeypatch):
    copied = tmp_path / "fixture.json"
    copied.write_text(capture.FIXTURE_PATH.read_text() + " ")
    monkeypatch.setattr(capture, "FIXTURE_PATH", copied)
    with pytest.raises(ValueError, match="fixture_identity_mismatch"):
        capture.load_registered_fixture(copied)


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://capture_fixture@127.0.0.1:5432/repopilot",
    "postgresql+psycopg://capture_fixture@localhost:54321/repopilot_capture_disposable_0123456789abcdef",
    "postgresql+psycopg://other@127.0.0.1:54321/repopilot_capture_disposable_0123456789abcdef",
    "postgresql+psycopg://capture_fixture:password@127.0.0.1:54321/repopilot_capture_disposable_0123456789abcdef",
    "postgresql+psycopg://capture_fixture@127.0.0.1:54321/repopilot-local",
    "sqlite:///fixture.db",
    "not-a-database-url",
])
def test_database_guard_rejects_application_or_ambiguous_targets(url):
    with pytest.raises(ValueError, match="disposable_database_required"):
        capture._disposable_url(url)


def test_environment_guard_runs_before_database_access(monkeypatch, tmp_path):
    monkeypatch.setenv("UNEXPECTED_SECRET", "not-a-real-secret")
    monkeypatch.setattr(capture, "create_engine", lambda *_a, **_k: pytest.fail("database accessed"))
    with pytest.raises(SystemExit, match="clean_environment_required"):
        capture.main(["--output-dir", str(tmp_path / "output")])


def test_database_marker_is_required_before_schema_changes():
    class Result:
        def one(self):
            return ("repopilot_capture_disposable_0123456789abcdef", "capture_fixture", None)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _statement):
            return Result()

    class Engine:
        def connect(self):
            return Connection()

    url = SimpleNamespace(database="repopilot_capture_disposable_0123456789abcdef")
    with pytest.raises(ValueError, match="marked_disposable_database_required"):
        capture.verify_disposable_database(Engine(), url, require_empty=True)


def test_production_terms_v2_context_truncation_and_comment_exclusion(synthetic_pg, fixture_data, monkeypatch):
    data = fixture_data.model_dump(mode="json")
    issue = data["examples"][0]["issue"]
    issue["body"] += "x" * 4100
    issue["labels"] = ["arithmetic" * 15] + ["label"] * 21
    fixture = capture.SyntheticFixture.model_validate(data)
    seen = []
    original_build, original_retrieve = capture.build_queries_for_version, capture.retrieve_candidates

    def build(*args, **kwargs):
        seen.append(("build", args))
        return original_build(*args, **kwargs)

    def retrieve(*args, **kwargs):
        seen.append(("retrieve", kwargs))
        return original_retrieve(*args, **kwargs)

    monkeypatch.setattr(capture, "build_queries_for_version", build)
    monkeypatch.setattr(capture, "retrieve_candidates", retrieve)
    stable, records, _ = capture.capture_fixture(synthetic_pg, fixture, tenant_id=fixture.tenant_id,
                                                 user_id=fixture.user_id)
    first = stable["examples"][0]
    assert first["query_input_truncated"] and not first["comments_used_by_terms_v2"]
    assert first["comment_order"] == [83001, 83002]
    build_args = next(args for name, args in seen if name == "build")
    assert build_args[0] == "terms-v2" and len(build_args[2]) == 4000 and build_args[3] == issue["labels"]
    expected_queries = original_build(*build_args)
    assert first["queries"] == [{"id": q.id, "text_sha256": hashlib.sha256(q.text.encode()).hexdigest()}
                                for q in expected_queries]
    kwargs = next(args for name, args in seen if name == "retrieve")
    assert kwargs["ranking_context"] == (issue["title"], issue["body"][:4000])
    assert all(record["response"]["query_version"] == "terms-v2" for record in records)


def test_capture_is_deterministic_fused_and_uses_one_eligible_universe(synthetic_pg, fixture_data):
    first, records, observations = capture.capture_fixture(synthetic_pg, fixture_data,
        tenant_id=fixture_data.tenant_id, user_id=fixture_data.user_id)
    second, _, _ = capture.capture_fixture(synthetic_pg, fixture_data,
        tenant_id=fixture_data.tenant_id, user_id=fixture_data.user_id)
    assert first == second and first["semantic_quality_status"] == "MECHANICAL_TEST_ONLY"
    assert first["universe_count"] == 6 and len(records) == 6 and len(observations["observations"]) == 6
    assert {item["response"]["universe_digest"] for item in records} == {first["universe_digest"]}
    assert all(item["response"]["semantic_quality_status"] == "MECHANICAL_TEST_ONLY" for item in records)
    case = first["examples"][0]["modes"]
    lexical = [item["chunk_id"] for item in case["keyword"]["items"]]
    semantic = [item["chunk_id"] for item in case["semantic"]["items"]]
    hybrid = [item["chunk_id"] for item in case["hybrid"]["items"]]
    assert semantic[:2] == ["22000000-0000-4000-8000-000000000001", "22000000-0000-4000-8000-000000000004"]
    assert hybrid == [item for item, _ in reciprocal_rank_fusion([lexical, semantic], k=60)]
    assert case["keyword"]["scores"]["recall"]["10"] == 1.0
    assert first["examples"][1]["modes"]["semantic"]["scores"]["recall"]["10"] is None
    assert observations["kind"] == "synthetic-mechanical-timing-not-performance"
    serialized = json.dumps([first, records])
    assert fixture_data.examples[0].issue.body not in serialized
    assert fixture_data.examples[0].issue.comments[0].body not in serialized
    assert fixture_data.files[0].source not in serialized


def test_context_aware_heldout_contract_checks_captures(synthetic_pg, fixture_data, tmp_path, monkeypatch):
    class FixtureSource:
        def __init__(self, _root, _commit, _repo):
            self.blobs = {hashlib.sha1(file.source.encode()).hexdigest(): file.source.encode()
                          for file in fixture_data.files}
            self.entries = [{"path": file.path, "sha": hashlib.sha1(file.source.encode()).hexdigest(),
                             "size": len(file.source.encode())} for file in fixture_data.files]

        def blob(self, _token, _repo, sha, size):
            raw = self.blobs[sha]
            assert len(raw) == size
            return raw

    monkeypatch.setattr(retrieval_heldout, "GitSource", FixtureSource)
    _, records, _ = capture.capture_fixture(synthetic_pg, fixture_data, tenant_id=fixture_data.tenant_id,
                                            user_id=fixture_data.user_id)
    dataset = {"version": "heldout-v2", "split": "held_out",
               "retrieval_config": fixture_data.config.model_dump(),
               "annotation": {"instructions": fixture_data.annotation.instructions,
                              "adjudication_protocol": "synthetic fixture protocol",
                              "exclusion_criteria": fixture_data.annotation.exclusion_criteria},
               "queries": []}
    for item in fixture_data.examples:
        dataset["queries"].append({"id": item.id, "repository": fixture_data.repository,
            "commit": fixture_data.commit, "query": item.issue.title, "language": "mixed",
            "category": "synthetic", "label_provenance": "fixture-derived",
            "adjudication_status": "adjudicated" if item.relevance else "insufficient-evidence",
            "issue_context": item.issue.model_dump(), "relevance": [label.model_dump() for label in item.relevance]})
    captures = {(item["mode"], item["query_id"]): (item["response"], item["latency_ms"]) for item in records}
    roots = {fixture_data.repository: tmp_path}
    result = retrieval_heldout.evaluate(dataset, captures, roots=roots)
    assert result["context_validation"] == "issue-context-v1"
    assert result["semantic_quality_status"] == "MECHANICAL_TEST_ONLY"
    tampered = copy.deepcopy(captures)
    tampered[("keyword", fixture_data.examples[0].id)][0]["queries"][0]["text_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="issue_context_capture_mismatch"):
        retrieval_heldout.evaluate(dataset, tampered, roots=roots)
    tampered = copy.deepcopy(captures)
    tampered[("semantic", fixture_data.examples[0].id)][0]["semantic_query_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="issue_context_capture_mismatch"):
        retrieval_heldout.evaluate(dataset, tampered, roots=roots)
    tampered = copy.deepcopy(captures)
    tampered[("semantic", fixture_data.examples[0].id)][0]["universe_digest"] = "0" * 64
    with pytest.raises(ValueError, match="candidate_universe_mismatch"):
        retrieval_heldout.evaluate(dataset, tampered, roots=roots)
    tampered = copy.deepcopy(captures)
    tampered[("semantic", fixture_data.examples[0].id)][0]["missing_embeddings"] = True
    with pytest.raises(ValueError, match="issue_context_capture_mismatch"):
        retrieval_heldout.evaluate(dataset, tampered, roots=roots)
    tampered = copy.deepcopy(captures)
    for mode in retrieval_heldout.MODES:
        tampered[(mode, fixture_data.examples[1].id)][0]["universe_digest"] = "0" * 64
    with pytest.raises(ValueError, match="candidate_universe_mismatch"):
        retrieval_heldout.evaluate(dataset, tampered, roots=roots)
    tampered = copy.deepcopy(captures)
    tampered[("hybrid", fixture_data.examples[0].id)][0]["retrieval_config"]["fusion_k"] = 61
    with pytest.raises(ValueError, match="issue_context_capture_mismatch"):
        retrieval_heldout.evaluate(dataset, tampered, roots=roots)
    malformed = copy.deepcopy(dataset)
    del malformed["queries"][0]["issue_context"]["comments"]
    with pytest.raises(ValueError, match="invalid_issue_context"):
        retrieval_heldout.validate_dataset(malformed, roots)
    incomplete = copy.deepcopy(dataset)
    incomplete["queries"][0]["relevance"] = []
    with pytest.raises(ValueError, match="invalid_adjudication"):
        retrieval_heldout.validate_dataset(incomplete, roots)
    malformed = copy.deepcopy(dataset)
    malformed["retrieval_config"]["semantic_candidate_pool"] = 5
    with pytest.raises(ValueError, match="invalid_retrieval_config"):
        retrieval_heldout.validate_dataset(malformed, roots)
    malformed = copy.deepcopy(dataset)
    del malformed["annotation"]["adjudication_protocol"]
    with pytest.raises(ValueError, match="invalid_annotation_protocol"):
        retrieval_heldout.validate_dataset(malformed, roots)


def test_comments_change_context_digest_not_production_queries(synthetic_pg, fixture_data):
    data = fixture_data.model_dump(mode="json")
    data["examples"][0]["issue"]["comments"][0]["body"] = "Different synthetic comment text."
    changed = capture.SyntheticFixture.model_validate(data)
    before, _, _ = capture.capture_fixture(synthetic_pg, fixture_data,
        tenant_id=fixture_data.tenant_id, user_id=fixture_data.user_id)
    after, _, _ = capture.capture_fixture(synthetic_pg, changed,
        tenant_id=changed.tenant_id, user_id=changed.user_id)
    assert before["examples"][0]["context_sha256"] != after["examples"][0]["context_sha256"]
    assert before["examples"][0]["queries"] == after["examples"][0]["queries"]
    assert before["examples"][0]["modes"]["keyword"] == after["examples"][0]["modes"]["keyword"]


@pytest.mark.parametrize("change", ["foreign_tenant", "membership", "installation", "repository"])
def test_current_fixture_access_is_required(synthetic_pg, fixture_data, change):
    tenant = fixture_data.tenant_id
    if change == "foreign_tenant":
        tenant += 1
    else:
        with synthetic_pg.begin() as db:
            if change == "membership":
                db.delete(db.get(Membership, (tenant, fixture_data.user_id)))
            elif change == "installation":
                db.get(Installation, fixture_data.installation_id).active = False
            else:
                db.get(Repository, fixture_data.repository_id).enabled = False
    with pytest.raises(ValueError, match="fixture_access_denied"):
        capture.capture_fixture(synthetic_pg, fixture_data, tenant_id=tenant, user_id=fixture_data.user_id)


@pytest.mark.parametrize("change", ["missing_vector", "mixed_model", "tampered_chunk", "extra_chunk"])
def test_inventory_and_vector_integrity_fail_closed(synthetic_pg, fixture_data, change):
    with synthetic_pg.begin() as db:
        first = fixture_data.chunks[0]
        if change == "missing_vector":
            db.execute(delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id == first.id))
        elif change == "mixed_model":
            link = db.scalar(select(ChunkEmbedding).where(ChunkEmbedding.chunk_id == first.id))
            db.get(EmbeddingCache, link.cache_id).model = "foreign-model"
        elif change == "tampered_chunk":
            db.get(CodeChunk, first.id).source_text = "tampered\n"
        else:
            db.add(CodeChunk(id="22000000-0000-4000-8000-000000000099", file_id=first.file_id,
                repository_id=fixture_data.repository_id, tenant_id=fixture_data.tenant_id,
                symbol="extra", start_line=99, end_line=99, source_text="extra\n"))
    with pytest.raises(ValueError, match="fixture_.*(incomplete|mismatch)"):
        capture.capture_fixture(synthetic_pg, fixture_data, tenant_id=fixture_data.tenant_id,
                                user_id=fixture_data.user_id)


@pytest.mark.parametrize("change", ["snapshot", "commit", "revoked"])
def test_snapshot_and_commit_mismatch_are_rejected(synthetic_pg, fixture_data, change):
    if change == "snapshot":
        fixture_data = fixture_data.model_copy(update={"snapshot_id": "10000000-0000-4000-8000-000000000099"})
    elif change == "commit":
        with synthetic_pg.begin() as db:
            db.get(CodeSnapshot, fixture_data.snapshot_id).commit_sha = "b" * 40
    else:
        with synthetic_pg.begin() as db:
            publication = db.get(SnapshotPublication, fixture_data.snapshot_id)
            publication.revoked_at, publication.revocation_reason = now(), "security"
    with pytest.raises(SnapshotUnavailable):
        capture.capture_fixture(synthetic_pg, fixture_data, tenant_id=fixture_data.tenant_id,
                                user_id=fixture_data.user_id)


def test_forged_citation_is_rejected(synthetic_pg, fixture_data, monkeypatch):
    monkeypatch.setattr(capture, "github_citation", lambda *_args: "https://example.invalid/forged")
    with pytest.raises(ValueError, match="fixture_citation_invalid"):
        capture.capture_fixture(synthetic_pg, fixture_data, tenant_id=fixture_data.tenant_id,
                                user_id=fixture_data.user_id)


def test_capture_never_imports_a_real_model(synthetic_pg, fixture_data, monkeypatch):
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.startswith(("onnxruntime", "tokenizers")):
            pytest.fail("real model runtime import attempted")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    stable, _, _ = capture.capture_fixture(synthetic_pg, fixture_data,
        tenant_id=fixture_data.tenant_id, user_id=fixture_data.user_id)
    assert stable["semantic_quality_status"] == "MECHANICAL_TEST_ONLY"
