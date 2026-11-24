import math
import json
from pathlib import Path

import pytest

from app.evaluation.retrieval_heldout import ann_recall, evaluate, main, paired_interval, score_query, validate_dataset


def test_graded_labels_unjudged_duplicates_and_missing_evidence():
    labels = [{"path": "a.py", "start_line": 1, "end_line": 1, "grade": 3},
              {"path": "b.py", "start_line": 2, "end_line": 2, "grade": 1},
              {"path": "c.py", "start_line": 3, "end_line": 3, "grade": 0}]
    a = {"path": "a.py", "start_line": 1, "end_line": 1}
    b = {"path": "b.py", "start_line": 2, "end_line": 2}
    unknown = {"path": "x.py", "start_line": 1, "end_line": 1}
    result = score_query(labels, [unknown, a, a, b])
    assert result["recall"]["1"] == 0 and result["recall"]["5"] == 1
    assert result["judged_precision"]["5"] == 2 / 3
    assert result["precision_at_k_bounds"]["5"] == {"lower": .4, "upper": .6}
    assert result["unjudged"] == 1 and result["mrr"] == .5
    assert 0 < result["ndcg_at_10"] < 1
    empty = score_query([], [unknown])
    assert empty["recall"]["10"] is None and empty["judged_precision"]["10"] is None
    assert empty["ndcg_at_10"] is None and empty["unjudged"] == 1
    two = [{"path": "a.py", "start_line": 1, "end_line": 1, "grade": 1},
           {"path": "a.py", "start_line": 2, "end_line": 2, "grade": 1}]
    assert score_query(two, [{"path": "a.py", "start_line": 1, "end_line": 2}])["recall"]["1"] == 1


def test_paired_capture_requires_same_commit_snapshot_and_tracks_citations(tmp_path, monkeypatch):
    class Source:
        def __init__(self, root, commit, repo):
            self.entries = [{"path": "x.py", "sha": "b" * 40, "size": 4}]
        def blob(self, *_args):
            return b"x=1\n"
    monkeypatch.setattr("app.evaluation.retrieval_heldout.GitSource", Source)
    sha = "a" * 40
    query = {"id": "q", "repository": "alice/repo", "commit": sha, "query": "find f",
             "language": "python", "category": "symbol", "label_provenance": "reviewed fixture",
             "relevance": [{"path": "x.py", "start_line": 1, "end_line": 1, "grade": 1}]}
    dataset = {"version": "heldout-v1", "split": "held_out", "queries": [query]}
    item = {"path": "x.py", "start_line": 1, "end_line": 1, "commit_sha": sha,
            "url": f"https://github.com/alice/repo/blob/{sha}/x.py#L1-L1"}
    identity = {"provider": "fake", "model": "fixture", "revision": "1", "dimensions": 8, "representation_contract": "f" * 64,
                "normalization": "none"}
    responses = {(mode, "q"): ({"commit_sha": sha, "snapshot_id": "snapshot", "mode": mode, "lexical_strategy": "terms-v2", "semantic_identity": identity,
                                  "items": [item]}, 3.0) for mode in ("keyword", "semantic", "hybrid")}
    result = evaluate(dataset, responses, roots={"alice/repo": tmp_path})
    assert result["semantic_quality_status"] == "MECHANICAL_TEST_ONLY"
    assert result["context_validation"] == "legacy-query-only-unverified"
    assert result["modes"]["semantic"]["recall"]["10"] == 1
    assert result["modes"]["hybrid"]["per_language_recall_at_10"]["python"] == 1
    assert result["modes"]["keyword"]["invalid_citations"] == 0
    # A well-formed URL alone does not establish that its file, range, or
    # returned source exists at the pinned commit.
    forged = [{**item, "path": "missing.py", "url": f"https://github.com/alice/repo/blob/{sha}/missing.py#L1-L1"},
              {**item, "end_line": 2, "url": f"https://github.com/alice/repo/blob/{sha}/x.py#L1-L2"},
              {**item, "snippet": "tampered\n"}]
    responses[("keyword", "q")][0]["items"] = forged
    result = evaluate(dataset, responses, roots={"alice/repo": tmp_path})
    assert result["modes"]["keyword"]["invalid_citations"] == 3
    assert result["modes"]["keyword"]["recall"]["10"] == 0
    responses[("keyword", "q")][0]["items"] = [{**item, "snippet": "x=1\n"}]
    assert evaluate(dataset, responses, roots={"alice/repo": tmp_path})["modes"]["keyword"]["invalid_citations"] == 0
    responses[("hybrid", "q")][0]["semantic_identity"] = {**identity, "representation_contract": "e" * 64}
    with pytest.raises(ValueError, match="embedding_space_mismatch"):
        evaluate(dataset, responses, roots={"alice/repo": tmp_path})
    responses[("hybrid", "q")][0]["semantic_identity"] = {**identity, "dimensions": 16}
    with pytest.raises(ValueError, match="embedding_space_mismatch"):
        evaluate(dataset, responses, roots={"alice/repo": tmp_path})
    responses[("hybrid", "q")][0]["semantic_identity"] = identity
    responses[("hybrid", "q")][0]["snapshot_id"] = "different"
    with pytest.raises(ValueError, match="snapshot_mismatch"):
        evaluate(dataset, responses, roots={"alice/repo": tmp_path})


def test_git_dataset_validation_rejects_unheldout_and_bad_ranges(tmp_path, monkeypatch):
    class Source:
        def __init__(self, root, commit, repo):
            self.entries = [{"path": "x.py", "sha": "a" * 40, "size": 4}]
        def blob(self, *_args):
            return b"x=1\n"
    monkeypatch.setattr("app.evaluation.retrieval_heldout.GitSource", Source)
    query = {"id": "q", "repository": "a/b", "commit": "a" * 40, "query": "x",
             "language": "python", "category": "symbol", "label_provenance": "reviewed",
             "relevance": [{"path": "x.py", "start_line": 1, "end_line": 1, "grade": 1}]}
    data = {"version": "heldout-v1", "split": "held_out", "queries": [query]}
    validate_dataset(data, {"a/b": tmp_path})
    query["relevance"][0]["end_line"] = 2
    with pytest.raises(ValueError, match="invalid_label_range"):
        validate_dataset(data, {"a/b": tmp_path})
    with pytest.raises(ValueError, match="invalid_dataset_split"):
        validate_dataset({**data, "split": "training"}, {"a/b": tmp_path})


def test_ann_and_paired_uncertainty_are_bounded_and_deterministic():
    assert ann_recall(["a", "b", "c"], ["b", "x", "a"], 3) == 2 / 3
    assert ann_recall([], [], 3) is None
    with pytest.raises(ValueError):
        ann_recall(["a", "a"], ["a"], 2)
    assert paired_interval([0], [1]) is None
    interval = paired_interval([0] * 5, [1] * 5, seed=7, samples=100)
    assert interval == paired_interval([0] * 5, [1] * 5, seed=7, samples=100)
    assert math.isclose(interval["mean_difference"], 1) and interval["low"] == interval["high"] == 1


def test_offline_cli_reads_captures_and_refuses_overwrite(tmp_path, monkeypatch):
    class Source:
        def __init__(self, root, commit, repo):
            self.entries = []
    monkeypatch.setattr("app.evaluation.retrieval_heldout.GitSource", Source)
    sha = "a" * 40
    query = {"id": "q", "repository": "alice/repo", "commit": sha, "query": "missing",
             "language": "python", "category": "missing", "label_provenance": "fixture", "relevance": []}
    dataset = {"version": "heldout-v1", "split": "held_out", "queries": [query]}
    identity = {"provider": "fake", "model": "fixture", "revision": "1", "dimensions": 8,
                "representation_contract": "f" * 64, "normalization": "none"}
    records = [{"mode": mode, "query_id": "q", "latency_ms": 1.0,
                "response": {"commit_sha": sha, "snapshot_id": "snapshot", "mode": mode,
                             "lexical_strategy": "terms-v2", "semantic_identity": identity, "items": []}}
               for mode in ("keyword", "semantic", "hybrid")]
    dataset_path, captures_path, output_path = (tmp_path / name for name in ("dataset.json", "captures.json", "result.json"))
    dataset_path.write_text(json.dumps(dataset))
    captures_path.write_text(json.dumps(records))
    argv = ["--dataset", str(dataset_path), "--captures", str(captures_path),
            "--repository", f"alice/repo={tmp_path}", "--output", str(output_path)]
    main(argv)
    assert json.loads(output_path.read_text())["semantic_quality_status"] == "MECHANICAL_TEST_ONLY"
    assert output_path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        main(argv)
    captures_path.write_text(json.dumps(records + [records[0]]))
    with pytest.raises(ValueError, match="duplicate_capture"):
        main(argv)


def test_validation_reads_pinned_local_git_objects_without_modifying_repository():
    # This exercises Git/range validation only; it is not a held-out quality evaluation.
    root = Path(__file__).resolve().parents[3]
    existing = json.loads((root / "apps/api/evaluation/investigation-evidence-v1.json").read_text())
    case = existing["cases"][0]
    label = {**case["labels"][0], "grade": 1}
    query = {"id": "fixture", "repository": "alice/public", "commit": existing["source_commit"],
             "query": case["title"], "language": "python", "category": "symbol",
             "label_provenance": "existing synthetic regression fixture", "relevance": [label]}
    dataset = {"version": "heldout-v1", "split": "held_out", "queries": [query]}
    validate_dataset(dataset, {"alice/public": root})
    start, end, path, sha = label["start_line"], label["end_line"], label["path"], existing["source_commit"]
    item = {"path": path, "start_line": start, "end_line": end, "commit_sha": sha,
            "url": f"https://github.com/alice/public/blob/{sha}/{path}#L{start}-L{end}"}
    identity = {"provider": "fake", "model": "fixture", "revision": "1", "dimensions": 8, "representation_contract": "f" * 64,
                "normalization": "none"}
    captures = {(mode, "fixture"): ({"commit_sha": sha, "snapshot_id": "synthetic", "mode": mode,
        "lexical_strategy": "terms-v2", "semantic_identity": identity, "items": [item]}, 1.0)
        for mode in ("keyword", "semantic", "hybrid")}
    result = evaluate(dataset, captures, roots={"alice/public": root})
    assert result["modes"]["keyword"]["invalid_citations"] == 0
    assert result["modes"]["keyword"]["recall"]["10"] == 1
