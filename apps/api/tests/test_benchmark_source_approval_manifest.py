"""Offline schema checks for the unapproved source-selection manifest."""
import copy
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

MANIFEST = Path(__file__).resolve().parents[1] / "evaluation/benchmark-source-approval-v1.json"
NOT_APPROVED = Literal["NOT_APPROVED"]
SHA = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
REPOSITORY = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}$")]
SECRET_PATTERNS = (
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Permissions(Strict):
    git_objects_and_source_trees: NOT_APPROVED
    source_files: NOT_APPROVED
    issue_bodies: NOT_APPROVED
    issue_comments: NOT_APPROVED
    patches_and_pr_diffs: NOT_APPROVED
    store_source: NOT_APPROVED
    store_issue_context: NOT_APPROVED
    source_embeddings: NOT_APPROVED
    local_coderankembed_inference: NOT_APPROVED
    real_benchmark_execution: NOT_APPROVED
    external_source_transmission: NOT_APPROVED
    github_writes: NOT_APPROVED


class Limits(Strict):
    repositories: int = Field(ge=1, le=3)
    snapshots: int = Field(ge=1, le=3)
    issues: int = Field(ge=1, le=10)
    source_download_bytes_per_repository: int = Field(ge=1, le=104857600)
    aggregate_source_download_bytes: int = Field(ge=1, le=314572800)
    aggregate_issue_context_download_bytes: int = Field(ge=1, le=10485760)
    eligible_file_bytes: int = Field(ge=1, le=100000)
    eligible_source_bytes_per_snapshot: int = Field(ge=1, le=5000000)
    issue_body_characters: int = Field(ge=1, le=10000)
    comments_per_issue: int = Field(ge=0, le=30)
    characters_per_comment: int = Field(ge=1, le=2000)


class Retention(Strict):
    status: NOT_APPROVED
    directory: Literal["/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1"]
    directory_mode: Literal["0700"]
    file_mode: Literal["0600"]
    maximum_days: int = Field(ge=1, le=30)
    external_upload: NOT_APPROVED


class Dataset(Strict):
    pilot_candidates: int = Field(ge=1, le=10)
    approved_issues: int = Field(ge=0, le=0)
    independently_labeled_issues: int = Field(ge=0, le=0)
    heldout_candidates: int = Field(ge=0, le=0)


class Issue(Strict):
    number: int = Field(ge=1, lt=2**31)
    url: str = Field(max_length=300)
    title_cue: str = Field(min_length=1, max_length=250)
    created_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    observed_state: Literal["open", "closed"]
    visible_labels: list[str] = Field(max_length=20)
    labels_status: Literal["NOT_VERIFIED", "PARTIAL_LISTING_ONLY"]
    category: Literal["symbol", "exception", "behavior", "ambiguous"]
    split: Literal["pilot_candidate"]
    source_relationship: Literal["UNVERIFIED"]
    relevance_labels: Literal["NOT_CREATED"]

    @model_validator(mode="after")
    def check_issue(self):
        date.fromisoformat(self.created_date)
        if (self.labels_status == "NOT_VERIFIED") != (not self.visible_labels):
            raise ValueError("invalid_label_observation")
        return self


class Repository(Strict):
    repository: REPOSITORY
    repository_id: int = Field(ge=1, lt=2**63)
    url: str = Field(max_length=250)
    public: bool
    archived: bool
    primary_language: Literal["Python", "JavaScript", "TypeScript", "Java", "Go"]
    github_size_kb: int = Field(ge=1)
    github_open_issues_and_prs: int = Field(ge=0)
    default_branch: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    license_spdx: Literal["MIT", "BSD-3-Clause"]
    license_path: Literal["LICENSE", "LICENSE.md"]
    license_url: str = Field(max_length=400)
    commit_sha: SHA
    commit_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    commit_cutoff: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    commit_url: str = Field(max_length=300)
    metadata_url: str = Field(max_length=300)
    commit_metadata_url: str = Field(max_length=500)
    issues_list_url: str = Field(max_length=300)
    decision: NOT_APPROVED
    issues: list[Issue] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def check_links_and_chronology(self):
        root = f"https://github.com/{self.repository}"
        api = f"https://api.github.com/repos/{self.repository}"
        if (not self.public or self.archived or ".." in self.repository.split("/")[1]
                or self.url != root or self.metadata_url != api
                or self.issues_list_url != root + "/issues"
                or self.commit_url != root + "/commit/" + self.commit_sha
                or self.license_url != root + "/blob/" + self.commit_sha + "/" + self.license_path
                or self.commit_metadata_url != f"{api}/commits?sha={self.default_branch}"
                    f"&until={quote(self.commit_cutoff, safe='')}&per_page=1"):
            raise ValueError("invalid_source_urls")
        commit_date = datetime.strptime(self.commit_date, "%Y-%m-%dT%H:%M:%SZ")
        cutoff = datetime.strptime(self.commit_cutoff, "%Y-%m-%dT%H:%M:%SZ")
        if commit_date > cutoff:
            raise ValueError("commit_after_cutoff")
        numbers = [issue.number for issue in self.issues]
        if len(numbers) != len(set(numbers)) or numbers != sorted(numbers):
            raise ValueError("duplicate_or_unordered_issues")
        for issue in self.issues:
            if issue.url != f"{root}/issues/{issue.number}" or cutoff.date() >= date.fromisoformat(issue.created_date):
                raise ValueError("invalid_issue_url_or_cutoff")
        return self


class Manifest(Strict):
    version: Literal["benchmark-source-approval-v1"]
    status: NOT_APPROVED
    metadata_observed_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    intent: Literal["source-selection-only"]
    dataset: Dataset
    future_permissions: Permissions
    proposed_limits: Limits
    proposed_retention: Retention
    repositories: list[Repository] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def check_manifest(self):
        date.fromisoformat(self.metadata_observed_date)
        names = [repo.repository for repo in self.repositories]
        ids = [repo.repository_id for repo in self.repositories]
        issues = [(repo.repository, issue.number) for repo in self.repositories for issue in repo.issues]
        if (names != sorted(names) or len(set(names)) != len(names) or len(set(ids)) != len(ids)
                or len(set(issues)) != len(issues) or len(issues) != self.dataset.pilot_candidates
                or len(names) > self.proposed_limits.repositories or len(names) > self.proposed_limits.snapshots
                or len(issues) > self.proposed_limits.issues):
            raise ValueError("invalid_inventory_or_limits")
        encoded = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=True)
        if any(pattern.search(encoded) for pattern in SECRET_PATTERNS):
            raise ValueError("potential_secret")
        return self


@pytest.fixture
def synthetic_manifest():
    sha = "a" * 40
    name, cutoff = "fixture/example", "2025-01-01T23:59:59Z"
    root, api = f"https://github.com/{name}", f"https://api.github.com/repos/{name}"
    not_approved = "NOT_APPROVED"
    return {"version": "benchmark-source-approval-v1", "status": not_approved,
        "metadata_observed_date": "2026-11-07", "intent": "source-selection-only",
        "dataset": {"pilot_candidates": 1, "approved_issues": 0, "independently_labeled_issues": 0,
                    "heldout_candidates": 0},
        "future_permissions": {key: not_approved for key in Permissions.model_fields},
        "proposed_limits": {"repositories": 3, "snapshots": 3, "issues": 10,
            "source_download_bytes_per_repository": 104857600, "aggregate_source_download_bytes": 314572800,
            "aggregate_issue_context_download_bytes": 10485760, "eligible_file_bytes": 100000,
            "eligible_source_bytes_per_snapshot": 5000000, "issue_body_characters": 10000,
            "comments_per_issue": 30, "characters_per_comment": 2000},
        "proposed_retention": {"status": not_approved,
            "directory": "/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1",
            "directory_mode": "0700", "file_mode": "0600", "maximum_days": 30, "external_upload": not_approved},
        "repositories": [{"repository": name, "repository_id": 123, "url": root, "public": True,
            "archived": False, "primary_language": "Python", "github_size_kb": 1,
            "github_open_issues_and_prs": 1, "default_branch": "main", "license_spdx": "MIT",
            "license_path": "LICENSE", "license_url": f"{root}/blob/{sha}/LICENSE", "commit_sha": sha,
            "commit_date": "2025-01-01T12:00:00Z", "commit_cutoff": cutoff,
            "commit_url": f"{root}/commit/{sha}", "metadata_url": api,
            "commit_metadata_url": f"{api}/commits?sha=main&until={quote(cutoff, safe='')}&per_page=1",
            "issues_list_url": root + "/issues", "decision": not_approved,
            "issues": [{"number": 1, "url": root + "/issues/1", "title_cue": "Synthetic issue",
                "created_date": "2025-01-02", "observed_state": "open", "visible_labels": [],
                "labels_status": "NOT_VERIFIED", "category": "behavior", "split": "pilot_candidate",
                "source_relationship": "UNVERIFIED", "relevance_labels": "NOT_CREATED"}]}]}


def test_actual_manifest_schema_and_canonical_output():
    raw = MANIFEST.read_text(encoding="utf-8")
    data = json.loads(raw)
    manifest = Manifest.model_validate(data)
    assert len(manifest.repositories) == 3
    assert manifest.dataset.pilot_candidates == 10
    assert raw == json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    assert manifest.model_dump(mode="json") == data


def test_synthetic_manifest_passes(synthetic_manifest):
    assert Manifest.model_validate(synthetic_manifest).dataset.pilot_candidates == 1


@pytest.mark.parametrize("mutation", ["approval", "repo", "sha", "license", "issue_duplicate", "issue_url",
    "heldout", "labels", "cutoff", "secret", "issue_body", "limit", "source_relationship", "retention",
    "bool_coercion", "integer_coercion"])
def test_synthetic_manifest_rejects_unsafe_or_inconsistent_records(synthetic_manifest, mutation):
    data = copy.deepcopy(synthetic_manifest)
    repo, issue = data["repositories"][0], data["repositories"][0]["issues"][0]
    if mutation == "approval":
        data["future_permissions"]["source_embeddings"] = "APPROVED"
    elif mutation == "repo":
        repo["repository"] = "../foreign/repo"
    elif mutation == "sha":
        repo["commit_sha"] = "not-a-git-sha"
    elif mutation == "license":
        del repo["license_spdx"]
    elif mutation == "issue_duplicate":
        repo["issues"].append(copy.deepcopy(issue))
        data["dataset"]["pilot_candidates"] = 2
    elif mutation == "issue_url":
        issue["url"] = "https://example.invalid/issues/1"
    elif mutation == "heldout":
        issue["split"] = "held_out"
    elif mutation == "labels":
        issue["visible_labels"] = ["bug"]
    elif mutation == "cutoff":
        issue["created_date"] = "2025-01-01"
    elif mutation == "secret":
        issue["title_cue"] = "ghp_" + "a" * 36
    elif mutation == "issue_body":
        issue["body"] = "not permitted in metadata selection"
    elif mutation == "limit":
        data["proposed_limits"]["issues"] = 11
    elif mutation == "source_relationship":
        issue["source_relationship"] = "VERIFIED"
    elif mutation == "bool_coercion":
        repo["public"] = 1
    elif mutation == "integer_coercion":
        data["dataset"]["approved_issues"] = False
    else:
        data["proposed_retention"]["status"] = "APPROVED"
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)
