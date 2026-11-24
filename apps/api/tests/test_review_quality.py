import copy
import pytest
from app.evaluation.review_quality import evaluate


def data():
    loc = {"rule": "RULE-1", "path": "src/a.py", "start": 4, "end": 5, "severity": "MEDIUM"}
    return {
        "version": "review-quality-v1",
        "split": "regression",
        "analyzer": "fixture-v1",
        "cases": [
            {
                "id": "one",
                "repository": "synthetic/example",
                "commit": "a" * 40,
                "source_sha256": "b" * 64,
                "language": "python",
                "scope": "changed lines",
                "label_provenance": "synthetic test label",
                "supported": True,
                "labels": [loc],
                "findings": [copy.deepcopy(loc)],
            }
        ],
    }


def test_one_to_one_matching_and_digest_stability():
    sample = data()
    result = evaluate(sample)
    assert (result["tp"], result["fp"], result["fn"]) == (1, 0, 0)
    assert (
        result["severity_agreement"] == 1 and result["independence"] == "not independently verified"
    )
    assert result["dataset_sha256"] == evaluate(copy.deepcopy(sample))["dataset_sha256"]


def test_duplicate_is_not_counted_as_second_true_positive():
    sample = data()
    sample["cases"][0]["findings"].append(copy.deepcopy(sample["cases"][0]["findings"][0]))
    result = evaluate(sample)
    assert (result["tp"], result["fp"], result["duplicate_findings"]) == (1, 1, 1)


def test_unsupported_is_separate_and_cannot_have_findings():
    sample = data()
    sample["cases"][0]["supported"] = False
    with pytest.raises(ValueError, match="unsupported"):
        evaluate(sample)
    sample["cases"][0]["findings"] = []
    result = evaluate(sample)
    assert result["unsupported_cases"] == 1 and result["recall_on_supported_cases"] is None


def test_mismatch_counts_fp_fn_and_severity_is_separate():
    sample = data()
    sample["cases"][0]["findings"][0]["start"] = 6
    sample["cases"][0]["findings"][0]["end"] = 6
    result = evaluate(sample)
    assert (result["tp"], result["fp"], result["fn"]) == (0, 1, 1)
    sample = data()
    sample["cases"][0]["findings"][0]["severity"] = "HIGH"
    assert evaluate(sample)["severity_agreement"] == 0


def test_invalid_identity_duplicate_case_and_extra_source_rejected():
    sample = data()
    sample["cases"][0]["source_sha256"] = "bad"
    with pytest.raises(ValueError):
        evaluate(sample)
    sample = data()
    sample["cases"].append(copy.deepcopy(sample["cases"][0]))
    with pytest.raises(ValueError):
        evaluate(sample)
    sample = data()
    sample["cases"][0]["source"] = "not allowed"
    with pytest.raises(ValueError):
        evaluate(sample)


def test_negative_case_false_positive_rate_is_case_based():
    sample = data()
    sample["cases"][0]["labels"] = []
    result = evaluate(sample)
    assert result["negative_cases"] == 1
    assert result["negative_cases_with_findings"] == 1
    assert result["false_positive_case_rate"] == 1


def test_per_rule_scores_and_duplicate_denominator():
    sample = data()
    sample["cases"][0]["findings"].append(copy.deepcopy(sample["cases"][0]["findings"][0]))
    result = evaluate(sample)
    assert result["per_rule"]["RULE-1"] == {"tp": 1, "fp": 1, "fn": 0, "precision": .5, "recall": 1}
    assert result["finding_count"] == 2 and result["duplicate_rate"] == .5
    assert result["supported_case_fraction"] == 1
    assert result["independence"] == "not independently verified"


def test_candidate_packet_integrity_and_unlabeled_provenance():
    from hashlib import sha256
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "evaluation/fixtures/alpha-review-candidates-v1"
    raw = (root / "manifest.json").read_bytes()
    assert (root / "manifest.sha256").read_text().split()[0] == sha256(raw).hexdigest()
    manifest = json.loads(raw)
    assert manifest["count"] == len(manifest["cases"]) == 20
    assert manifest["independent_human_labels"] == 0
    assert len({case["id"] for case in manifest["cases"]}) == 20
    original = [case for case in manifest["cases"] if "source_file" in case]
    public = [case for case in manifest["cases"] if "repository" in case]
    assert len(original) == 16 and len(public) == 4
    assert {case["language"] for case in original} == {"python", "typescript", "tsx"}
    for case in original:
        assert sha256((root / case["source_file"]).read_bytes()).hexdigest() == case["source_sha256"]
    assert all("requires independent adjudication" in case["expected"] for case in manifest["cases"])


def test_offline_reviewer_packet_contains_no_prediction_labels():
    from hashlib import sha256
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "evaluation/fixtures/alpha-review-candidates-v1"
    html = (root / "reviewer.html").read_text()
    assert sha256((root / "manifest.json").read_bytes()).hexdigest() in html
    assert "TS-EVAL-001" not in html and "PY-SHELL-001" not in html
    assert "connect-src 'none'" in html
    assert "not an independent benchmark" in html


def test_wilson_uncertainty_intervals_include_estimate():
    result = evaluate(data())
    low, high = result["precision_wilson_95"]
    assert 0 < low < result["precision"] <= high <= 1
    assert result["false_positive_case_rate_wilson_95"] is None
