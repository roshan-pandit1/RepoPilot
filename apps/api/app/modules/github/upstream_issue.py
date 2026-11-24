"""Verified, public direct-parent issue identity for an authorized fork.

This module does not authorize access to a target repository. Callers must perform
RepoPilot's tenant, session and target-repository checks before and after network I/O.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import re
from urllib.parse import quote

from pydantic import ValidationError

from app.modules.github.client import GitHubFailure
from app.modules.github.issue_context import IssueData

_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


@dataclass(frozen=True)
class VerifiedUpstreamIssue:
    target_repository_id: int
    target_repository_name: str
    origin_repository_id: int
    origin_repository_name: str
    issue_id: int
    issue_number: int
    issue_url: str
    issue_title: str
    issue_body_sha256: str
    issue_updated_at: datetime
    verified_at: datetime
    issue_body: str = field(repr=False)
    relationship: str = "direct_public_parent"
    issue_data: IssueData | None = field(default=None, repr=False, compare=False)


def _valid_name(value):
    return (isinstance(value, str) and len(value) <= 250 and bool(_NAME.fullmatch(value))
            and all(part not in {".", ".."} for part in value.split("/")))


def _valid_id(value):
    return type(value) is int and 0 < value < 2**63


def _path(name):
    return "/".join(quote(part, safe="") for part in name.split("/"))


def read_direct_parent_issue(client, token, target_id, target_name, issue_number, *,
                             expected_parent_id=None, expected_issue_id=None):
    """Verify the parent from GitHub metadata; caller input cannot choose the origin.

    `expected_*` values may only narrow accepted results; they cannot override GitHub.
    An issue's API and HTML URLs must both identify the verified parent repository.
    """
    if (not _valid_id(target_id) or not _valid_name(target_name)
            or type(issue_number) is not int or not 0 < issue_number < 2**31
            or (expected_parent_id is not None and not _valid_id(expected_parent_id))
            or (expected_issue_id is not None and not _valid_id(expected_issue_id))):
        raise GitHubFailure("upstream_identity_invalid")
    repository = client.repository(token, target_name)
    if not isinstance(repository, dict):
        raise GitHubFailure("upstream_relationship_invalid")
    parent = repository.get("parent")
    if (repository.get("id") != target_id or type(repository.get("id")) is not int
            or repository.get("full_name") != target_name or repository.get("private") is not False
            or repository.get("fork") is not True or not isinstance(parent, dict)
            or parent.get("private") is not False or not _valid_id(parent.get("id"))
            or not _valid_name(parent.get("full_name")) or parent["id"] == target_id
            or parent["full_name"] == target_name
            or (expected_parent_id is not None and parent["id"] != expected_parent_id)):
        raise GitHubFailure("upstream_relationship_invalid")
    name, parent_id = parent["full_name"], parent["id"]
    raw = client.issue(token, name, issue_number)
    expected_url = f"https://github.com/{_path(name)}/issues/{issue_number}"
    expected_api_url = f"https://api.github.com/repos/{_path(name)}"
    if (not isinstance(raw, dict) or "pull_request" in raw
            or raw.get("html_url") != expected_url or raw.get("repository_url") != expected_api_url):
        raise GitHubFailure("upstream_issue_invalid")
    try:
        issue = IssueData.model_validate(raw)
        body = issue.body or ""
        if (issue.number != issue_number or (expected_issue_id is not None and issue.id != expected_issue_id)
                or len(issue.title) > 1024 or len(body) > 16000
                or any(not isinstance(label.get("name"), str) for label in issue.labels)):
            raise ValueError("invalid issue")
        body_hash = sha256(body.encode("utf-8")).hexdigest()
    except (ValidationError, ValueError, TypeError, UnicodeError):
        raise GitHubFailure("upstream_issue_invalid") from None
    return VerifiedUpstreamIssue(target_id, target_name, parent_id, name, issue.id, issue.number,
                                 expected_url, issue.title, body_hash, issue.updated_at,
                                 datetime.now(timezone.utc), body, issue_data=issue)


def revalidate_direct_parent_issue(client, token, saved):
    """Re-read relationship and issue; reject moved, edited or replaced origin data."""
    if not isinstance(saved, VerifiedUpstreamIssue) or saved.relationship != "direct_public_parent":
        raise GitHubFailure("upstream_identity_invalid")
    fresh = read_direct_parent_issue(client, token, saved.target_repository_id,
                                     saved.target_repository_name, saved.issue_number,
                                     expected_parent_id=saved.origin_repository_id,
                                     expected_issue_id=saved.issue_id)
    if (fresh.origin_repository_name != saved.origin_repository_name or fresh.issue_url != saved.issue_url
            or fresh.issue_title != saved.issue_title or fresh.issue_body_sha256 != saved.issue_body_sha256
            or fresh.issue_updated_at != saved.issue_updated_at):
        raise GitHubFailure("upstream_issue_changed")
    return fresh
