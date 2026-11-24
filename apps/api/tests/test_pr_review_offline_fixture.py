"""Synthetic integrity checks for the private offline transport."""

import hashlib
import json
import httpx
import pytest
from evaluation.pr_review_offline_fixture import OfflineFixtureError, OfflineGitHubTransport


def fixture(tmp_path):
    tmp_path.chmod(0o700)
    raw = b'{"synthetic":true}'
    digest = hashlib.sha256(raw).hexdigest()
    name = digest + ".json"
    (tmp_path / name).write_bytes(raw)
    (tmp_path / name).chmod(0o600)
    url = "https://api.github.com/repos/encode/httpx/pulls/3690"
    value = {
        "version": "httpx-3690-github-readonly-v1",
        "repository_id": 179492861,
        "pr": {
            "id": 2910330172,
            "base_sha": "20380490fd0bd13c68704080754c1385bff96d69",
            "head_sha": "350221558d4f079fc4ab3673d81a4bc730fbb9c3",
        },
        "requests": {url: {"file": name, "sha256": digest, "bytes": len(raw)}},
    }
    manifest = json.dumps(value).encode()
    (tmp_path / "manifest.json").write_bytes(manifest)
    (tmp_path / "manifest.json").chmod(0o600)
    return hashlib.sha256(manifest).hexdigest(), url, name


def test_verified_object_replays_without_network_and_rejects_missing(tmp_path):
    digest, url, _ = fixture(tmp_path)
    transport = OfflineGitHubTransport(str(tmp_path), digest)
    assert transport.handle_request(httpx.Request("GET", url)).json() == {"synthetic": True}
    with pytest.raises(OfflineFixtureError, match="missing"):
        transport.handle_request(httpx.Request("GET", url + "/missing"))
    with pytest.raises(OfflineFixtureError, match="denied"):
        transport.handle_request(httpx.Request("POST", url))


def test_manifest_and_object_tampering_fail_closed(tmp_path):
    digest, url, name = fixture(tmp_path)
    with pytest.raises(OfflineFixtureError, match="manifest mismatch"):
        OfflineGitHubTransport(str(tmp_path), "0" * 64)
    transport = OfflineGitHubTransport(str(tmp_path), digest)
    (tmp_path / name).write_bytes(b"tampered")
    with pytest.raises(OfflineFixtureError, match="object mismatch"):
        transport.handle_request(httpx.Request("GET", url))
