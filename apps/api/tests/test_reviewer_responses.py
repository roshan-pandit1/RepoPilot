import copy
import json
from hashlib import sha256
import pytest
from app.evaluation.reviewer_responses import freeze_ground_truth, reconcile, score_adjudicated


def sample():
    manifest = json.dumps({"cases": [{"id": "one"}, {"id": "two"}]}).encode()
    response = {"case_id": "one", "decision": "present", "severity": "low", "confidence": "medium",
        "actionability": "yes", "start_line": 1, "end_line": 1, "minutes": 1,
        "reason": "Review this", "false_positive_reason": ""}
    bundle = {"version": "reviewer-responses-v1", "manifest_sha256": sha256(manifest).hexdigest(),
              "reviewer_reference": "reviewer-a", "responses": [response]}
    return manifest, bundle


def test_pending_disagreement_and_adjudication_are_distinct():
    manifest, a = sample()
    b = copy.deepcopy(a)
    b["reviewer_reference"] = "reviewer-b"
    b["responses"][0]["decision"] = "absent"
    out = reconcile(manifest, [a, b])
    assert out["cases"] == {"one": "disagreement", "two": "pending"}
    assert out["accuracy_metrics"] is None and out["reviewer_independence"] == "not independently verified"
    adjudication = [{"case_id": "one", "decision": "present", "adjudicator_reference": "reviewer-c", "reason": "reviewed evidence"}]
    assert reconcile(manifest, [a, b], adjudication)["cases"]["one"] == "adjudicated"
    adjudication[0]["adjudicator_reference"] = "reviewer-a"
    with pytest.raises(ValueError):
        reconcile(manifest, [a, b], adjudication)


def test_manifest_mismatch_and_duplicate_reviewer_are_rejected():
    manifest, bundle = sample()
    wrong = copy.deepcopy(bundle)
    wrong["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        reconcile(manifest, [wrong])
    with pytest.raises(ValueError):
        reconcile(manifest, [bundle, bundle])


def test_scoring_requires_adjudicated_evidence_and_two_reviewers():
    manifest = json.dumps({"cases": [{"id": "one", "source_file": "a.ts", "source_sha256": "b" * 64,
        "line_range": [1, 2], "language": "typescript", "review_scope": "snippet"}]}).encode()
    _, first = sample()
    first["manifest_sha256"] = sha256(manifest).hexdigest()
    second = copy.deepcopy(first)
    second["reviewer_reference"] = "reviewer-b"
    label = {"rule": "TS-EVAL-001", "path": "a.ts", "start": 1, "end": 1, "severity": "LOW"}
    decisions = [{"case_id": "one", "decision": "present", "adjudicator_reference": "reviewer-c",
                  "reason": "reviewed", "labels": [label]}]
    predictions = {"version": "review-predictions-v1", "manifest_sha256": sha256(manifest).hexdigest(),
        "analyzer": "synthetic-test", "cases": [{"case_id": "one", "supported": True, "findings": [label]}]}
    with pytest.raises(ValueError, match="two reviewer"):
        score_adjudicated(manifest, [first], decisions, predictions)
    result = score_adjudicated(manifest, [first, second], decisions, predictions)
    assert result["tp"] == 1 and result["precision"] == 1
    assert result["independence"] == "not independently verified"
    decisions[0]["labels"][0]["start"] = 9
    with pytest.raises(ValueError):
        score_adjudicated(manifest, [first, second], decisions, predictions)


def test_extended_reviewer_fields_are_accepted_without_inventing_independence():
    manifest, bundle = sample()
    bundle["responses"][0].update(file="example.py", category="SECURITY")
    result = reconcile(manifest, [bundle])
    assert result["cases"]["one"] == "awaiting_adjudication"
    assert result["reviewer_independence"] == "not independently verified"
    bundle["responses"][0]["category"] = "invented"
    with pytest.raises(ValueError):
        reconcile(manifest, [bundle])


def test_freeze_is_deterministic_and_rejects_unreviewed_cases():
    manifest = json.dumps({"cases": [{"id": "one", "source_file": "a.ts", "source_sha256": "b" * 64,
        "line_range": [1, 2], "language": "typescript", "review_scope": "snippet"}]}).encode()
    _, first = sample()
    first["manifest_sha256"] = sha256(manifest).hexdigest()
    second = copy.deepcopy(first)
    second["reviewer_reference"] = "reviewer-b"
    label = {"rule": "TS-EVAL-001", "path": "a.ts", "start": 1, "end": 1, "severity": "LOW"}
    decisions = [{"case_id": "one", "decision": "present", "adjudicator_reference": "reviewer-c",
                  "reason": "reviewed", "labels": [label]}]
    with pytest.raises(ValueError, match="two reviewer"):
        freeze_ground_truth(manifest, [first], decisions)
    frozen = freeze_ground_truth(manifest, [first, second], decisions)
    assert frozen == freeze_ground_truth(manifest, [second, first], decisions)
    assert json.loads(frozen)["reviewer_independence"] == "not independently verified"


def test_cli_requires_a_prior_matching_freeze_before_predictions(tmp_path, monkeypatch, capsys):
    from app.evaluation.reviewer_responses import main
    manifest = json.dumps({"cases": [{"id": "one", "source_file": "a.ts", "source_sha256": "b" * 64,
        "line_range": [1, 2], "language": "typescript", "review_scope": "snippet"}]}).encode()
    _, first = sample()
    first["manifest_sha256"] = sha256(manifest).hexdigest()
    second = copy.deepcopy(first)
    second["reviewer_reference"] = "reviewer-b"
    label = {"rule": "TS-EVAL-001", "path": "a.ts", "start": 1, "end": 1, "severity": "LOW"}
    decisions = [{"case_id": "one", "decision": "present", "adjudicator_reference": "reviewer-c",
                  "reason": "reviewed", "labels": [label]}]
    predictions = {"version": "review-predictions-v1", "manifest_sha256": sha256(manifest).hexdigest(),
        "analyzer": "synthetic-test", "cases": [{"case_id": "one", "supported": True, "findings": [label]}]}
    files = {"manifest": manifest, "first": json.dumps(first).encode(), "second": json.dumps(second).encode(),
             "decisions": json.dumps(decisions).encode(), "predictions": json.dumps(predictions).encode()}
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    args = ["reviewer_responses", str(tmp_path / "manifest"), str(tmp_path / "first"), str(tmp_path / "second"),
            "--adjudications", str(tmp_path / "decisions")]
    monkeypatch.setattr("sys.argv", args + ["--predictions", str(tmp_path / "predictions")])
    with pytest.raises(ValueError, match="previously frozen"):
        main()
    monkeypatch.setattr("sys.argv", args + ["--freeze", str(tmp_path / "frozen")])
    main()
    assert json.loads(capsys.readouterr().out)["ground_truth_sha256"]
    with pytest.raises(FileExistsError):
        main()
    monkeypatch.setattr("sys.argv", args + ["--ground-truth", str(tmp_path / "frozen"), "--predictions", str(tmp_path / "predictions")])
    main()
    assert json.loads(capsys.readouterr().out)["score"]["independence"] == "not independently verified"
    (tmp_path / "frozen").write_text("tampered")
    with pytest.raises(ValueError, match="mismatch"):
        main()
