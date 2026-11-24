"""GitHub clients must not inherit proxy or certificate settings from the environment."""
import httpx
from app.modules.github.client import HttpGitHubClient
from app.modules.github.source_client import GitHubSourceClient
from app.modules.github.issue_context_client import IssueContextClient


def test_github_clients_ignore_inherited_proxy_and_certificate_configuration(monkeypatch):
    actual = httpx.Client
    options = []
    def client(*args, **kwargs):
        options.append((kwargs.get("trust_env"), kwargs.get("follow_redirects")))
        kwargs["transport"] = httpx.MockTransport(lambda request: httpx.Response(200, json={"id": 1}))
        return actual(*args, **kwargs)
    monkeypatch.setattr(httpx, "Client", client)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("SSL_CERT_FILE", "/nonexistent/synthetic-certificate")
    assert HttpGitHubClient().current_user("synthetic-token")["id"] == 1
    assert GitHubSourceClient().repository("synthetic-token", "owner/repo")["id"] == 1
    assert IssueContextClient(1).repository("synthetic-token", "owner/repo")["id"] == 1
    assert options == [(False, False)] * 3
