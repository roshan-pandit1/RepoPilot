"""Narrow GitHub App user-token client, replaceable in tests."""
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class GitHubFailure(Exception):
    """Sanitized upstream failure with optional validated retry eligibility."""

    def __init__(self, code: str, *, retry_at: datetime | None = None):
        super().__init__(code)
        self.retry_at = retry_at


def github_http_failure(status: int, headers, *, now: datetime | None = None) -> GitHubFailure:
    """Honor bounded GitHub reset metadata; never derive retries from response text."""
    code = classify_github_status(status, headers)
    current = now or datetime.now(timezone.utc)
    if code not in {"github_rate_limited", "github_secondary_rate_limited"}:
        return GitHubFailure(code)
    candidates = []
    reset = headers.get("x-ratelimit-reset")
    after = headers.get("retry-after")
    if headers.get("x-ratelimit-remaining") == "0":
        if not isinstance(reset, str) or not reset.isascii() or not reset.isdigit() or len(reset) > 12:
            return GitHubFailure(code)
        try:
            candidates.append(datetime.fromtimestamp(int(reset), timezone.utc) + timedelta(seconds=1))
        except (ValueError, OverflowError, OSError):
            return GitHubFailure(code)
    if after is not None:
        if not isinstance(after, str) or not after.isascii() or not after.isdigit() or len(after) > 6:
            return GitHubFailure(code)
        candidates.append(current + timedelta(seconds=int(after) + 1))
    if not candidates:
        return GitHubFailure(code)
    retry_at = max(candidates + [current + timedelta(seconds=60)])
    if retry_at <= current or retry_at > current + timedelta(hours=24):
        return GitHubFailure(code)
    return GitHubFailure(code, retry_at=retry_at)


def classify_github_status(status: int, headers) -> str:
    """Return a fixed, non-sensitive failure code; never inspect response bodies."""
    if status == 401:
        return "github_authentication_failed"
    if status in (403, 429) and headers.get("x-ratelimit-remaining") == "0":
        return "github_rate_limited"
    if status in (403, 429) and headers.get("retry-after") is not None:
        return "github_secondary_rate_limited"
    if status == 429:
        return "github_rate_limited"
    if status == 403:
        return "github_permission_denied"
    if status == 404:
        return "github_not_found"
    if status >= 500:
        return "github_temporarily_unavailable"
    return "github_request_failed"


class GitHubClient(Protocol):
    def exchange_code(self, code: str, verifier: str) -> dict: ...
    def current_user(self, token: str) -> dict: ...
    def installations(self, token: str) -> list[dict]: ...
    def repositories(self, token: str, installation_id: int) -> list[dict]: ...
    def issues(self, token: str, full_name: str) -> list[dict]: ...


class HttpGitHubClient:
    def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
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
            with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
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
