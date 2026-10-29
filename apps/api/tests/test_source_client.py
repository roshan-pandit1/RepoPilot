import base64
import hashlib

import httpx
import pytest

from app.modules.github.client import GitHubFailure
from app.modules.github.source_client import GitHubSourceClient
from app.modules.ingestion.code_selection import contains_sensitive_source
from app.modules.ingestion.code_snapshot import plan_snapshot


def test_snapshot_and_blob_fetch_are_pinned_and_verified():
    source = b"def answer():\n    return 42\n"
    blob = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "api.github.com"
        assert request.headers["authorization"] == "Bearer fixture-token"
        if request.url.path == "/repos/alice/example":
            return httpx.Response(200, json={"private": False, "full_name": "alice/example", "default_branch": "main"})
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "a" * 40, "commit": {"tree": {"sha": "b" * 40}}})
        if request.url.path.endswith("/git/trees/" + "b" * 40):
            assert request.url.params["recursive"] == "1"
            return httpx.Response(200, json={"truncated": False, "tree": [{"path": "main.py", "type": "blob", "mode": "100644", "sha": blob, "size": len(source)}]})
        if request.url.path.endswith("/git/blobs/" + blob):
            return httpx.Response(200, json={"sha": blob, "size": len(source), "encoding": "base64", "content": base64.b64encode(source).decode()})
        return httpx.Response(404)

    client = GitHubSourceClient(transport=httpx.MockTransport(handler))
    plan = plan_snapshot(client, "fixture-token", "alice/example")
    assert plan.commit_sha == "a" * 40
    assert client.blob("fixture-token", "alice/example", plan.files[0].blob_sha, len(source)) == source
    assert len(requests) == 4


def test_source_client_rejects_rate_limits_and_bounded_requests():
    client = GitHubSourceClient(max_requests=1, transport=httpx.MockTransport(
        lambda request: httpx.Response(429, text="sensitive upstream text")))
    with pytest.raises(GitHubFailure, match="github_rate_limited"):
        client.repository("secret-token", "alice/example")
    with pytest.raises(GitHubFailure, match="github_request_budget_exceeded"):
        client.repository("secret-token", "alice/example")


def test_source_client_rejects_unresolved_and_invalid_blob():
    client = GitHubSourceClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        "sha": "a" * 40, "size": 1, "encoding": "base64", "content": "eA=="})))
    with pytest.raises(GitHubFailure, match="github_commit_not_resolved"):
        client.tree("token", "alice/example", "a" * 40)
    with pytest.raises(GitHubFailure, match="github_blob_invalid"):
        client.blob("token", "alice/example", "a" * 40, 1)


def test_sensitive_source_detection_is_conservative():
    assert contains_sensitive_source("key = '" + "ghp_" + "a" * 36 + "'")
    assert contains_sensitive_source("-----BEGIN PRIVATE KEY-----")
    assert not contains_sensitive_source("def token_count(value):\n    return len(value)\n")
