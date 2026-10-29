import pytest

from app.modules.ingestion.code_snapshot import SnapshotError, plan_snapshot


class FakeSource:
    def __init__(self):
        self.meta = {"full_name": "alice/example", "private": False, "default_branch": "main"}
        self.entries = [{"path": "src/app.py", "type": "blob", "mode": "100644",
                         "sha": "b" * 40, "size": 10}]
        self.truncated = False

    def repository(self, token, full_name):
        return self.meta

    def commit(self, token, full_name, branch):
        assert branch == "main"
        return {"sha": "a" * 40}

    def tree(self, token, full_name, sha):
        assert sha == "a" * 40
        return {"truncated": self.truncated, "tree": self.entries}


def test_public_snapshot_is_pinned_and_excludes_symlinks_and_generated_files():
    client = FakeSource()
    client.entries += [{"path": "node_modules/a.py", "type": "blob", "mode": "100644"},
                       {"path": "link.py", "type": "blob", "mode": "120000"}]
    plan = plan_snapshot(client, "token", "alice/example")
    assert plan.commit_sha == "a" * 40
    assert [item.path for item in plan.files] == ["src/app.py"]


def test_truncated_tree_and_private_repository_fail_closed():
    client = FakeSource()
    client.truncated = True
    with pytest.raises(SnapshotError, match="incomplete_tree"):
        plan_snapshot(client, "token", "alice/example")
    client.meta["private"] = True
    with pytest.raises(SnapshotError, match="repository_not_public_or_moved"):
        plan_snapshot(client, "token", "alice/example")


def test_snapshot_limits_and_invalid_entries_are_not_silently_complete():
    client = FakeSource()
    client.entries *= 2
    with pytest.raises(SnapshotError, match="tree_limit_exceeded"):
        plan_snapshot(client, "token", "alice/example", max_entries=1)
    with pytest.raises(SnapshotError, match="invalid_tree_entry"):
        plan_snapshot(client, "token", "alice/example")
