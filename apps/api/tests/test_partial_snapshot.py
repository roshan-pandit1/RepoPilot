from dataclasses import replace
from hashlib import sha1, sha256

import pytest

from app.modules.ingestion.code_chunking import SourceChunk
from app.modules.ingestion.code_collect import CollectedFile, Collection
from app.modules.ingestion.code_snapshot import Candidate, SnapshotPlan
from app.modules.ingestion.partial_snapshot import (
    PARTIAL_INVENTORY, PartialSnapshotError, build_partial_manifest, plan_pinned_partial, verify_partial_manifest,
)


def make_file(path, raw):
    blob = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    candidate = Candidate(path, blob, len(raw))
    source = raw.decode("utf-8")
    chunk = SourceChunk(1, source.count("\n"), None, source)
    item = CollectedFile(path, sha256(raw).hexdigest(), (chunk,), source_byte_length=len(raw),
                         source_encoding="utf-8", source_normalization="identity", source_coverage="COMPLETE_FILE")
    return candidate, item


def fixture():
    a, first = make_file("src/alpha.ts", b"export const alpha = 1;\n")
    b, second = make_file("src/beta.ts", b"export const beta = 2;\n")
    plan = SnapshotPlan("a" * 40, (b, a), multilingual=True)
    collection = Collection((second, first), 0, a.size + b.size)
    return {"repository_id": 123, "tenant_id": 7, "repository_full_name": "example/synthetic",
            "plan": plan, "collection": collection}


def test_partial_manifest_is_canonical_and_binds_verified_complete_files():
    args = fixture()
    manifest, digest = build_partial_manifest(**args)
    assert manifest["inventory_coverage"] == PARTIAL_INVENTORY
    assert [f["path"] for f in manifest["files"]] == ["src/alpha.ts", "src/beta.ts"]
    assert all(f["coverage"] == "COMPLETE_FILE" for f in manifest["files"])
    reordered = {**args, "plan": replace(args["plan"], files=tuple(reversed(args["plan"].files))),
                 "collection": replace(args["collection"], files=tuple(reversed(args["collection"].files)))}
    assert build_partial_manifest(**reordered) == (manifest, digest)
    verify_partial_manifest(expected_manifest=manifest, expected_sha256=digest, **args)
    assert "export const" not in str(manifest)


def test_manifest_detects_tampering_and_wrong_identity():
    args = fixture()
    manifest, digest = build_partial_manifest(**args)
    for changed in ({**manifest, "commit_sha": "b" * 40},
                    {**manifest, "inventory_coverage": "COMPLETE_INVENTORY"}):
        with pytest.raises(PartialSnapshotError, match="partial_manifest_mismatch"):
            verify_partial_manifest(expected_manifest=changed, expected_sha256=digest, **args)
    with pytest.raises(PartialSnapshotError, match="partial_manifest_mismatch"):
        verify_partial_manifest(expected_manifest=manifest, expected_sha256="f" * 64, **args)
    with pytest.raises(PartialSnapshotError, match="partial_manifest_mismatch"):
        verify_partial_manifest(expected_manifest=manifest, expected_sha256=digest, **{**args, "tenant_id": 8})


@pytest.mark.parametrize("change", ["missing", "duplicate", "path", "blob", "length", "hash", "coverage", "range", "source", "skipped", "commit"])
def test_partial_manifest_rejects_incomplete_or_inconsistent_sources(change):
    args = fixture()
    plan, collection = args["plan"], args["collection"]
    candidate, item = plan.files[0], collection.files[0]
    if change == "missing":
        collection = replace(collection, files=collection.files[:1])
    elif change == "duplicate":
        plan = replace(plan, files=(candidate, candidate))
    elif change == "path":
        plan = replace(plan, files=(replace(candidate, path="../escape.ts"), plan.files[1]))
    elif change == "blob":
        plan = replace(plan, files=(replace(candidate, blob_sha="f" * 40), plan.files[1]))
    elif change == "length":
        collection = replace(collection, files=(replace(item, source_byte_length=0), collection.files[1]))
    elif change == "hash":
        collection = replace(collection, files=(replace(item, content_hash="f" * 64), collection.files[1]))
    elif change == "coverage":
        collection = replace(collection, files=(replace(item, source_coverage="UNKNOWN_COVERAGE"), collection.files[1]))
    elif change == "range":
        chunk = replace(item.chunks[0], start_line=2)
        collection = replace(collection, files=(replace(item, chunks=(chunk,)), collection.files[1]))
    elif change == "source":
        chunk = replace(item.chunks[0], text="export const beta = 3;\n")
        collection = replace(collection, files=(replace(item, chunks=(chunk,)), collection.files[1]))
    elif change == "skipped":
        collection = replace(collection, skipped_files=1)
    else:
        plan = replace(plan, commit_sha="wrong")
    with pytest.raises(PartialSnapshotError):
        build_partial_manifest(**{**args, "plan": plan, "collection": collection})


class FakeSource:
    def __init__(self):
        self.metadata = {"id": 123, "private": False, "full_name": "example/synthetic", "default_branch": "main"}
        self.pinned = "a" * 40
        self.head = self.pinned
        self.ancestor = True
        self.calls = []

    def repository(self, token, name):
        return self.metadata

    def commit(self, token, name, ref):
        return {"sha": self.head if ref == "main" else self.pinned}

    def is_ancestor(self, token, name, pinned, head):
        self.calls.append(("ancestor", pinned, head))
        return self.ancestor

    def tree_file(self, token, name, commit, path):
        self.calls.append(("tree_file", commit, path))
        return {"path": path, "sha": "b" * 40, "size": 24}


def test_pinned_partial_plan_fetches_only_explicit_sorted_files():
    client = FakeSource()
    plan = plan_pinned_partial(client, "token", repository_id=123, repository_full_name="example/synthetic",
        commit_sha="a" * 40, paths=("src/b.ts", "src/a.ts"))
    assert plan.commit_sha == "a" * 40
    assert [item.path for item in plan.files] == ["src/a.ts", "src/b.ts"]
    assert client.calls[1:] == [("tree_file", "a" * 40, "src/a.ts"), ("tree_file", "a" * 40, "src/b.ts")]


@pytest.mark.parametrize("change", ["wrong_id", "private", "wrong_branch", "not_ancestor", "traversal", "duplicate", "non_string"])
def test_pinned_partial_plan_rejects_untrusted_scope(change):
    client = FakeSource()
    args = {"repository_id": 123, "repository_full_name": "example/synthetic", "commit_sha": "a" * 40,
            "paths": ("src/a.ts",)}
    if change == "wrong_id":
        client.metadata["id"] = 124
    elif change == "private":
        client.metadata["private"] = True
    elif change == "wrong_branch":
        client.metadata["default_branch"] = "other"
    elif change == "not_ancestor":
        client.ancestor = False
    elif change == "traversal":
        args["paths"] = ("../escape.ts",)
    elif change == "duplicate":
        args["paths"] = ("src/a.ts", "src/a.ts")
    else:
        args["paths"] = ([],)
    with pytest.raises(PartialSnapshotError):
        plan_pinned_partial(client, "token", **args)
    assert not any(call[0] == "tree_file" for call in client.calls)


def test_nonrecursive_tree_resolution_follows_only_regular_file_path():
    from app.modules.github.source_client import GitHubSourceClient
    client = GitHubSourceClient()
    client._trees[("example/synthetic", "a" * 40)] = "b" * 40
    calls = []
    trees = {
        "b" * 40: {"sha": "b" * 40, "truncated": False, "tree": [
            {"path": "src", "type": "tree", "mode": "040000", "sha": "c" * 40}]},
        "c" * 40: {"sha": "c" * 40, "truncated": False, "tree": [
            {"path": "a.ts", "type": "blob", "mode": "100644", "sha": "d" * 40, "size": 24}]},
    }
    def fake_get(path, token, **kwargs):
        calls.append(path)
        return trees[path.rsplit("/", 1)[-1]]
    client._get = fake_get
    assert client.tree_file("token", "example/synthetic", "a" * 40, "src/a.ts") == {
        "path": "src/a.ts", "sha": "d" * 40, "size": 24}
    assert len(calls) == 2 and all("recursive" not in path for path in calls)


@pytest.mark.parametrize("change", ["symlink", "truncated", "missing", "wrong_tree", "duplicate", "path_traversal"])
def test_nonrecursive_tree_resolution_rejects_unsafe_entries(change):
    from app.modules.github.client import GitHubFailure
    from app.modules.github.source_client import GitHubSourceClient
    client = GitHubSourceClient()
    client._trees[("example/synthetic", "a" * 40)] = "b" * 40
    entry = {"path": "a.ts", "type": "blob", "mode": "100644", "sha": "d" * 40, "size": 24}
    tree = {"sha": "b" * 40, "truncated": False, "tree": [entry]}
    if change == "symlink":
        entry["mode"] = "120000"
    elif change == "truncated":
        tree["truncated"] = True
    elif change == "missing":
        tree["tree"] = []
    elif change == "wrong_tree":
        tree["sha"] = "f" * 40
    elif change == "duplicate":
        tree["tree"] = [entry, dict(entry)]
    client._get = lambda *args, **kwargs: tree
    path = "../a.ts" if change == "path_traversal" else "a.ts"
    with pytest.raises(GitHubFailure):
        client.tree_file("token", "example/synthetic", "a" * 40, path)
