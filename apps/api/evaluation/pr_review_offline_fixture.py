"""Private, content-addressed GitHub response replay for opt-in integration tests.

This transport has no fallback network path. Callers must separately authenticate
and authorize repository access; fixture integrity does not grant access.
"""

from hashlib import sha256
import json
import os
from pathlib import Path
import stat

import httpx

from app.modules.github.client import GitHubFailure


class OfflineFixtureError(GitHubFailure):
    pass


class OfflineGitHubTransport(httpx.BaseTransport):
    def __init__(self, directory: str, manifest_sha256: str):
        self.directory = Path(directory)
        if (
            not self.directory.is_absolute()
            or self.directory.is_symlink()
            or not self.directory.is_dir()
            or self.directory.stat().st_uid != os.getuid()
            or stat.S_IMODE(self.directory.stat().st_mode) & 0o077
        ):
            raise OfflineFixtureError("invalid fixture directory")
        raw = self._read("manifest.json", 2_000_000)
        if sha256(raw).hexdigest() != manifest_sha256:
            raise OfflineFixtureError("fixture manifest mismatch")
        try:
            manifest = json.loads(raw)
            records = manifest["requests"]
            if (
                manifest["version"] != "httpx-3690-github-readonly-v1"
                or manifest["repository_id"] != 179492861
                or manifest["pr"]["id"] != 2910330172
                or manifest["pr"]["base_sha"] != "20380490fd0bd13c68704080754c1385bff96d69"
                or manifest["pr"]["head_sha"] != "350221558d4f079fc4ab3673d81a4bc730fbb9c3"
                or not isinstance(records, dict)
                or not 1 <= len(records) <= 100
            ):
                raise ValueError
            self.records = records
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise OfflineFixtureError("invalid fixture manifest") from None

    def _read(self, name: str, maximum: int) -> bytes:
        path = self.directory / name
        if (
            "/" in name
            or "\\" in name
            or path.is_symlink()
            or not path.is_file()
            or path.stat().st_uid != os.getuid()
            or stat.S_IMODE(path.stat().st_mode) & 0o077
            or path.stat().st_size > maximum
        ):
            raise OfflineFixtureError("invalid fixture object")
        return path.read_bytes()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if (
            request.method != "GET"
            or request.url.scheme != "https"
            or request.url.host != "api.github.com"
            or request.url.port is not None
        ):
            raise OfflineFixtureError("fixture request denied")
        entry = self.records.get(str(request.url))
        if not isinstance(entry, dict):
            raise OfflineFixtureError("fixture object missing")
        digest, size, name = entry.get("sha256"), entry.get("bytes"), entry.get("file")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or name != digest + ".json"
            or type(size) is not int
            or not 0 <= size <= 4_000_000
        ):
            raise OfflineFixtureError("invalid fixture identity")
        raw = self._read(name, 4_000_000)
        if len(raw) != size or sha256(raw).hexdigest() != digest:
            raise OfflineFixtureError("fixture object mismatch")
        return httpx.Response(200, content=raw, request=request)
