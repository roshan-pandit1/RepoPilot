import pytest
from sqlalchemy import select

from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, Repository
from app.modules.ingestion.code_chunking import chunk_python
from app.modules.ingestion.code_collect import CollectedFile, Collection
from app.modules.ingestion.code_persistence import publish_snapshot
from app.modules.ingestion.code_snapshot import SnapshotPlan


def test_snapshot_publication_and_rollback_preserve_previous(factory):
    plan = SnapshotPlan("a" * 40, ())
    source = "def hello():\n    return 42\n"
    collection = Collection((CollectedFile("hello.py", "b" * 64, tuple(chunk_python(source))),), 0, len(source))
    with factory.begin() as db:
        repo = db.get(Repository, 2001)
        first = publish_snapshot(db, repo, plan, collection)
        first_id = first.id
    with factory() as db:
        assert db.scalar(select(CodeChunk)).symbol == "hello"
        assert db.scalar(select(IndexedFile)).path == "hello.py"
        assert db.get(CodeSnapshot, first_id).published
    with pytest.raises(RuntimeError), factory.begin() as db:
        publish_snapshot(db, db.get(Repository, 2001), SnapshotPlan("c" * 40, ()), collection)
        raise RuntimeError("simulate interruption")
    with factory() as db:
        assert db.get(CodeSnapshot, first_id).published
        assert len(db.scalars(select(CodeSnapshot)).all()) == 1
