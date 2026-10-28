import httpx
import pytest

from app.modules.github.client import GitHubFailure, HttpGitHubClient


def mock_client(monkeypatch, handler):
    constructor = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: constructor(
        transport=httpx.MockTransport(handler), **kwargs))


def test_github_client_uses_fixed_origin_bearer_and_bounded_pagination(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "api.github.com"
        assert request.headers["authorization"] == "Bearer fixture-token"
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 7, "login": "test"})
        if request.url.path == "/user/installations":
            return httpx.Response(200, json={"installations": [{"id": 1}]})
        if request.url.path == "/user/installations/1/repositories":
            return httpx.Response(200, json={"repositories": [{"id": 2}]})
        if request.url.path == "/repos/owner/repo/issues":
            return httpx.Response(200, json=[{"id": 4}])
        return httpx.Response(404)

    mock_client(monkeypatch, handler)
    client = HttpGitHubClient()
    assert client.current_user("fixture-token")["id"] == 7
    assert client.installations("fixture-token")[0]["id"] == 1
    assert client.repositories("fixture-token", 1)[0]["id"] == 2
    assert client.issues("fixture-token", "owner/repo")[0]["id"] == 4
    assert all(request.url.scheme == "https" for request in requests)
    with pytest.raises(GitHubFailure):
        client.issues("fixture-token", "../repo")


def test_github_client_sanitizes_upstream_failure(monkeypatch):
    mock_client(monkeypatch, lambda request: httpx.Response(403, text="sensitive-response"))
    with pytest.raises(GitHubFailure) as exc:
        HttpGitHubClient().current_user("sensitive-token")
    assert "sensitive" not in str(exc.value)


def test_code_exchange_posts_pkce_to_fixed_github_endpoint(monkeypatch):
    from urllib.parse import parse_qs

    from pydantic import SecretStr

    from app.core.config import get_settings

    config = get_settings()
    monkeypatch.setattr(config, "github_client_id", "fixture-client")
    monkeypatch.setattr(config, "github_client_secret", SecretStr("fixture-secret"))
    monkeypatch.setattr(config, "github_callback_url", "http://localhost:3000/api/auth/callback")

    def handler(request):
        assert str(request.url) == "https://github.com/login/oauth/access_token"
        body = parse_qs(request.content.decode())
        assert body["code"] == ["fixture-code"]
        assert body["code_verifier"] == ["fixture-verifier"]
        assert body["client_secret"] == ["fixture-secret"]
        return httpx.Response(200, json={"access_token": "fixture-token"})

    mock_client(monkeypatch, handler)
    assert HttpGitHubClient().exchange_code("fixture-code", "fixture-verifier")["access_token"] == "fixture-token"
