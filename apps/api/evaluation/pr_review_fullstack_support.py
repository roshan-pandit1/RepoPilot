import os
import app.modules.github.client as github_client
from evaluation.pr_review_celery_support import Github, Pull, guard
from evaluation.pr_review_celery_support import celery as celery
from evaluation.pr_review_offline_fixture import OfflineGitHubTransport
from app.modules.github.client import get_github_client
from app.modules.github.source_client import GitHubSourceClient
from app.modules.pr_review import worker
from app.modules.pr_review.core import PullClient
from app.main import app
from app.workers import tasks

guard()

# Even an unexpected production-client fallback must not contact GitHub during replay.
import httpx  # noqa: E402

_original_network_request = httpx.HTTPTransport.handle_request


def _deny_github_network(self, request):
    if request.url.host in {"api.github.com", "github.com"}:
        raise RuntimeError("network GitHub access is disabled for offline integration")
    return _original_network_request(self, request)


httpx.HTTPTransport.handle_request = _deny_github_network
assert os.environ.get("RP_MODE") in ("httpx", "synthetic"), "explicit fixture mode required"
real = os.environ["RP_MODE"] == "httpx"
transport = None
if real:
    transport = OfflineGitHubTransport(
        os.environ["RP_PR_FIXTURE_DIR"],
        "19348c64f374322107b39c6d6cf60375ddecd0c293ad20a91ab3615c6bba25eb",
    )

    class FixturePull(PullClient):
        def __init__(self, *a, **kw):
            super().__init__(70, transport=transport)

    class FixtureSource(GitHubSourceClient):
        def __init__(self, *a, **kw):
            super().__init__(max_requests=160, max_seconds=120, transport=transport)

    worker.PullClient = FixturePull
    worker.GitHubSourceClient = FixtureSource


class FixtureGithub(Github):
    def exchange_code(self, code, verifier):
        assert code in ("fixture-code", "fixture-code2") and len(verifier) >= 43
        return {
            "access_token": "other-fixture-token"
            if code == "fixture-code2"
            else "sensitive-github-token",
            "expires_in": 3600,
        }

    def current_user(self, token):
        return (
            {"id": 78, "login": "other"}
            if token == "other-fixture-token"
            else {"id": 77, "login": "alice"}
        )

    def repositories(self, token, installation):
        # Synthetic-only test marker simulates an authoritative GitHub deselection.
        marker = os.environ.get("RP_REVOCATION_MARKER", "")
        if marker and os.path.isfile(marker):
            return []
        return (
            [{"id": 179492861, "full_name": "encode/httpx", "private": False}]
            if real
            else super().repositories(token, installation)
        )

    def issues(self, token, repo):
        return []

    def pull(self, token, repo, number):
        return FixturePull().pull(token, repo, number) if real else Pull().pull(token, repo, number)


fixture = FixtureGithub()
worker.get_github_client = lambda: fixture
app.dependency_overrides[get_github_client] = lambda: fixture
tasks.get_github_client = lambda: fixture
github_client.get_github_client = lambda: fixture
if __name__ == "__main__":
    from app.workers.dispatcher import main

    main()
