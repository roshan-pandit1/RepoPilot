"""Offline validation for human judgments of a *partial* source inventory.

This module neither creates judgments nor proves the identity or independence
of their authors. It does not perform retrieval, execute source, or access Git.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from app.evaluation.issue_context_schema import IssueContext, StrictModel, context_digest

SHA1 = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Reviewer = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Explanation = Annotated[str, Field(min_length=1, max_length=2000)]
Grade = Annotated[int, Field(ge=0, le=3)] | Literal["UNJUDGED"]
WARNING = "Partial source selection; not a complete repository or full-repository relevance judgment."


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("blank_text")
    return value


def _stamp(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("invalid_utc_timestamp")
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return value


def _path(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or len(value) > 240 or "\\" in value or "\x00" in value
            or path.is_absolute() or str(path) != value
            or any(part in {".", ".."} for part in path.parts)):
        raise ValueError("invalid_source_path")
    return value


def canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


class SourceFile(StrictModel):
    path: str
    git_blob_sha1: SHA1
    sha256: SHA256
    size_bytes: int = Field(ge=0, le=100_000)
    line_count: int = Field(ge=1, le=100_000)

    _safe_path = field_validator("path")(_path)


class PartialInventory(StrictModel):
    version: Literal["human-review-inventory-v1"]
    repository: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", max_length=250)]
    commit: SHA1
    root_tree: SHA1
    source_complete: Literal[False]
    files: list[SourceFile] = Field(min_length=1, max_length=10)

    @field_validator("repository")
    @classmethod
    def repository_namespace(cls, value):
        if any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("invalid_repository_namespace")
        return value

    @model_validator(mode="after")
    def ordered_unique(self):
        paths = [file.path for file in self.files]
        if self.source_complete is not False or paths != sorted(set(paths)):
            raise ValueError("invalid_partial_inventory")
        return self


def inventory_digest(inventory: PartialInventory) -> str:
    return hashlib.sha256(canonical(inventory.model_dump(mode="json"))).hexdigest()


def verify_sources(inventory: PartialInventory, sources: dict[str, bytes]) -> None:
    """Rehash supplied inert bytes, including Git's blob header; never parse Go."""
    if set(sources) != {file.path for file in inventory.files}:
        raise ValueError("missing_or_unexpected_source")
    for file in inventory.files:
        raw = sources[file.path]
        if not isinstance(raw, bytes):
            raise ValueError("invalid_source_bytes")
        try:
            text = raw.decode("utf-8")
        except UnicodeError:
            raise ValueError("invalid_source_encoding") from None
        blob = hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()
        line_count = len(raw.split(b"\n")) - int(raw.endswith(b"\n")) if raw else 0
        if (b"\0" in raw or "\r" in text or len(raw) != file.size_bytes
                or line_count != file.line_count
                or hashlib.sha256(raw).hexdigest() != file.sha256 or blob != file.git_blob_sha1):
            raise ValueError("source_identity_mismatch")


class RangeJudgment(StrictModel):
    path: str
    git_blob_sha1: SHA1
    file_sha256: SHA256
    start_line: int = Field(ge=1, le=100_000)
    end_line: int = Field(ge=1, le=100_000)
    grade: Grade
    rationale: Explanation
    uncertainty: Explanation

    _safe_path = field_validator("path")(_path)
    _text = field_validator("rationale", "uncertainty")(_nonblank)


class HumanReview(StrictModel):
    version: Literal["human-relevance-review-v1"]
    rubric_version: Literal["source-relevance-v1"]
    repository: str
    issue_id: int = Field(gt=0)
    issue_number: int = Field(gt=0)
    issue_context_sha256: SHA256
    commit: SHA1
    root_tree: SHA1
    source_inventory_sha256: SHA256
    dataset_split: Literal["pilot_development"]
    label_scope: Literal["partial_source_subset"]
    source_complete: Literal[False]
    source_completeness_warning: Literal[WARNING]
    reviewer_kind: Literal["HUMAN"]
    reviewer_id: Reviewer
    reviewed_at_utc: str
    independence: Literal["DECLARED_BLIND_INDEPENDENT", "SINGLE_REVIEWER_EXPLORATORY"]
    adjudication_status: Literal["NOT_ADJUDICATED", "SINGLE_REVIEWER_EXPLORATORY"]
    outcome: Literal["JUDGED", "UNJUDGED", "INSUFFICIENT_EVIDENCE", "OUTSIDE_RETAINED_CORPUS"]
    issue_evidence_sufficiency: Literal["SUFFICIENT", "INSUFFICIENT", "UNCERTAIN"]
    source_sufficiency: Literal["SUFFICIENT_FOR_SELECTED_RANGES", "MISSING_SOURCE", "UNCERTAIN"]
    missing_source: list[Explanation] = Field(max_length=20)
    uncertainty: Explanation
    abstention_reason: Explanation | None
    labels: list[RangeJudgment] = Field(max_length=200)

    _timestamp = field_validator("reviewed_at_utc")(_stamp)
    _text = field_validator("uncertainty")(_nonblank)

    @model_validator(mode="after")
    def status_consistency(self):
        if self.source_complete is not False:
            raise ValueError("partial_warning_required")
        if ((self.independence == "DECLARED_BLIND_INDEPENDENT") !=
                (self.adjudication_status == "NOT_ADJUDICATED")):
            raise ValueError("conflicting_review_status")
        if self.source_sufficiency == "MISSING_SOURCE" and not self.missing_source:
            raise ValueError("missing_source_details_required")
        for entry in self.missing_source:
            _nonblank(entry)
        graded = [item for item in self.labels if type(item.grade) is int]
        if self.outcome == "JUDGED":
            if not graded or self.abstention_reason is not None:
                raise ValueError("invalid_judged_outcome")
        elif graded or self.abstention_reason is None or not self.abstention_reason.strip():
            raise ValueError("invalid_abstention")
        return self


def validate_review(payload: dict, inventory: PartialInventory, sources: dict[str, bytes],
                    issue: IssueContext) -> HumanReview:
    """Bind a submitted, self-attested human review to verified local bytes."""
    verify_sources(inventory, sources)
    review = HumanReview.model_validate(payload)
    if ((review.repository, review.commit, review.root_tree, review.source_inventory_sha256)
            != (inventory.repository, inventory.commit, inventory.root_tree, inventory_digest(inventory))
            or (review.issue_id, review.issue_number, review.issue_context_sha256)
            != (issue.issue_id, issue.number, context_digest(issue))):
        raise ValueError("review_identity_mismatch")
    files = {file.path: file for file in inventory.files}
    seen = set()
    for label in review.labels:
        file = files.get(label.path)
        identity = (label.path, label.start_line, label.end_line)
        if (not file or label.git_blob_sha1 != file.git_blob_sha1 or label.file_sha256 != file.sha256
                or label.end_line < label.start_line or label.end_line > file.line_count or identity in seen):
            raise ValueError("invalid_review_range_or_identity")
        seen.add(identity)
    return review


def review_digest(review: HumanReview) -> str:
    return hashlib.sha256(canonical(review.model_dump(mode="json"))).hexdigest()


class Adjudication(StrictModel):
    version: Literal["human-relevance-adjudication-v1"]
    status: Literal["ADJUDICATED", "UNRESOLVED", "SINGLE_REVIEWER_EXPLORATORY"]
    repository: str
    issue_id: int = Field(gt=0)
    issue_number: int = Field(gt=0)
    issue_context_sha256: SHA256
    commit: SHA1
    root_tree: SHA1
    source_inventory_sha256: SHA256
    dataset_split: Literal["pilot_development"]
    label_scope: Literal["partial_source_subset"]
    source_complete: Literal[False]
    source_completeness_warning: Literal[WARNING]
    submission_sha256s: list[SHA256] = Field(min_length=1, max_length=10)
    adjudicator_kind: Literal["HUMAN"] | None
    adjudicator_id: Reviewer | None
    decided_at_utc: str
    resolution_note: Explanation
    outcome: Literal["JUDGED", "UNJUDGED", "INSUFFICIENT_EVIDENCE", "OUTSIDE_RETAINED_CORPUS"]
    labels: list[RangeJudgment] = Field(max_length=200)

    _timestamp = field_validator("decided_at_utc")(_stamp)
    _text = field_validator("resolution_note")(_nonblank)


def validate_adjudication(payload: dict, reviews: list[HumanReview], inventory: PartialInventory,
                          sources: dict[str, bytes], issue: IssueContext) -> Adjudication:
    """Check references and ranges; no status authenticates a person's identity."""
    checked = [validate_review(r.model_dump(mode="json"), inventory, sources, issue) for r in reviews]
    result = Adjudication.model_validate(payload)
    hashes = [review_digest(r) for r in checked]
    ids = [r.reviewer_id for r in checked]
    if ((result.repository, result.commit, result.root_tree, result.source_inventory_sha256,
         result.issue_id, result.issue_number, result.issue_context_sha256)
            != (inventory.repository, inventory.commit, inventory.root_tree, inventory_digest(inventory),
                issue.issue_id, issue.number, context_digest(issue)) or result.source_complete is not False
            or len(set(ids)) != len(ids) or len(set(hashes)) != len(hashes)
            or result.submission_sha256s != sorted(hashes)
            or any(r.reviewed_at_utc > result.decided_at_utc for r in checked)):
        raise ValueError("invalid_adjudication_references")
    if result.status == "SINGLE_REVIEWER_EXPLORATORY":
        if (len(checked) != 1 or result.adjudicator_id is not None or result.adjudicator_kind is not None or result.labels
                or result.outcome != "UNJUDGED"):
            raise ValueError("invalid_single_reviewer_status")
    elif result.status == "ADJUDICATED":
        if (len(checked) < 2 or result.adjudicator_kind != "HUMAN" or not result.adjudicator_id
                or result.adjudicator_id in ids
                or any(r.independence != "DECLARED_BLIND_INDEPENDENT" for r in checked)):
            raise ValueError("independent_adjudication_requirements")
    elif (result.adjudicator_kind != "HUMAN" or not result.adjudicator_id or result.adjudicator_id in ids or result.labels
          or result.outcome != "UNJUDGED"):
        raise ValueError("invalid_unresolved_adjudication")
    graded = [item for item in result.labels if type(item.grade) is int]
    if result.status == "ADJUDICATED" and ((result.outcome == "JUDGED") != bool(graded)):
        raise ValueError("invalid_adjudicated_outcome")
    # Validate human-supplied adjudication ranges using the same inventory checks.
    if result.labels:
        sample = checked[0].model_dump(mode="json")
        sample.update(labels=[v.model_dump(mode="json") for v in result.labels],
                      outcome="JUDGED" if graded else "UNJUDGED",
                      abstention_reason=None if graded else "Unjudged adjudication ranges.")
        validate_review(sample, inventory, sources, issue)
    return result
