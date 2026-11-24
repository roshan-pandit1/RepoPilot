"""Human annotation validation uses original synthetic data only."""
import copy
import hashlib
import json
import socket
import subprocess

import pytest
from pydantic import ValidationError

from app.evaluation.human_relevance import (
    WARNING,
    PartialInventory,
    canonical,
    inventory_digest,
    review_digest,
    validate_adjudication,
    validate_review,
    verify_sources,
)
from app.evaluation.issue_context_schema import IssueContext, context_digest
from evaluation import prepare_chi_1188_review as packet
from evaluation.validate_human_review import read_private_json


@pytest.fixture
def sample():
    sources = {"router.go": b"package fixture\nfunc Route() {}\n", "util.go": b"package fixture\n"}
    entries = [{"path": path, "git_blob_sha1": hashlib.sha1(
        f"blob {len(raw)}\0".encode() + raw).hexdigest(), "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw), "line_count": len(raw.decode().splitlines())}
        for path, raw in sorted(sources.items())]
    inventory = PartialInventory.model_validate({"version": "human-review-inventory-v1",
        "repository": "fixture/repo", "commit": "a" * 40, "root_tree": "b" * 40,
        "source_complete": False, "files": entries})
    issue = IssueContext.model_validate({"version": "issue-context-v1", "issue_id": 101, "number": 7,
        "state": "open", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z",
        "title": "Synthetic behavior", "body": "A synthetic report.", "labels": [],
        "comment_count": 0, "comments": []})
    label = {"path": "router.go", "git_blob_sha1": entries[0]["git_blob_sha1"],
             "file_sha256": entries[0]["sha256"], "start_line": 1, "end_line": 2,
             "grade": 2, "rationale": "Synthetic rationale.", "uncertainty": "Unknown alternatives."}
    record = {"version": "human-relevance-review-v1", "rubric_version": "source-relevance-v1",
        "repository": "fixture/repo", "issue_id": 101, "issue_number": 7,
        "issue_context_sha256": context_digest(issue), "commit": "a" * 40, "root_tree": "b" * 40,
        "source_inventory_sha256": inventory_digest(inventory), "dataset_split": "pilot_development",
        "label_scope": "partial_source_subset", "source_complete": False,
        "source_completeness_warning": WARNING, "reviewer_kind": "HUMAN", "reviewer_id": "reviewer_a",
        "reviewed_at_utc": "2026-02-01T12:00:00Z", "independence": "DECLARED_BLIND_INDEPENDENT",
        "adjudication_status": "NOT_ADJUDICATED", "outcome": "JUDGED", "issue_evidence_sufficiency": "SUFFICIENT",
        "source_sufficiency": "UNCERTAIN", "missing_source": [], "uncertainty": "Partial inventory.",
        "abstention_reason": None, "labels": [label]}
    return inventory, sources, issue, record


def validate(sample, record):
    return validate_review(record, sample[0], sample[1], sample[2])


def bind_adjudication(data, sample):
    for field in ("repository", "issue_id", "issue_number", "issue_context_sha256", "commit", "root_tree",
                  "source_inventory_sha256", "dataset_split", "label_scope", "source_complete",
                  "source_completeness_warning"):
        data[field] = sample[3][field]
    return data


def test_valid_review_and_deterministic_canonical_form(sample):
    record = sample[3]
    first = validate(sample, record)
    assert review_digest(first) == review_digest(validate(sample, dict(reversed(list(record.items())))))
    assert canonical(first.model_dump(mode="json")) == canonical(validate(sample, copy.deepcopy(record)).model_dump(mode="json"))


@pytest.mark.parametrize("grade", [0, 1, 2, 3])
def test_existing_relevance_scale_accepts_each_explicit_grade(sample, grade):
    record = copy.deepcopy(sample[3])
    record["labels"][0]["grade"] = grade
    assert validate(sample, record).labels[0].grade == grade


def test_missing_reviewer_field_is_rejected(sample):
    record = copy.deepcopy(sample[3])
    del record["reviewer_id"]
    with pytest.raises(ValidationError):
        validate(sample, record)


@pytest.mark.parametrize("field,value", [
    ("reviewer_id", ""), ("reviewer_kind", "AI"), ("reviewed_at_utc", "2026-02-99T12:00:00Z"),
    ("source_complete", True), ("source_completeness_warning", ""), ("dataset_split", "held_out"),
    ("commit", "c" * 40), ("root_tree", "c" * 40), ("issue_context_sha256", "0" * 64),
    ("source_inventory_sha256", "0" * 64), ("issue_number", 8),
    ("independence", "DECLARED_BLIND_INDEPENDENT"),
])
def test_reject_invalid_identity_and_status(sample, field, value):
    record = copy.deepcopy(sample[3])
    if field == "independence":
        record["adjudication_status"] = "SINGLE_REVIEWER_EXPLORATORY"
    record[field] = value
    with pytest.raises((ValueError, ValidationError)):
        validate(sample, record)


@pytest.mark.parametrize("grade", [-1, 4, True, "3", "INSUFFICIENT_EVIDENCE"])
def test_reject_invalid_grade(sample, grade):
    record = copy.deepcopy(sample[3])
    record["labels"][0]["grade"] = grade
    with pytest.raises((ValueError, ValidationError)):
        validate(sample, record)


@pytest.mark.parametrize("field,value", [
    ("start_line", 0), ("end_line", 3), ("start_line", 3), ("git_blob_sha1", "0" * 40),
    ("file_sha256", "0" * 64), ("path", "../router.go"), ("path", "missing.go"),
    ("rationale", "   "),
])
def test_reject_bad_range_or_source_identity(sample, field, value):
    record = copy.deepcopy(sample[3])
    record["labels"][0][field] = value
    with pytest.raises((ValueError, ValidationError)):
        validate(sample, record)


def test_duplicate_labels_are_rejected(sample):
    record = copy.deepcopy(sample[3])
    record["labels"].append(copy.deepcopy(record["labels"][0]))
    with pytest.raises(ValueError, match="invalid_review_range_or_identity"):
        validate(sample, record)


@pytest.mark.parametrize("outcome", ["UNJUDGED", "INSUFFICIENT_EVIDENCE", "OUTSIDE_RETAINED_CORPUS"])
def test_abstention_is_allowed_and_never_becomes_zero(sample, outcome):
    record = copy.deepcopy(sample[3])
    record.update(outcome=outcome, labels=[], abstention_reason="Not enough evidence.")
    assert validate(sample, record).labels == []
    record["labels"] = [copy.deepcopy(sample[3]["labels"][0])]
    with pytest.raises(ValueError, match="invalid_abstention"):
        validate(sample, record)


def test_explicit_unjudged_range_is_not_a_negative(sample):
    record = copy.deepcopy(sample[3])
    record["labels"][0]["grade"] = "UNJUDGED"
    record.update(outcome="UNJUDGED", abstention_reason="Uncertain range.")
    assert validate(sample, record).labels[0].grade == "UNJUDGED"


def test_missing_source_requires_explanation_and_is_not_a_zero(sample):
    record = copy.deepcopy(sample[3])
    record["source_sufficiency"] = "MISSING_SOURCE"
    with pytest.raises(ValueError, match="missing_source_details_required"):
        validate(sample, record)
    record["missing_source"] = ["The synthetic example may depend on another file."]
    assert validate(sample, record).source_sufficiency == "MISSING_SOURCE"


def test_missing_or_modified_inventory_sources_fail_closed(sample):
    inventory, sources, _, _ = sample
    with pytest.raises(ValueError, match="missing_or_unexpected_source"):
        verify_sources(inventory, {"router.go": sources["router.go"]})
    changed = dict(sources)
    changed["router.go"] += b"x"
    with pytest.raises(ValueError, match="source_identity_mismatch"):
        verify_sources(inventory, changed)


def test_single_reviewer_cannot_claim_adjudication(sample):
    first = validate(sample, sample[3])
    adjudication = {"version": "human-relevance-adjudication-v1", "status": "ADJUDICATED",
        "submission_sha256s": [review_digest(first)], "adjudicator_kind": "HUMAN", "adjudicator_id": "reviewer_c",
        "decided_at_utc": "2026-02-02T12:00:00Z", "resolution_note": "Synthetic test.",
        "outcome": "JUDGED", "labels": sample[3]["labels"]}
    bind_adjudication(adjudication, sample)
    with pytest.raises(ValueError, match="independent_adjudication_requirements"):
        validate_adjudication(adjudication, [first], *sample[:3])
    adjudication.update(status="SINGLE_REVIEWER_EXPLORATORY", adjudicator_kind=None,
                        adjudicator_id=None, outcome="UNJUDGED", labels=[])
    assert validate_adjudication(adjudication, [first], *sample[:3]).status == "SINGLE_REVIEWER_EXPLORATORY"


def test_single_reviewer_submission_remains_exploratory(sample):
    record = copy.deepcopy(sample[3])
    record.update(independence="SINGLE_REVIEWER_EXPLORATORY", adjudication_status="SINGLE_REVIEWER_EXPLORATORY")
    assert validate(sample, record).adjudication_status == "SINGLE_REVIEWER_EXPLORATORY"


def test_two_blind_submissions_require_separate_adjudicator(sample):
    first = validate(sample, sample[3])
    other = copy.deepcopy(sample[3])
    other["reviewer_id"] = "reviewer_b"
    second = validate(sample, other)
    data = {"version": "human-relevance-adjudication-v1", "status": "ADJUDICATED",
        "submission_sha256s": sorted([review_digest(first), review_digest(second)]),
        "adjudicator_kind": "HUMAN", "adjudicator_id": "reviewer_c", "decided_at_utc": "2026-02-02T12:00:00Z",
        "resolution_note": "Synthetic comparison.", "outcome": "JUDGED", "labels": sample[3]["labels"]}
    bind_adjudication(data, sample)
    assert validate_adjudication(data, [first, second], *sample[:3]).status == "ADJUDICATED"
    invalid_warning = dict(data, source_completeness_warning="")
    with pytest.raises(ValidationError):
        validate_adjudication(invalid_warning, [first, second], *sample[:3])
    invalid_adjudicator_kind = dict(data, adjudicator_kind="AI")
    with pytest.raises(ValidationError):
        validate_adjudication(invalid_adjudicator_kind, [first, second], *sample[:3])
    invalid_outcome = dict(data, labels=[])
    with pytest.raises(ValueError, match="invalid_adjudicated_outcome"):
        validate_adjudication(invalid_outcome, [first, second], *sample[:3])
    invalid_commit = dict(data, commit="c" * 40)
    with pytest.raises(ValueError, match="invalid_adjudication_references"):
        validate_adjudication(invalid_commit, [first, second], *sample[:3])
    data["adjudicator_id"] = "reviewer_a"
    with pytest.raises(ValueError, match="independent_adjudication_requirements"):
        validate_adjudication(data, [first, second], *sample[:3])


def test_adjudication_cannot_use_a_single_reviewer_claimed_as_two(sample):
    first = validate(sample, sample[3])
    duplicate = copy.deepcopy(sample[3])
    duplicate["uncertainty"] = "Different text."
    second = validate(sample, duplicate)
    data = {"version": "human-relevance-adjudication-v1", "status": "ADJUDICATED",
        "submission_sha256s": sorted([review_digest(first), review_digest(second)]),
        "adjudicator_kind": "HUMAN", "adjudicator_id": "reviewer_c", "decided_at_utc": "2026-02-02T12:00:00Z",
        "resolution_note": "Synthetic comparison.", "outcome": "JUDGED", "labels": sample[3]["labels"]}
    bind_adjudication(data, sample)
    with pytest.raises(ValueError, match="invalid_adjudication_references"):
        validate_adjudication(data, [first, second], *sample[:3])


def test_blind_packet_contains_only_synthetic_context_and_blank_judgments(sample, tmp_path, monkeypatch):
    inventory, sources, issue, _ = sample
    issue_data = issue.model_dump(mode="json")
    issue_data.update({"comment_count": 1, "comments": [{"id": 3,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "body": "WITHHELD_SYNTHETIC_COMMENT"}]})
    issue = IssueContext.model_validate(issue_data)
    monkeypatch.setattr(packet, "load_chi", lambda *_args: pytest.fail("real source was accessed"))
    monkeypatch.setattr(socket, "socket", lambda *_a, **_k: pytest.fail("network access attempted"))
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: pytest.fail("subprocess attempted"))
    target = packet.write_packet(tmp_path, issue, inventory, sources)
    assert not (target / "INCOMPLETE").exists()
    assert target.stat().st_mode & 0o777 == 0o700
    left, right = target / "reviewer-a", target / "reviewer-b"
    for directory in (left, right, left / "source", right / "source"):
        assert directory.stat().st_mode & 0o777 == 0o700
    for file in left.rglob("*"):
        if file.is_file():
            assert file.stat().st_mode & 0o777 == 0o600
            assert file.read_bytes() == (right / file.relative_to(left)).read_bytes()
            assert b"WITHHELD_SYNTHETIC_COMMENT" not in file.read_bytes()
    assert "Synthetic behavior" in (left / "issue.txt").read_text()
    assert (left / "source/router.go.txt").read_text().splitlines() == [
        "00001 | package fixture", "00002 | func Route() {}"]
    template = json.loads((left / "annotation-template.json").read_text())
    assert template["labels"] == [] and template["reviewer_id"] is None and template["source_complete"] is False
    with pytest.raises((ValueError, ValidationError)):
        validate(sample, template)


def test_packet_rejects_missing_source_before_creating_anything(sample, tmp_path):
    inventory, sources, issue, _ = sample
    del sources["router.go"]
    with pytest.raises(ValueError, match="missing_or_unexpected_source"):
        packet.write_packet(tmp_path, issue, inventory, sources)
    assert list(tmp_path.iterdir()) == []


def test_control_characters_are_rendered_as_text():
    assert packet._safe_display("a\x1bb\u202ec") == "a\\u001bb\\u202ec"


def test_private_submission_file_guards(tmp_path):
    folder = tmp_path / "reviewer"
    folder.mkdir(mode=0o700)
    submission = folder / "response.json"
    submission.write_text('{"a":1}')
    submission.chmod(0o600)
    assert read_private_json(submission, tmp_path) == {"a": 1}
    submission.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError, match="duplicate_json_key"):
        read_private_json(submission, tmp_path)
    submission.write_text('{"a":1}')
    submission.chmod(0o644)
    with pytest.raises(ValueError, match="invalid_private_submission"):
        read_private_json(submission, tmp_path)
    submission.chmod(0o600)
    link = folder / "link.json"
    link.symlink_to(submission)
    with pytest.raises(ValueError, match="invalid_private_submission"):
        read_private_json(link, tmp_path)
