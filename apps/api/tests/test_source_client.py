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


def test_tree_cache_is_bounded_to_authorization_and_validated_tree(monkeypatch):
    client = GitHubSourceClient()
    client._trees[("example/repo", "a" * 40)] = "b" * 40
    requests = []
    def get(path, token, **kwargs):
        requests.append((path, token))
        return {"sha": "b" * 40, "truncated": False, "tree": [
            {"path": "a.py", "type": "blob", "mode": "100644", "sha": "c" * 40, "size": 2},
            {"path": "b.py", "type": "blob", "mode": "100644", "sha": "d" * 40, "size": 3}]}
    monkeypatch.setattr(client, "_get", get)
    assert client.tree_file("token1", "example/repo", "a" * 40, "a.py")["size"] == 2
    assert client.tree_file("token1", "example/repo", "a" * 40, "b.py")["size"] == 3
    assert len(requests) == 1
    assert client.tree_file("token2", "example/repo", "a" * 40, "a.py")["size"] == 2
    assert len(requests) == 2


def test_truncated_tree_is_never_cached(monkeypatch):
    client = GitHubSourceClient()
    client._trees[("example/repo", "a" * 40)] = "b" * 40
    calls = []
    def get(path, token, **kwargs):
        calls.append(1)
        return {"sha": "b" * 40, "truncated": True, "tree": []}
    monkeypatch.setattr(client, "_get", get)
    for _ in range(2):
        with pytest.raises(GitHubFailure, match="github_tree_invalid"):
            client.tree_file("token", "example/repo", "a" * 40, "a.py")
    assert len(calls) == 2 and not client._tree_cache


@pytest.mark.parametrize("status,headers,expected", [
    (401, {}, "github_authentication_failed"),
    (403, {}, "github_permission_denied"),
    (403, {"x-ratelimit-remaining": "0"}, "github_rate_limited"),
    (403, {"retry-after": "60"}, "github_secondary_rate_limited"),
    (429, {"retry-after": "60"}, "github_secondary_rate_limited"),
    (429, {}, "github_rate_limited"),
    (404, {}, "github_not_found"),
    (503, {}, "github_temporarily_unavailable"),
])
def test_source_http_errors_are_classified_without_leaking_body(status, headers, expected):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, headers=headers, text="private error"))
    client = GitHubSourceClient(transport=transport)
    with pytest.raises(GitHubFailure) as caught:
        client.repository("secret-token", "alice/example")
    assert str(caught.value) == expected


def test_network_timeout_is_sanitized_as_transient():
    def timeout(request):
        raise httpx.ReadTimeout("sensitive upstream detail", request=request)
    client = GitHubSourceClient(transport=httpx.MockTransport(timeout))
    with pytest.raises(GitHubFailure) as caught:
        client.repository("secret-token", "alice/example")
    assert str(caught.value) == "github_temporarily_unavailable"


def test_rate_limit_metadata_is_bounded_and_sanitized():
    from datetime import datetime, timedelta, timezone
    from app.modules.github.client import github_http_failure
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    reset = str(int((now + timedelta(minutes=4)).timestamp()))
    failure = github_http_failure(403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset}, now=now)
    assert str(failure) == "github_rate_limited"
    assert failure.retry_at == now + timedelta(minutes=4, seconds=1)
    secondary = github_http_failure(429, {"retry-after": "125"}, now=now)
    assert str(secondary) == "github_secondary_rate_limited"
    assert secondary.retry_at == now + timedelta(seconds=126)
    assert github_http_failure(401, {"retry-after": "120"}, now=now).retry_at is None
    assert github_http_failure(403, {"x-ratelimit-remaining": "0"}, now=now).retry_at is None
    assert github_http_failure(429, {"retry-after": "999999"}, now=now).retry_at is None
    assert github_http_failure(429, {"retry-after": "NaN"}, now=now).retry_at is None
