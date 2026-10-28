"""Narrow GitHub App user-token client, replaceable in tests."""
from typing import Protocol
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class GitHubFailure(Exception):
    """Sanitized upstream failure: never include tokens, codes, or response bodies."""


class GitHubClient(Protocol):
    def exchange_code(self, code: str, verifier: str) -> dict: ...
    def current_user(self, token: str) -> dict: ...
    def installations(self, token: str) -> list[dict]: ...
    def repositories(self, token: str, installation_id: int) -> list[dict]: ...
    def issues(self, token: str, full_name: str) -> list[dict]: ...


class HttpGitHubClient:
    def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            with httpx.Client(timeout=10, follow_redirects=False) as client:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError("Unexpected GitHub response")
                return result
        except (httpx.HTTPError, ValueError, TypeError):
            raise GitHubFailure("github_request_failed") from None

    def exchange_code(self, code: str, verifier: str) -> dict:
        settings = get_settings()
        return self._request("POST", "https://github.com/login/oauth/access_token",
                             headers={"Accept": "application/json"}, data={
                                 "client_id": settings.github_client_id,
                                 "client_secret": settings.github_client_secret.get_secret_value(),
                                 "code": code, "code_verifier": verifier,
                                 "redirect_uri": settings.github_callback_url,
                             })

    def _get(self, path: str, token: str, params: dict | None = None) -> dict:
        return self._request("GET", "https://api.github.com" + path, params=params,
                             headers={"Accept": "application/vnd.github+json",
                                      "Authorization": "Bearer " + token,
                                      "X-GitHub-Api-Version": "2022-11-28"})

    def current_user(self, token: str) -> dict:
        return self._get("/user", token)

    def _pages(self, path: str, key: str, token: str) -> list[dict]:
        records = []
        for page in range(1, 11):
            data = self._get(path, token, {"per_page": 100, "page": page})
            items = data.get(key)
            if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
                raise GitHubFailure("github_response_invalid")
            records.extend(items)
            if len(items) < 100:
                return records
        # Never authorize using a truncated view of accessible repositories/installations.
        raise GitHubFailure("github_pagination_limit")

    def installations(self, token: str) -> list[dict]:
        return self._pages("/user/installations", "installations", token)

    def repositories(self, token: str, installation_id: int) -> list[dict]:
        return self._pages(f"/user/installations/{installation_id}/repositories", "repositories", token)

    def issues(self, token: str, full_name: str) -> list[dict]:
        parts = full_name.split("/")
        if len(parts) != 2 or not all(parts) or any(part in {".", ".."} for part in parts):
            raise GitHubFailure("github_repository_invalid")
        path = "/repos/" + "/".join(quote(part, safe="") for part in parts) + "/issues"
        try:
            with httpx.Client(timeout=10, follow_redirects=False) as client:
                response = client.get("https://api.github.com" + path,
                    params={"state": "all", "per_page": 100, "page": 1},
                    headers={"Accept": "application/vnd.github+json", "Authorization": "Bearer " + token,
                             "X-GitHub-Api-Version": "2022-11-28"})
                response.raise_for_status()
                records = response.json()
                if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
                    raise ValueError("Unexpected GitHub response")
                return records
        except (httpx.HTTPError, ValueError, TypeError):
            raise GitHubFailure("github_request_failed") from None


def get_github_client() -> GitHubClient:
    return HttpGitHubClient()
