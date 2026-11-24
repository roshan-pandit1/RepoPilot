from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256

import httpx
import pytest

from app.modules.github.client import GitHubFailure
from app.modules.github.issue_context_client import IssueContextClient
from app.modules.github.upstream_issue import read_direct_parent_issue, revalidate_direct_parent_issue


class SyntheticGitHub:
    def __init__(self):
        self.repo = {"id": 11, "full_name": "alice/fork", "private": False, "fork": True,
                     "parent": {"id": 22, "full_name": "bob/project", "private": False}}
        self.item = {"id": 33, "number": 7, "title": "Example issue", "body": "Synthetic issue body",
                     "html_url": "https://github.com/bob/project/issues/7",
                     "repository_url": "https://api.github.com/repos/bob/project", "state": "open",
                     "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-02T00:00:00Z",
                     "comments": 0, "labels": []}
        self.seen = []

    def repository(self, token, name):
        self.seen.append(("repository", name))
        return deepcopy(self.repo)

    def issue(self, token, name, number):
        self.seen.append(("issue", name, number))
        return deepcopy(self.item)


def read(github, **kwargs):
    return read_direct_parent_issue(github, "synthetic-token", 11, "alice/fork", 7, **kwargs)


def test_direct_parent_verifies_stable_identity_and_body_digest():
    github = SyntheticGitHub()
    value = read(github, expected_parent_id=22, expected_issue_id=33)
    assert github.seen == [("repository", "alice/fork"), ("issue", "bob/project", 7)]
    assert (value.target_repository_id, value.origin_repository_id, value.origin_repository_name) == (11, 22, "bob/project")
    assert value.issue_id == 33 and value.issue_number == 7
    assert value.issue_body_sha256 == sha256(b"Synthetic issue body").hexdigest()
    assert value.issue_updated_at == datetime(2025, 1, 2, tzinfo=timezone.utc)
    assert value.relationship == "direct_public_parent" and value.issue_body not in repr(value)
    assert revalidate_direct_parent_issue(github, "synthetic-token", value).issue_id == 33


@pytest.mark.parametrize("change", ["wrong_target", "private_fork", "not_fork", "private_parent",
                                     "same_parent", "bad_parent_name", "forged_parent_id"])
def test_unverified_parent_is_rejected_before_issue_read(change):
    github = SyntheticGitHub()
    if change == "wrong_target":
        github.repo["id"] = 12
    if change == "private_fork":
        github.repo["private"] = True
    if change == "not_fork":
        github.repo["fork"] = False
    if change == "private_parent":
        github.repo["parent"]["private"] = True
    if change == "same_parent":
        github.repo["parent"]["id"] = 11
    if change == "bad_parent_name":
        github.repo["parent"]["full_name"] = "../other"
    if change == "forged_parent_id":
        github.repo["parent"]["id"] = 44
    with pytest.raises(GitHubFailure, match="upstream_relationship_invalid"):
        read(github, expected_parent_id=22)
    assert len(github.seen) == 1


@pytest.mark.parametrize("change", ["wrong_id", "wrong_number", "wrong_html", "wrong_repo_url", "pull_request"])
def test_wrong_or_unrelated_issue_is_rejected(change):
    github = SyntheticGitHub()
    if change == "wrong_id":
        github.item["id"] = 34
    if change == "wrong_number":
        github.item["number"] = 8
    if change == "wrong_html":
        github.item["html_url"] = "https://github.com/eve/other/issues/7"
    if change == "wrong_repo_url":
        github.item["repository_url"] = "https://api.github.com/repos/eve/other"
    if change == "pull_request":
        github.item["pull_request"] = {}
    with pytest.raises(GitHubFailure, match="upstream_issue_invalid"):
        read(github, expected_issue_id=33)


@pytest.mark.parametrize("field", ["title", "body", "updated_at"])
def test_revalidation_rejects_changed_issue(field):
    github = SyntheticGitHub()
    saved = read(github)
    github.item[field] = {"title": "Changed", "body": "Changed", "updated_at": "2025-01-03T00:00:00Z"}[field]
    with pytest.raises(GitHubFailure, match="upstream_issue_changed"):
        revalidate_direct_parent_issue(github, "synthetic-token", saved)


def test_bounded_client_repository_fetch_uses_existing_request_budget():
    def response(request):
        assert request.url.path == "/repos/alice/fork"
        return httpx.Response(200, json={"id": 11})
    client = IssueContextClient(1, transport=httpx.MockTransport(response))
    assert client.repository("synthetic-token", "alice/fork") == {"id": 11}
    with pytest.raises(GitHubFailure, match="github_budget_exceeded"):
        client.repository("synthetic-token", "alice/fork")
