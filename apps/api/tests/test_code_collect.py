import pytest

from app.modules.ingestion.code_collect import CollectionError, collect_source
from app.modules.ingestion.code_snapshot import Candidate, SnapshotPlan


class Blobs:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def blob(self, token, full_name, sha, expected_size):
        self.calls.append(sha)
        return self.data[sha]


def test_rejected_secret_file_is_not_retained():
    safe = b"def ok():\n    return 42\n"
    secret = b"key = '" + b"ghp_" + b"a" * 36 + b"'\n"
    client = Blobs({"a": safe, "b": secret})
    plan = SnapshotPlan("c" * 40, (Candidate("ok.py", "a", len(safe)),
                                   Candidate("config.py", "b", len(secret))))
    result = collect_source(client, "token", "alice/repo", plan)
    assert [f.path for f in result.files] == ["ok.py"]
    assert result.skipped_files == 1
    assert result.fetched_bytes == len(safe) + len(secret)
    assert "ghp_" not in repr(result)


def test_total_limit_stops_before_fetching_extra_file():
    client = Blobs({"a": b"abc", "b": b"def"})
    plan = SnapshotPlan("c" * 40, (Candidate("a.py", "a", 3), Candidate("b.py", "b", 3)))
    with pytest.raises(CollectionError, match="source_byte_limit_exceeded"):
        collect_source(client, "token", "alice/repo", plan, max_total_bytes=5)
    assert client.calls == ["a"]
