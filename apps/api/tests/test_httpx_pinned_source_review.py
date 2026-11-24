"""Bounded, one-issue GitHub capture and synthetic object-integrity tests.

Running pytest only exercises synthetic fixtures. Live collection requires the
explicit ``--capture`` entry point and the approved private destination.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import pytest

from app.evaluation.issue_context_schema import IssueContext, context_digest
from app.modules.ingestion.code_selection import (
    contains_sensitive_source,
    decode_source,
    eligible_python_path,
    incompatible_line_endings,
)

REPOSITORY = "encode/httpx"
REPOSITORY_ID = 179492861
COMMIT = "def4778d622e8bf49a9fea4dda78cca4cf666d8a"
ROOT_TREE = "706b304f7f46b07fa19e000148be76c059890b26"
CONTEXT_SHA256 = "b23e59ea453789ad4783bfbee1e6c0b0e25ac4bfb6938c0bc4b6435338cd6689"
STORAGE = Path("/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1")
ISSUE_DIR = STORAGE / "httpx-issue-triage-20261107T022457Z-cd8f4a83"
SELECTED_PATHS = ("httpx/_client.py", "httpx/_config.py", "httpx/_transports/default.py")
NETWORK_LIMIT = 32 * 1024 * 1024
SOURCE_LIMIT = 5_000_000  # The earlier approval manifest is stricter than 20 MiB.
FILE_LIMIT = 100_000  # The earlier approval manifest is stricter than 1 MiB.
FILE_COUNT_LIMIT = 80
SHA1 = re.compile(r"[0-9a-f]{40}\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def object_id(kind, raw):
    return hashlib.sha1(f"{kind} {len(raw)}\0".encode("ascii") + raw).hexdigest()


def validate_commit(payload, commit, tree):
    if (not isinstance(payload, dict) or payload.get("sha") != commit
            or payload.get("tree", {}).get("sha") != tree):
        raise ValueError("commit_or_tree_mismatch")
    parents = payload.get("parents")
    date = payload.get("committer", {}).get("date")
    if (not isinstance(parents, list) or not parents
            or any(not isinstance(p, dict) or not isinstance(p.get("sha"), str)
                   or not SHA1.fullmatch(p["sha"]) for p in parents)
            or not isinstance(date, str)):
        raise ValueError("invalid_commit_metadata")
    datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
    return {"sha": commit, "tree": tree, "parents": [p["sha"] for p in parents], "committer_date": date}


def validate_tree(payload, expected):
    if (not isinstance(payload, dict) or payload.get("sha") != expected
            or payload.get("truncated") is not False or not isinstance(payload.get("tree"), list)
            or len(payload["tree"]) > 10_000):
        raise ValueError("invalid_or_incomplete_tree")
    seen, entries = set(), []
    for item in payload["tree"]:
        if not isinstance(item, dict):
            raise ValueError("invalid_tree_entry")
        name, mode, kind, sha = (item.get(k) for k in ("path", "mode", "type", "sha"))
        if (not isinstance(name, str) or not name or name in {".", ".."} or "/" in name
                or "\\" in name or "\0" in name or name in seen
                or not isinstance(sha, str) or not SHA1.fullmatch(sha)):
            raise ValueError("invalid_tree_entry")
        # Refuse symlinks and gitlinks rather than resolving or following them.
        if (mode, kind) not in {("040000", "tree"), ("100644", "blob"), ("100755", "blob")}:
            raise ValueError("unsupported_tree_entry")
        seen.add(name)
        entry = {"path": name, "mode": mode, "type": kind, "sha": sha}
        if kind == "blob":
            size = item.get("size")
            if type(size) is not int or size < 0:
                raise ValueError("invalid_blob_size")
            entry["size"] = size
        entries.append(entry)
    ordered = sorted(entries, key=lambda x: x["path"].encode("utf-8") + (b"/" if x["type"] == "tree" else b""))
    raw = b"".join(item["mode"].lstrip("0").encode("ascii") + b" "
                   + item["path"].encode("utf-8") + b"\0" + bytes.fromhex(item["sha"])
                   for item in ordered)
    if object_id("tree", raw) != expected:
        raise ValueError("tree_object_hash_mismatch")
    return ordered


def select_entry(entries, name, kind):
    result = [e for e in entries if e["path"] == name and e["type"] == kind]
    if len(result) != 1:
        raise ValueError("missing_selected_entry")
    return result[0]


def validate_path(path):
    if (not isinstance(path, str) or not path.startswith(("httpx/", "tests/"))
            or not eligible_python_path(path) or str(PurePosixPath(path)) != path):
        raise ValueError("ineligible_source_path")
    return path


def check_source_budget(files):
    if len(files) > FILE_COUNT_LIMIT or len({f["path"] for f in files}) != len(files):
        raise ValueError("source_file_count_or_identity")
    total = 0
    for item in files:
        validate_path(item["path"])
        size = item.get("size")
        if type(size) is not int or size < 0 or size > FILE_LIMIT:
            raise ValueError("source_file_size")
        total += size
        if total > SOURCE_LIMIT:
            raise ValueError("source_aggregate_size")
    return total


def validate_blob(payload, entry):
    if (not isinstance(payload, dict) or payload.get("sha") != entry["sha"]
            or payload.get("size") != entry["size"] or payload.get("encoding") != "base64"
            or not isinstance(payload.get("content"), str)):
        raise ValueError("blob_metadata_mismatch")
    try:
        raw = base64.b64decode(payload["content"].replace("\n", ""), validate=True)
    except (ValueError, TypeError):
        raise ValueError("invalid_blob_encoding") from None
    if len(raw) != entry["size"] or object_id("blob", raw) != entry["sha"]:
        raise ValueError("blob_object_hash_mismatch")
    source = decode_source(raw, FILE_LIMIT)
    if (source is None or contains_sensitive_source(source) or incompatible_line_endings(source)):
        raise ValueError("unsafe_or_invalid_source")
    return raw


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("unexpected_redirect")


class GitHubReader:
    """Anonymous bounded reader; constructed paths never come from GitHub responses."""
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), RejectRedirects())
        self.total = 0
        self.requests = []

    def get(self, kind, sha):
        if kind not in {"commits", "trees", "blobs"} or not SHA1.fullmatch(sha):
            raise ValueError("unexpected_api_request")
        url = f"https://api.github.com/repos/{REPOSITORY}/git/{kind}/{sha}"
        req = Request(url, headers={"Accept": "application/vnd.github+json", "Accept-Encoding": "identity",
                                    "User-Agent": "RepoPilot-3734-pinned-source-review"})
        try:
            with self.opener.open(req, timeout=20) as response:
                if (response.status != 200 or response.geturl() != url
                        or response.headers.get_content_type() != "application/json"
                        or response.headers.get("Content-Encoding", "identity") != "identity"):
                    raise ValueError("unexpected_http_response")
                length = response.headers.get("Content-Length")
                remaining = NETWORK_LIMIT - self.total
                if length is not None and (not length.isdigit() or int(length) >= remaining):
                    raise ValueError("network_budget")
                parts, count = [], 0
                while True:
                    remaining = NETWORK_LIMIT - self.total - count
                    if remaining <= 0:
                        raise ValueError("network_budget")
                    part = response.read(min(65_536, remaining))
                    if not part:
                        break
                    count += len(part)
                    if count >= NETWORK_LIMIT - self.total:
                        raise ValueError("network_budget")
                    parts.append(part)
                if length is not None and count != int(length):
                    raise ValueError("incomplete_http_response")
        except HTTPError as exc:
            raise ValueError(f"github_http_status_{exc.code}") from None
        self.total += count
        self.requests.append({"kind": kind, "sha": sha, "response_body_bytes": count})
        try:
            return json.loads(b"".join(parts))
        except (ValueError, UnicodeError):
            raise ValueError("invalid_github_json") from None


def validate_issue_record():
    summary = json.loads((ISSUE_DIR / "capture-summary.json").read_bytes())
    review = json.loads((ISSUE_DIR / "review-validation.json").read_bytes())
    item = next(x for x in summary["results"] if x["issue"] == 3734)
    standalone = next(x for x in review["standalone_valid_contexts"] if x["issue"] == 3734)
    envelope_raw = (ISSUE_DIR / item["filename"]).read_bytes()
    context_raw = (ISSUE_DIR / standalone["file"]).read_bytes()
    envelope = json.loads(envelope_raw)
    issue = IssueContext.model_validate_json(context_raw)
    if (summary["repository"] != REPOSITORY or envelope["repository"] != REPOSITORY
            or summary["repository_id"] != REPOSITORY_ID or envelope["repository_id"] != REPOSITORY_ID
            or summary["pinned_source_commit"] != COMMIT or envelope["pinned_source_commit"] != COMMIT
            or issue.number != 3734 or envelope["context"] != json.loads(context_raw)
            or hashlib.sha256(envelope_raw).hexdigest() != item["file_sha256"]
            or hashlib.sha256(context_raw).hexdigest() != standalone["file_sha256"]
            or context_digest(issue) != CONTEXT_SHA256 or item["context_sha256"] != CONTEXT_SHA256
            or standalone["context_sha256"] != CONTEXT_SHA256
            or envelope["context_sha256"] != CONTEXT_SHA256
            or issue.comments != sorted(issue.comments, key=lambda x: (x.created_at, x.id))):
        raise ValueError("issue_identity_or_fingerprint_mismatch")


def check_private_directory(directory):
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError("unsafe_private_directory")


def write_private(root, relative, data):
    parts = PurePosixPath(relative).parts
    if not parts or any(p in {"", ".", ".."} for p in parts) or relative.startswith("/"):
        raise ValueError("invalid_private_output_path")
    parent = root
    check_private_directory(parent)
    for part in parts[:-1]:
        parent = parent / part
        try:
            parent.mkdir(mode=0o700)
        except FileExistsError:
            pass
        check_private_directory(parent)
    path = parent / parts[-1]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    if stat.S_IMODE(path.lstat().st_mode) != 0o600:
        raise ValueError("unsafe_private_file")


def make_source_manifest(commit, trees, files):
    return {"version": "pinned-httpx-3734-source-review-v1", "repository": REPOSITORY,
            "issue": 3734, "issue_context_sha256": CONTEXT_SHA256, "commit": commit,
            "trees": trees, "files": sorted(files, key=lambda item: item["path"])}


def capture(reader, root):
    commit = validate_commit(reader.get("commits", COMMIT), COMMIT, ROOT_TREE)
    root_tree = validate_tree(reader.get("trees", ROOT_TREE), ROOT_TREE)
    httpx_entry = select_entry(root_tree, "httpx", "tree")
    httpx_tree = validate_tree(reader.get("trees", httpx_entry["sha"]), httpx_entry["sha"])
    transports_entry = select_entry(httpx_tree, "_transports", "tree")
    transports_tree = validate_tree(reader.get("trees", transports_entry["sha"]), transports_entry["sha"])
    selected = []
    for path in SELECTED_PATHS:
        name = PurePosixPath(path).name
        source_tree = transports_tree if path.startswith("httpx/_transports/") else httpx_tree
        selected.append({"path": path, **{key: value for key, value in select_entry(source_tree, name, "blob").items()
                                       if key in {"sha", "size", "mode"}}})
    expected_bytes = check_source_budget(selected)
    files = []
    for entry in selected:
        raw = validate_blob(reader.get("blobs", entry["sha"]), entry)
        write_private(root, "source/" + entry["path"], raw)
        files.append({"path": entry["path"], "git_blob_sha1": entry["sha"],
                      "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "mode": entry["mode"]})
    if sum(f["size"] for f in files) != expected_bytes:
        raise ValueError("source_accounting_mismatch")
    tree_ids = {"root": ROOT_TREE, "httpx": httpx_entry["sha"],
                "httpx/_transports": transports_entry["sha"]}
    source_manifest = make_source_manifest(commit, tree_ids, files)
    metadata = {"root": root_tree, "httpx": httpx_tree, "httpx/_transports": transports_tree}
    summary = {"source_manifest": source_manifest, "http_response_body_bytes": reader.total,
               "retained_source_bytes": expected_bytes, "requests": reader.requests,
               "retrieved_at": datetime.now(timezone.utc).isoformat()}
    write_private(root, "tree-metadata.json", canonical(metadata) + b"\n")
    write_private(root, "source-manifest.json", canonical(source_manifest) + b"\n")
    write_private(root, "capture-summary.json", canonical(summary) + b"\n")
    return summary


def test_git_blob_hash_matches_git_hash_object():
    raw = b"def example():\n    return 1\n"
    output = subprocess.check_output(["git", "hash-object", "--stdin"], input=raw,
                                     env={"PATH": "/usr/bin:/bin", "GIT_NO_REPLACE_OBJECTS": "1"})
    assert object_id("blob", raw) == output.decode().strip()


def test_tree_hash_matches_real_synthetic_git_fixture(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_NO_REPLACE_OBJECTS": "1", "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.test",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.test"}
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], env=env, stderr=subprocess.DEVNULL).decode().strip()
    git("init", "-q")
    (tmp_path / "httpx").mkdir()
    (tmp_path / "httpx" / "a.py").write_text("x = 1\n")
    git("add", "httpx/a.py")
    git("commit", "-qm", "fixture")
    parent = git("rev-parse", "HEAD")
    (tmp_path / "httpx" / "a.py").write_text("x = 2\n")
    git("add", "httpx/a.py")
    git("commit", "-qm", "second fixture commit")
    commit = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    subtree = git("rev-parse", "HEAD:httpx")
    commit_raw = subprocess.check_output(["git", "-C", str(tmp_path), "cat-file", "commit", commit], env=env)
    assert object_id("commit", commit_raw) == commit != parent
    assert validate_commit({"sha": commit, "tree": {"sha": tree}, "parents": [{"sha": parent}],
                            "committer": {"date": "2025-01-01T00:00:00Z"}}, commit, tree)["sha"] == commit
    with pytest.raises(ValueError, match="commit_or_tree_mismatch"):
        validate_commit({"sha": parent, "tree": {"sha": tree}}, commit, tree)
    root_data = {"sha": tree, "truncated": False, "tree": [{"path": "httpx", "type": "tree", "mode": "040000", "sha": subtree}]}
    assert validate_tree(root_data, tree)[0]["sha"] == subtree
    with pytest.raises(ValueError, match="tree_object_hash_mismatch"):
        validate_tree({**root_data, "tree": [{**root_data["tree"][0], "sha": "0" * 40}]}, tree)


def test_commit_and_cross_commit_mismatch_are_rejected():
    data = {"sha": "a" * 40, "tree": {"sha": "b" * 40}, "parents": [{"sha": "c" * 40}],
            "committer": {"date": "2025-01-01T00:00:00Z"}}
    assert validate_commit(data, "a" * 40, "b" * 40)["parents"] == ["c" * 40]
    with pytest.raises(ValueError, match="commit_or_tree_mismatch"):
        validate_commit(data, "d" * 40, "b" * 40)
    with pytest.raises(ValueError, match="commit_or_tree_mismatch"):
        validate_commit(data, "a" * 40, "e" * 40)


@pytest.mark.parametrize("path", ["../httpx/a.py", "httpx/../a.py", "httpx//a.py", "/httpx/a.py",
                                 "httpx/a.js", "httpx/secret.py", "other/a.py", "httpx/evil\\a.py"])
def test_path_rejection(path):
    with pytest.raises(ValueError, match="ineligible_source_path"):
        validate_path(path)


@pytest.mark.parametrize("mode,kind", [("120000", "blob"), ("160000", "commit")])
def test_symlink_and_gitlink_are_rejected(mode, kind):
    with pytest.raises(ValueError, match="unsupported_tree_entry"):
        validate_tree({"sha": "a" * 40, "truncated": False, "tree": [
            {"path": "x", "mode": mode, "type": kind, "sha": "b" * 40}]}, "a" * 40)


def test_blob_verification_and_binary_rejection():
    raw = b"print('synthetic')\n"
    entry = {"sha": object_id("blob", raw), "size": len(raw)}
    data = {"sha": entry["sha"], "size": len(raw), "encoding": "base64", "content": base64.b64encode(raw).decode()}
    assert validate_blob(data, entry) == raw
    with pytest.raises(ValueError, match="blob_object_hash_mismatch"):
        validate_blob({**data, "content": base64.b64encode(b"x" * len(raw)).decode()}, entry)
    binary = b"a\0b"
    with pytest.raises(ValueError, match="unsafe_or_invalid_source"):
        validate_blob({"sha": object_id("blob", binary), "size": len(binary), "encoding": "base64",
                       "content": base64.b64encode(binary).decode()}, {"sha": object_id("blob", binary), "size": len(binary)})


def test_source_byte_counting_and_limits():
    assert check_source_budget([{"path": "httpx/a.py", "size": 12}, {"path": "httpx/b.py", "size": 7}]) == 19
    with pytest.raises(ValueError, match="source_file_size"):
        check_source_budget([{"path": "httpx/a.py", "size": FILE_LIMIT + 1}])
    with pytest.raises(ValueError, match="source_aggregate_size"):
        check_source_budget([{"path": f"httpx/a{i}.py", "size": FILE_LIMIT} for i in range(51)])
    with pytest.raises(ValueError, match="source_file_count_or_identity"):
        check_source_budget([{"path": "httpx/a.py", "size": 1}] * 2)


def test_manifest_is_deterministic():
    one, two = {"path": "httpx/a.py"}, {"path": "httpx/b.py"}
    assert canonical(make_source_manifest({}, {}, [one, two])) == canonical(make_source_manifest({}, {}, [two, one]))


def test_private_storage_permissions_and_no_overwrite(tmp_path):
    tmp_path.chmod(0o700)
    write_private(tmp_path, "source/httpx/a.py", b"synthetic\n")
    path = tmp_path / "source/httpx/a.py"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    with pytest.raises(FileExistsError):
        write_private(tmp_path, "source/httpx/a.py", b"replacement")
    with pytest.raises(ValueError, match="invalid_private_output_path"):
        write_private(tmp_path, "../outside.py", b"x")


def test_complete_capture_with_synthetic_git_objects(tmp_path, monkeypatch):
    def blob(path, raw):
        sha = object_id("blob", raw)
        return ({"path": path, "mode": "100644", "type": "blob", "sha": sha, "size": len(raw)},
                {"sha": sha, "size": len(raw), "encoding": "base64", "content": base64.b64encode(raw).decode()})

    def tree(entries):
        ordered = sorted(entries, key=lambda e: e["path"].encode() + (b"/" if e["type"] == "tree" else b""))
        raw = b"".join(e["mode"].lstrip("0").encode() + b" " + e["path"].encode() + b"\0"
                       + bytes.fromhex(e["sha"]) for e in ordered)
        sha = object_id("tree", raw)
        return {"sha": sha, "truncated": False, "tree": entries}

    client, client_blob = blob("_client.py", b"class BoundSyncStream: pass\n")
    config, config_blob = blob("_config.py", b"def create_ssl_context(): pass\n")
    default, default_blob = blob("default.py", b"def transport(): pass\n")
    transports = tree([default])
    httpx = tree([client, config, {"path": "_transports", "mode": "040000", "type": "tree", "sha": transports["sha"]}])
    root = tree([{"path": "httpx", "mode": "040000", "type": "tree", "sha": httpx["sha"]}])
    synthetic_commit = "a" * 40
    monkeypatch.setitem(capture.__globals__, "COMMIT", synthetic_commit)
    monkeypatch.setitem(capture.__globals__, "ROOT_TREE", root["sha"])
    objects = {("commits", synthetic_commit): {"sha": synthetic_commit, "tree": {"sha": root["sha"]},
               "parents": [{"sha": "b" * 40}], "committer": {"date": "2025-01-01T00:00:00Z"}},
               ("trees", root["sha"]): root, ("trees", httpx["sha"]): httpx,
               ("trees", transports["sha"]): transports,
               ("blobs", client["sha"]): client_blob, ("blobs", config["sha"]): config_blob,
               ("blobs", default["sha"]): default_blob}

    class FakeReader:
        total = 0
        requests = []

        def get(self, kind, sha):
            data = objects[(kind, sha)]
            count = len(canonical(data))
            self.total += count
            self.requests.append({"kind": kind, "sha": sha, "response_body_bytes": count})
            return data

    tmp_path.chmod(0o700)
    result = capture(FakeReader(), tmp_path)
    assert len(result["requests"]) == 7
    assert result["http_response_body_bytes"] == sum(r["response_body_bytes"] for r in result["requests"])
    assert result["retained_source_bytes"] == sum(f["size"] for f in result["source_manifest"]["files"])
    assert {item["path"] for item in result["source_manifest"]["files"]} == set(SELECTED_PATHS)
    assert (tmp_path / "source/httpx/_config.py").read_bytes() == b"def create_ssl_context(): pass\n"


def test_network_budget_is_checked_before_response_body_is_read(monkeypatch):
    from email.message import Message

    class Response:
        status = 200
        def __init__(self, url):
            self.url = url
            self.headers = Message()
            self.headers["Content-Type"] = "application/json"
            self.headers["Content-Length"] = "10"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def geturl(self):
            return self.url
        def read(self, size):
            raise AssertionError("over-budget response must not be read")

    class Opener:
        def open(self, request, timeout):
            return Response(request.full_url)

    reader = GitHubReader()
    reader.opener = Opener()
    reader.total = NETWORK_LIMIT - 5
    with pytest.raises(ValueError, match="network_budget"):
        reader.get("trees", "a" * 40)


def test_no_model_import_or_inference_in_collector():
    # The capture module uses only Git/HTTP and source validation; it never imports a model runtime.
    import ast
    tree = ast.parse(Path(__file__).read_text())
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imported.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert not any(name and ("onnx" in name or "embedding" in name) for name in imported)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] != ["--capture"]:
        raise SystemExit("Explicit --capture is required")
    os.umask(0o077)
    validate_issue_record()
    check_private_directory(STORAGE)
    check_private_directory(STORAGE.parent)
    review_dir = STORAGE / ("httpx-3734-source-review-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                            + "-" + secrets.token_hex(4))
    review_dir.mkdir(mode=0o700)
    try:
        result = capture(GitHubReader(), review_dir)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r"[a-z0-9_]+", str(exc)) else "capture_failed"
        print(json.dumps({"status": "STOP", "error_type": type(exc).__name__,
                          "reason": reason,
                          "private_directory": str(review_dir)}))
        raise SystemExit(1) from None
    print(json.dumps({"status": "PASS", "private_directory": str(review_dir),
                      "http_response_body_bytes": result["http_response_body_bytes"],
                      "retained_source_bytes": result["retained_source_bytes"],
                      "source_manifest": result["source_manifest"]}, sort_keys=True))
