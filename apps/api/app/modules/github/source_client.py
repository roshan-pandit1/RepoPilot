"""Bounded GitHub source reads. Callers must enforce repository authorization."""
import base64
import binascii
import hashlib
import json
import re
import time
from urllib.parse import quote

import httpx

from app.modules.github.client import GitHubFailure

_SHA = re.compile(r"[0-9a-f]{40}\Z")


class GitHubSourceClient:
    def __init__(self, *, max_requests: int = 1005, max_response_bytes: int = 4_000_000,
                 max_file_bytes: int = 100_000, max_seconds: int = 120,
                 transport: httpx.BaseTransport | None = None):
        if min(max_requests, max_response_bytes, max_file_bytes, max_seconds) <= 0:
            raise ValueError("source limits must be positive")
        self.remaining = max_requests
        self.max_response_bytes = max_response_bytes
        self.max_file_bytes = max_file_bytes
        self.transport = transport
        self.deadline = time.monotonic() + max_seconds
        self._trees: dict[tuple[str, str], str] = {}

    @staticmethod
    def _repo(full_name: str) -> str:
        parts = full_name.split("/")
        if len(parts) != 2 or any(not p or p in {".", ".."} for p in parts):
            raise GitHubFailure("github_repository_invalid")
        return "/repos/" + "/".join(quote(part, safe="") for part in parts)

    def _get(self, path: str, token: str, *, params: dict | None = None,
             limit: int | None = None) -> dict:
        if self.remaining <= 0:
            raise GitHubFailure("github_request_budget_exceeded")
        if time.monotonic() >= self.deadline:
            raise GitHubFailure("github_time_budget_exceeded")
        self.remaining -= 1
        try:
            with httpx.Client(timeout=10, follow_redirects=False, transport=self.transport) as client:
                with client.stream("GET", "https://api.github.com" + path, params=params,
                                   headers={"Accept": "application/vnd.github+json",
                                            "Authorization": "Bearer " + token,
                                            "X-GitHub-Api-Version": "2022-11-28"}) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() >= self.deadline:
                            raise GitHubFailure("github_time_budget_exceeded")
                        if len(body) + len(chunk) > (limit or self.max_response_bytes):
                            raise GitHubFailure("github_response_too_large")
                        body.extend(chunk)
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError("invalid response")
            return result
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 or (exc.response.status_code == 403 and
                    exc.response.headers.get("x-ratelimit-remaining") == "0"):
                raise GitHubFailure("github_rate_limited") from None
            raise GitHubFailure("github_request_failed") from None
        except (httpx.HTTPError, ValueError, TypeError):
            raise GitHubFailure("github_request_failed") from None

    def repository(self, token: str, full_name: str) -> dict:
        return self._get(self._repo(full_name), token)

    def commit(self, token: str, full_name: str, branch: str) -> dict:
        if not branch or len(branch) > 255:
            raise GitHubFailure("github_branch_invalid")
        data = self._get(self._repo(full_name) + "/commits/" + quote(branch, safe=""), token)
        sha = data.get("sha")
        commit_data = data.get("commit")
        tree_data = commit_data.get("tree") if isinstance(commit_data, dict) else None
        tree = tree_data.get("sha") if isinstance(tree_data, dict) else None
        if not isinstance(sha, str) or not _SHA.fullmatch(sha) or not isinstance(tree, str) or not _SHA.fullmatch(tree):
            raise GitHubFailure("github_commit_invalid")
        self._trees[(full_name, sha)] = tree
        return {"sha": sha}

    def tree(self, token: str, full_name: str, sha: str) -> dict:
        tree = self._trees.get((full_name, sha))
        if not tree:
            raise GitHubFailure("github_commit_not_resolved")
        return self._get(self._repo(full_name) + "/git/trees/" + tree, token,
                         params={"recursive": "1"})

    def blob(self, token: str, full_name: str, sha: str, expected_size: int) -> bytes:
        if not _SHA.fullmatch(sha) or isinstance(expected_size, bool) or not 0 <= expected_size <= self.max_file_bytes:
            raise GitHubFailure("github_blob_invalid")
        data = self._get(self._repo(full_name) + "/git/blobs/" + sha, token,
                         limit=min(self.max_response_bytes, self.max_file_bytes * 2 + 4096))
        try:
            if data.get("encoding") != "base64" or data.get("sha") != sha or data.get("size") != expected_size:
                raise ValueError("invalid metadata")
            content = data["content"]
            if not isinstance(content, str):
                raise ValueError("invalid content")
            raw = base64.b64decode("".join(content.split()), validate=True)
            git_sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if len(raw) != expected_size or git_sha != sha:
                raise ValueError("invalid content")
            return raw
        except (ValueError, KeyError, TypeError, binascii.Error):
            raise GitHubFailure("github_blob_invalid") from None
