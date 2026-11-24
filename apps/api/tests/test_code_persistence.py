import pytest
from hashlib import sha256
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, Repository
from app.modules.ingestion.code_chunking import chunk_python
from app.modules.ingestion.code_collect import CollectedFile, Collection, collect_source
from app.modules.ingestion.code_persistence import publish_snapshot
from app.modules.ingestion.code_snapshot import Candidate, SnapshotPlan


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


def test_verified_synthetic_file_provenance_persists_and_legacy_stays_unknown(factory):
    source = "def total(a, b):\n    return a + b\n"
    raw = source.encode("utf-8")
    class SyntheticBlob:
        def blob(self, token, full_name, sha, expected_size):
            assert (token, full_name, sha, expected_size) == ("synthetic-token", "synthetic/repo",
                                                             "synthetic-blob", len(raw))
            return raw
    collected = collect_source(SyntheticBlob(), "synthetic-token", "synthetic/repo",
                               SnapshotPlan("e" * 40, (Candidate("total.py", "synthetic-blob", len(raw)),)))
    complete = collected.files[0]
    digest = sha256(raw).hexdigest()
    assert complete.source_coverage == "COMPLETE_FILE"
    assert complete.source_byte_length == len(raw)
    assert complete.content_hash == digest
    legacy = CollectedFile("legacy.py", "b" * 64, tuple(chunk_python(source)))
    collection = Collection((complete, legacy), 0, len(raw) * 2)
    with factory.begin() as db:
        repo = db.get(Repository, 2001)
        snapshot = publish_snapshot(db, repo, SnapshotPlan("e" * 40, ()), collection)
        snapshot_id = snapshot.id
    with factory() as db:
        files = {item.path: item for item in db.scalars(select(IndexedFile)).all()}
        saved = files["total.py"]
        assert (saved.source_byte_length, saved.source_encoding, saved.source_normalization,
                saved.source_coverage, saved.content_hash) == (len(source.encode()), "utf-8", "identity",
                                                               "COMPLETE_FILE", digest)
        old = files["legacy.py"]
        assert old.source_byte_length is None and old.source_coverage == "UNKNOWN_COVERAGE"
        assert db.get(CodeSnapshot, snapshot_id).file_count == 2


@pytest.mark.parametrize("declared_length,declared_hash", [(999, None), (None, "f" * 64)])
def test_complete_source_provenance_rejects_mismatched_bytes(factory, declared_length, declared_hash):
    source = "def total(a, b):\n    return a + b\n"
    actual_hash = sha256(source.encode()).hexdigest()
    file = CollectedFile(
        "total.py", declared_hash or actual_hash, tuple(chunk_python(source)),
        source_byte_length=declared_length if declared_length is not None else len(source.encode()),
        source_encoding="utf-8", source_normalization="identity", source_coverage="COMPLETE_FILE",
    )
    with factory() as db:
        existing_count = len(db.scalars(select(CodeSnapshot)).all())
    with factory.begin() as db:
        with pytest.raises(ValueError, match="source_provenance_identity_mismatch"):
            publish_snapshot(db, db.get(Repository, 2001), SnapshotPlan("e" * 40, ()),
                             Collection((file,), 0, len(source.encode())))
    with factory() as db:
        assert len(db.scalars(select(CodeSnapshot)).all()) == existing_count


def test_database_constraint_rejects_complete_identity_with_null_byte_length(factory):
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            snapshot = CodeSnapshot(id="synthetic-provenance-snapshot", repository_id=2001,
                                   tenant_id=1, commit_sha="f" * 40, published=False)
            db.add(snapshot)
            db.flush()
            db.add(IndexedFile(id="synthetic-provenance-file", snapshot_id=snapshot.id,
                               repository_id=2001, tenant_id=1, path="total.py",
                               content_hash="a" * 64, source_coverage="COMPLETE_FILE",
                               source_byte_length=None, source_encoding="utf-8",
                               source_normalization="identity"))
            db.flush()
