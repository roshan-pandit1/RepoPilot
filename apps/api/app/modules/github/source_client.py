"""Bounded GitHub source reads. Callers must enforce repository authorization."""
import base64
import binascii
import hashlib
import json
import re
import time
from urllib.parse import quote

import httpx

from app.modules.github.client import GitHubFailure, github_http_failure

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
        # Git trees are immutable. Keep a bounded per-client cache, scoped to the
        # repository and a token fingerprint, so one review does not repeatedly
        # spend its GitHub request budget walking the same directory trees.
        self._tree_cache: dict[tuple[str, str, str], dict] = {}

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
            with httpx.Client(timeout=10, follow_redirects=False, transport=self.transport, trust_env=False) as client:
                with client.stream("GET", "https://api.github.com" + path, params=params,
                                   headers={"Accept": "application/vnd.github+json",
                                            "Authorization": "Bearer " + token,
                                            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "RepoPilot-ReadOnly/1"}) as response:
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
            raise github_http_failure(exc.response.status_code, exc.response.headers) from None
        except (httpx.TimeoutException, httpx.NetworkError):
            raise GitHubFailure("github_temporarily_unavailable") from None
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

    def is_ancestor(self, token: str, full_name: str, commit_sha: str, head_sha: str) -> bool:
        """Verify a pinned commit is in the explicitly resolved branch history."""
        if not isinstance(commit_sha, str) or not _SHA.fullmatch(commit_sha) or not isinstance(head_sha, str) or not _SHA.fullmatch(head_sha):
            raise GitHubFailure("github_commit_invalid")
        if (full_name, commit_sha) not in self._trees or (full_name, head_sha) not in self._trees:
            raise GitHubFailure("github_commit_not_resolved")
        if commit_sha == head_sha:
            return True
        data = self._get(self._repo(full_name) + "/compare/" + commit_sha + "..." + head_sha, token)
        base, merge = data.get("base_commit"), data.get("merge_base_commit")
        return (isinstance(base, dict) and base.get("sha") == commit_sha and isinstance(merge, dict)
                and merge.get("sha") == commit_sha and data.get("status") == "ahead"
                and type(data.get("behind_by")) is int and data["behind_by"] == 0)

    def tree_file(self, token: str, full_name: str, commit_sha: str, path: str) -> dict:
        """Resolve one regular file through nonrecursive trees bound to a resolved commit."""
        tree_sha = self._trees.get((full_name, commit_sha))
        if not tree_sha:
            raise GitHubFailure("github_commit_not_resolved")
        if (not isinstance(path, str) or not path or len(path) > 512 or path.startswith("/")
                or "\\" in path or "\x00" in path or any(x in {"", ".", ".."} for x in path.split("/"))
                or len(path.split("/")) > 32):
            raise GitHubFailure("github_path_invalid")
        parts = path.split("/")
        for index, part in enumerate(parts):
            token_fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
            cache_key = (full_name, tree_sha, token_fingerprint)
            data = self._tree_cache.get(cache_key)
            if data is None:
                data = self._get(self._repo(full_name) + "/git/trees/" + tree_sha, token)
            entries = data.get("tree")
            if (data.get("sha") != tree_sha or data.get("truncated") is not False
                    or not isinstance(entries, list) or len(entries) > 10000):
                raise GitHubFailure("github_tree_invalid")
            if cache_key not in self._tree_cache and len(self._tree_cache) < 16:
                self._tree_cache[cache_key] = data
            matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("path") == part]
            if len(matches) != 1:
                raise GitHubFailure("github_path_unavailable")
            entry = matches[0]
            sha = entry.get("sha")
            if not isinstance(sha, str) or not _SHA.fullmatch(sha):
                raise GitHubFailure("github_tree_invalid")
            if index < len(parts) - 1:
                if entry.get("type") != "tree" or entry.get("mode") != "040000":
                    raise GitHubFailure("github_path_unavailable")
                tree_sha = sha
            else:
                size = entry.get("size")
                if (entry.get("type") != "blob" or entry.get("mode") not in {"100644", "100755"}
                        or type(size) is not int or not 0 <= size <= self.max_file_bytes):
                    raise GitHubFailure("github_path_unavailable")
                return {"path": path, "sha": sha, "size": size}
        raise GitHubFailure("github_path_unavailable")

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
