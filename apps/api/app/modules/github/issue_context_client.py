"""Per-operation bounded GitHub issue and authorization reads."""
import json
import time

import httpx

from app.modules.github.client import GitHubFailure, HttpGitHubClient
from app.modules.github.source_client import GitHubSourceClient


class IssueContextClient(HttpGitHubClient):
    def __init__(self, max_requests: int, transport=None):
        self.remaining = max_requests
        self.transport = transport
        self.deadline = time.monotonic() + 60

    def _read(self, path, token, params=None):
        if self.remaining <= 0 or time.monotonic() >= self.deadline:
            raise GitHubFailure("github_budget_exceeded")
        self.remaining -= 1
        try:
            with httpx.Client(timeout=10, follow_redirects=False, transport=self.transport) as client:
                with client.stream("GET", "https://api.github.com" + path, params=params,
                    headers={"Accept": "application/vnd.github+json", "Authorization": "Bearer " + token,
                             "X-GitHub-Api-Version": "2022-11-28"}) as response:
                    if response.status_code == 404:
                        raise GitHubFailure("github_not_found")
                    if response.status_code == 429 or (response.status_code == 403 and
                            response.headers.get("x-ratelimit-remaining") == "0"):
                        raise GitHubFailure("github_rate_limited")
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if len(body) + len(chunk) > 1_000_000 or time.monotonic() >= self.deadline:
                            raise GitHubFailure("github_response_limit")
                        body.extend(chunk)
            return json.loads(body)
        except (httpx.HTTPError, ValueError, TypeError, RecursionError):
            raise GitHubFailure("github_request_failed") from None

    def _get(self, path, token, params=None):
        result = self._read(path, token, params)
        if not isinstance(result, dict):
            raise GitHubFailure("github_response_invalid")
        return result

    def issue(self, token, full_name, number):
        return self._get(GitHubSourceClient._repo(full_name) + f"/issues/{number}", token)

    def issue_comments(self, token, full_name, number, count):
        result = self._read(GitHubSourceClient._repo(full_name) + f"/issues/{number}/comments", token,
                            {"per_page": max(1, count + 1), "page": 1, "sort": "created", "direction": "asc"})
        if not isinstance(result, list) or not all(isinstance(x, dict) for x in result) or len(result) > count + 1:
            raise GitHubFailure("github_response_invalid")
        return result
