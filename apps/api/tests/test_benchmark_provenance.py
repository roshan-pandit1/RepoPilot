"""Provenance checks use only synthetic local Git objects and controlled captures."""
import copy
import hashlib
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from app.evaluation import benchmark_provenance as provenance
from app.evaluation.git_source import GitSource
from app.evaluation.issue_context_schema import IssueContext, context_digest
from app.evaluation.retrieval_heldout import _expected_query_provenance
from app.modules.ingestion.citations import github_citation
from app.modules.investigation.retrieval import fingerprint_chunk


def git(repo, *args, data=None):
    env = {"PATH": os.defpath, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": ""}
    return subprocess.run(["git", "-C", str(repo), *args], input=data, env=env, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()


def issue(number, title, body, *, comments=()):
    return {"version": "issue-context-v1", "issue_id": 1000 + number, "number": number, "state": "open",
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z",
            "title": title, "body": body, "labels": ["bug"], "comment_count": len(comments),
            "comments": list(comments)}


def comment(number):
    stamp = f"2026-01-01T00:0{number}:00Z"
    return {"id": number, "created_at": stamp, "updated_at": stamp, "body": f"Synthetic comment {number}."}


@pytest.fixture
def prepared(tmp_path):
    repo = tmp_path / "git-source"
    repo.mkdir()
    git(repo, "init", "-q")
    raw = b"def add_numbers(a, b):\n    return a + b\n"
    blob = git(repo, "hash-object", "-w", "--stdin", data=raw)
    tree = git(repo, "mktree", data=f"100644 blob {blob}\tarithmetic.py\n".encode())
    commit_text = (f"tree {tree}\nauthor Fixture <fixture@example.invalid> 1700000000 +0000\n"
                   f"committer Fixture <fixture@example.invalid> 1700000000 +0000\n\nSynthetic fixture\n").encode()
    commit = git(repo, "hash-object", "-t", "commit", "-w", "--stdin", data=commit_text)
    file_id, chunk_id, snapshot_id = ("11000000-0000-4000-8000-000000000001",
        "22000000-0000-4000-8000-000000000001", "10000000-0000-4000-8000-000000000001")
    file_hash = hashlib.sha256(raw).hexdigest()
    fingerprint = fingerprint_chunk(SimpleNamespace(id=chunk_id, file_id=file_id, symbol="add_numbers",
        start_line=1, end_line=2, source_text=raw.decode()),
        SimpleNamespace(snapshot_id=snapshot_id, path="arithmetic.py", content_hash=file_hash))
    chunk = {"chunk_id": chunk_id, "file_id": file_id, "path": "arithmetic.py", "language": "python", "symbol": "add_numbers",
             "start_line": 1, "end_line": 2, "git_blob_sha1": blob, "file_sha256": file_hash,
             "chunk_sha256": file_hash, "chunk_fingerprint": fingerprint}
    inventory = {"version": "git-source-inventory-v1", "repository": "fixture/repo", "commit": commit,
                 "tenant_id": 42, "repository_id": 43, "snapshot_id": snapshot_id, "chunks": [chunk]}
    config = {"version": "capture-config-v1", "query_version": "terms-v2", "query_limit": 3,
              "query_body_limit": 4000, "per_query_limit": 10, "evidence_limit": 20,
              "semantic_candidate_pool": 20, "top_k": 10, "fusion_k": 60,
              "chunking_policy": "synthetic-line-v1", "semantic_representation": "controlled-v1",
              "semantic_query_policy": "issue-title-v1", "missing_vectors": "reject", "missing_results": "empty"}
    annotation = {"instructions": "Synthetic independent review", "adjudication_protocol": "Synthetic adjudication",
                  "exclusion_criteria": ["unknown source"]}
    review = {"annotators": ["reviewer-a", "reviewer-b"], "adjudicator": "reviewer-c", "uncertainty": "unknowns remain",
              "single_annotator_reason": None, "exclusion_reason": None}

    def query(name, context, labels, status):
        return {"id": name, "repository": "fixture/repo", "commit": commit, "query": context["title"],
                "language": "python", "category": "synthetic", "label_provenance": "synthetic reviewers",
                "adjudication_status": status, "annotation_record": copy.deepcopy(review),
                "issue_context": context, "relevance": labels}

    label = {"path": "arithmetic.py", "start_line": 1, "end_line": 2, "grade": 2}
    pilot = query("pilot-1", issue(1, "Pilot addition", "A pilot issue."), [label], "adjudicated")
    held = query("held-1", issue(2, "Addition is incorrect", "Arithmetic failure.",
                               comments=[comment(1), comment(2)]), [label], "adjudicated")
    unknown = query("held-2", issue(3, "Unknown telemetry", "No evidence."), [], "insufficient-evidence")
    development = {"version": "heldout-v2", "split": "development", "retrieval_config": config,
                   "annotation": annotation, "queries": [pilot]}
    heldout = {"version": "heldout-v2", "split": "held_out", "retrieval_config": copy.deepcopy(config),
               "annotation": annotation, "queries": [held, unknown]}
    digest = provenance._digest([[chunk_id, fingerprint]])
    identity = {"provider": "fake", "model": "fixture", "revision": "1", "tokenizer_revision": "1",
                "representation_contract": "f" * 64, "normalization": "l2", "dimensions": 3,
                "pooling": "cls", "query_prefix": "synthetic query: ", "document_prefix": ""}
    development["semantic_identity"] = copy.deepcopy(identity)
    heldout["semantic_identity"] = copy.deepcopy(identity)
    item = {"chunk_id": chunk_id, "path": "arithmetic.py", "symbol": "add_numbers", "start_line": 1, "end_line": 2,
            "chunk_fingerprint": fingerprint, "commit_sha": commit,
            "url": github_citation("fixture/repo", commit, "arithmetic.py", 1, 2)}
    captures = {}
    for current in heldout["queries"]:
        context = IssueContext.model_validate(current["issue_context"])
        for mode in ("keyword", "semantic", "hybrid"):
            response = {"repository": "fixture/repo", "tenant_id": 42, "repository_id": 43,
                "snapshot_id": snapshot_id, "commit_sha": commit, "universe_digest": digest, "mode": mode,
                "lexical_strategy": "terms-v2", "semantic_identity": copy.deepcopy(identity),
                "issue_context_version": "issue-context-v1", "context_sha256": context_digest(context),
                "query_version": "terms-v2", "queries": _expected_query_provenance(context, config),
                "semantic_query_sha256": hashlib.sha256(current["query"].encode()).hexdigest(),
                "retrieval_config": copy.deepcopy(config), "fallback_reason": None, "missing_embeddings": False,
                "items": [copy.deepcopy(item)]}
            captures[(mode, current["id"])] = (response, 1.0)
    return SimpleNamespace(repo=repo, raw=raw, blob=blob, tree=tree, commit=commit, inventory=inventory,
                           development=development, heldout=heldout, captures=captures, chunk=chunk,
                           roots={"fixture/repo": repo})


def validate(p):
    return provenance.validate_and_evaluate(p.development, p.heldout, [p.inventory], p.captures, roots=p.roots)


def test_real_local_git_objects_and_deterministic_scorer(prepared):
    first, second = validate(prepared), validate(prepared)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["provenance_validation"]["status"] == "CONSISTENCY_CHECKED_CAPTURE_ORIGIN_UNAUTHENTICATED"
    assert first["semantic_quality_status"] == "MECHANICAL_TEST_ONLY"
    assert first["modes"]["keyword"]["queries"][0]["recall"]["10"] == 1
    assert first["modes"]["keyword"]["queries"][1]["recall"]["10"] is None
    assert first["modes"]["keyword"]["invalid_citations"] == 0


def test_uncommitted_worktree_change_does_not_replace_pinned_blob(prepared):
    (prepared.repo / "arithmetic.py").write_text("different worktree content\n")
    assert validate(prepared)["modes"]["keyword"]["invalid_citations"] == 0
    prepared.inventory["chunks"][0]["file_sha256"] = hashlib.sha256(b"different worktree content\n").hexdigest()
    with pytest.raises(ValueError, match="file_identity_or_range_mismatch"):
        validate(prepared)


@pytest.mark.parametrize("change", ["commit", "blob", "path", "file_hash", "chunk_hash", "fingerprint", "range", "language"])
def test_git_inventory_rejects_tampering(prepared, change):
    inventory = prepared.inventory
    chunk = inventory["chunks"][0]
    if change == "commit":
        inventory["commit"] = "f" * 40
    elif change == "blob":
        chunk["git_blob_sha1"] = "f" * 40
    elif change == "path":
        chunk["path"] = "missing.py"
    elif change == "file_hash":
        chunk["file_sha256"] = "f" * 64
    elif change == "chunk_hash":
        chunk["chunk_sha256"] = "f" * 64
    elif change == "fingerprint":
        chunk["chunk_fingerprint"] = "f" * 64
    elif change == "language":
        chunk["language"] = "typescript"
    else:
        chunk["end_line"] = 20
    with pytest.raises(ValueError):
        provenance.verify_git_inventory(inventory, prepared.roots)


@pytest.mark.parametrize("change", ["url", "range", "chunk", "fingerprint", "snapshot", "tenant", "repository",
                                     "commit", "universe", "query_version", "model", "tokenizer", "snippet", "symbol"])
def test_capture_mismatch_fails_closed(prepared, change):
    response = prepared.captures[("semantic", "held-1")][0]
    if change == "url":
        response["items"][0]["url"] = "https://example.invalid/fake"
    elif change == "range":
        response["items"][0]["end_line"] = 3
    elif change == "chunk":
        response["items"][0]["chunk_id"] = "22000000-0000-4000-8000-000000000099"
    elif change == "fingerprint":
        response["items"][0]["chunk_fingerprint"] = "0" * 64
    elif change == "snapshot":
        response["snapshot_id"] = "10000000-0000-4000-8000-000000000099"
    elif change == "tenant":
        response["tenant_id"] = 999
    elif change == "repository":
        response["repository"] = "other/repo"
    elif change == "commit":
        response["commit_sha"] = "0" * 40
    elif change == "universe":
        response["universe_digest"] = "0" * 64
    elif change == "query_version":
        response["query_version"] = "terms-v1"
    elif change == "snippet":
        response["items"][0]["snippet"] = "tampered source\n"
    elif change == "symbol":
        response["items"][0]["symbol"] = "forged"
    else:
        response["semantic_identity"]["model" if change == "model" else "tokenizer_revision"] = "other"
    with pytest.raises(ValueError):
        validate(prepared)


@pytest.mark.parametrize("change", ["duplicate_issue", "duplicate_query", "context_leak", "semantic_leak",
                                     "missing_comments", "comment_order", "label_conflict", "missing_judgment",
                                     "excluded", "config", "label_range", "semantic_query"])
def test_dataset_identity_context_and_annotation_rejected(prepared, change):
    pilot, query = prepared.development["queries"][0], prepared.heldout["queries"][0]
    if change == "duplicate_issue":
        query["issue_context"]["issue_id"] = pilot["issue_context"]["issue_id"]
    elif change == "duplicate_query":
        query["id"] = pilot["id"]
    elif change == "context_leak":
        query["issue_context"]["title"] = pilot["issue_context"]["title"]
        query["issue_context"]["body"] = pilot["issue_context"]["body"]
        query["query"] = pilot["query"]
    elif change == "semantic_leak":
        query["issue_context"]["title"] = pilot["issue_context"]["title"]
        query["query"] = pilot["query"]
    elif change == "missing_comments":
        query["issue_context"]["comments"].pop()
    elif change == "comment_order":
        query["issue_context"]["comments"].reverse()
    elif change == "label_conflict":
        query["relevance"].append({**query["relevance"][0], "grade": 0})
    elif change == "missing_judgment":
        del query["annotation_record"]["annotators"]
    elif change == "excluded":
        query["annotation_record"]["exclusion_reason"] = "not eligible"
    elif change == "config":
        prepared.heldout["retrieval_config"]["fusion_k"] = 61
    elif change == "semantic_query":
        query["query"] += " arithmetic.py line 1"
    else:
        query["relevance"][0]["end_line"] = 3
    expected = "duplicate_issue_or_split_leakage" if change in {
        "duplicate_issue", "duplicate_query", "context_leak", "semantic_leak"} else None
    with pytest.raises(ValueError, match=expected):
        validate(prepared)


def test_single_annotator_requires_explanation(prepared):
    review = prepared.heldout["queries"][0]["annotation_record"]
    review["annotators"] = ["reviewer-a"]
    with pytest.raises(ValueError, match="single_annotator_reason_required"):
        validate(prepared)
    review["single_annotator_reason"] = "Second reviewer unavailable in synthetic test."
    assert validate(prepared)["provenance_validation"]["heldout_queries"] == 2


def test_model_contract_must_be_pinned_and_predeclared(prepared):
    identity = {"provider": "local-onnx", "model": "nomic-ai/CodeRankEmbed", "revision": "a" * 40,
                "tokenizer_revision": "b" * 40, "representation_contract": "f" * 64, "normalization": "l2",
                "dimensions": 768, "pooling": "cls",
                "query_prefix": "Represent this query for searching relevant code: ", "document_prefix": ""}
    assert provenance._semantic_identity(identity)[0] == "local-onnx"
    with pytest.raises(ValueError, match="unpinned_model_revision"):
        provenance._semantic_identity({**identity, "tokenizer_revision": "main"})
    with pytest.raises(ValueError, match="coderankembed_contract_mismatch"):
        provenance._semantic_identity({**identity, "pooling": "mean"})
    with pytest.raises(ValueError, match="invalid_semantic_identity"):
        provenance._semantic_identity({**identity, "provider": []})
    prepared.heldout["semantic_identity"]["revision"] = "changed"
    with pytest.raises(ValueError, match="split_semantic_identity_mismatch"):
        validate(prepared)


def test_title_and_bounded_body_semantic_policy(prepared):
    for dataset in (prepared.development, prepared.heldout):
        dataset["retrieval_config"]["semantic_query_policy"] = "issue-title-body-v1"
        for query in dataset["queries"]:
            query["query"] = query["issue_context"]["title"] + "\n\n" + query["issue_context"]["body"]
    for query in prepared.heldout["queries"]:
        for mode in ("keyword", "semantic", "hybrid"):
            response = prepared.captures[(mode, query["id"])][0]
            response["retrieval_config"]["semantic_query_policy"] = "issue-title-body-v1"
            response["semantic_query_sha256"] = hashlib.sha256(query["query"].encode()).hexdigest()
    assert validate(prepared)["provenance_validation"]["heldout_queries"] == 2


def test_unverifiable_chunk_range_and_duplicate_inventory_rejected(prepared):
    with pytest.raises(ValueError, match="duplicate_inventory"):
        provenance.validate_and_evaluate(prepared.development, prepared.heldout,
            [prepared.inventory, copy.deepcopy(prepared.inventory)], prepared.captures, roots=prepared.roots)
    label = prepared.heldout["queries"][0]["relevance"][0]
    label["start_line"] = label["end_line"] = 1
    # A valid Git range is insufficient if it is not covered by any declared chunk.
    prepared.inventory["chunks"][0]["start_line"] = 2
    source_chunk = "    return a + b\n"
    chunk = prepared.inventory["chunks"][0]
    chunk["chunk_sha256"] = hashlib.sha256(source_chunk.encode()).hexdigest()
    chunk["chunk_fingerprint"] = fingerprint_chunk(SimpleNamespace(id=chunk["chunk_id"], file_id=chunk["file_id"],
        symbol=chunk["symbol"], start_line=2, end_line=2, source_text=source_chunk),
        SimpleNamespace(snapshot_id=prepared.inventory["snapshot_id"], path=chunk["path"],
                        content_hash=chunk["file_sha256"]))
    with pytest.raises(ValueError, match="label_outside_inventory"):
        validate(prepared)


def test_git_replacement_refs_do_not_change_pinned_source(prepared):
    replacement = (f"tree {prepared.tree}\nauthor X <x@example.invalid> 1700000001 +0000\n"
                   f"committer X <x@example.invalid> 1700000001 +0000\n\nDifferent commit\n").encode()
    other = git(prepared.repo, "hash-object", "-t", "commit", "-w", "--stdin", data=replacement)
    git(prepared.repo, "update-ref", f"refs/replace/{prepared.commit}", other)
    assert validate(prepared)["provenance_validation"]["inventories"] == 1


def test_git_plumbing_caps_output_before_buffering_unbounded_data(prepared):
    blob = git(prepared.repo, "hash-object", "-w", "--stdin", data=b"x" * 4_000_001)
    source = GitSource(prepared.repo, prepared.commit, "fixture/repo")
    with pytest.raises(ValueError, match="Git output exceeds limit"):
        source._git("cat-file", "blob", blob)


def test_cli_creates_private_report_and_refuses_overwrite(prepared, tmp_path):
    input_values = {"development": prepared.development, "heldout": prepared.heldout,
                    "inventories": [prepared.inventory], "captures": [
                        {"mode": mode, "query_id": query_id, "response": response, "latency_ms": elapsed}
                        for (mode, query_id), (response, elapsed) in prepared.captures.items()]}
    paths = {}
    for name, data in input_values.items():
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(data))
    output = tmp_path / "report.json"
    argv = [part for name in input_values for part in (f"--{name}", str(paths[name]))]
    argv += ["--repository", f"fixture/repo={prepared.repo}", "--output", str(output)]
    provenance.main(argv)
    assert output.stat().st_mode & 0o777 == 0o600
    assert json.loads(output.read_text())["semantic_quality_status"] == "MECHANICAL_TEST_ONLY"
    assert prepared.raw.decode() not in output.read_text()
    with pytest.raises(FileExistsError):
        provenance.main(argv)
    argv[-1] = str(prepared.repo / "result.json")
    with pytest.raises(ValueError, match="output_inside_source_repository"):
        provenance.main(argv)
