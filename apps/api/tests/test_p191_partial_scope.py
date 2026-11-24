"""Synthetic scoped partial snapshot persistence and fail-closed read checks."""
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, InvestigationJob, Repository
from app.modules.ingestion.code_collect import collect_source
from app.modules.ingestion.code_persistence import bind_partial_snapshot, persist_partial_snapshot, revoke_snapshot
from app.modules.investigation.retrieval import SnapshotUnavailable, readable_snapshot, validate_snapshot
from test_auth_enrollment import github_auth as github_auth
from test_investigation_evidence import context, submit
from test_partial_snapshot import fixture


def partial_setup(client, factory, github):
    old_snapshot, _ = context(client, factory, github)
    job_id = submit(client)
    args = fixture()
    with factory.begin() as db:
        job = db.get(InvestigationJob, job_id)
        repo = db.get(Repository, job.repository_id)
        snapshot = persist_partial_snapshot(db, repo, args["plan"], args["collection"])
        job.snapshot_id, job.snapshot_commit_sha = snapshot.id, snapshot.commit_sha
        db.flush()
        bind_partial_snapshot(db, job, snapshot)
        snapshot_id = snapshot.id
    return job_id, snapshot_id, old_snapshot


def test_partial_scope_revalidates_bytes_and_preserves_current_snapshot(client, factory, github_auth):
    job_id, snapshot_id, old_id = partial_setup(client, factory, github_auth)
    with factory() as db:
        job = db.get(InvestigationJob, job_id)
        assert db.get(CodeSnapshot, old_id).published is True
        assert validate_snapshot(db, snapshot_id=snapshot_id, repository_id=902, tenant_id=job.tenant_id,
            commit="a" * 40, job_id=job_id).inventory_coverage == "PARTIAL_INVENTORY"
        assert readable_snapshot(db, job).id == snapshot_id
        for wrong in (None, str(uuid4())):
            with pytest.raises(SnapshotUnavailable):
                validate_snapshot(db, snapshot_id=snapshot_id, repository_id=902, tenant_id=job.tenant_id,
                    commit="a" * 40, job_id=wrong)
        with pytest.raises(SnapshotUnavailable):
            validate_snapshot(db, snapshot_id=snapshot_id, repository_id=902, tenant_id=job.tenant_id + 1,
                commit="a" * 40, job_id=job_id)
        with pytest.raises(SnapshotUnavailable):
            validate_snapshot(db, snapshot_id=snapshot_id, repository_id=902, tenant_id=job.tenant_id,
                commit="b" * 40, job_id=job_id)


@pytest.mark.parametrize("tamper", ["bytes", "length", "manifest", "missing_file", "missing_chunk"])
def test_partial_scope_rejects_changed_or_missing_inventory(client, factory, github_auth, tamper):
    job_id, snapshot_id, _ = partial_setup(client, factory, github_auth)
    with factory.begin() as db:
        snapshot = db.get(CodeSnapshot, snapshot_id)
        file = db.scalar(select(IndexedFile).where(IndexedFile.snapshot_id == snapshot_id))
        chunk = db.scalar(select(CodeChunk).where(CodeChunk.file_id == file.id))
        if tamper == "bytes":
            chunk.source_text = chunk.source_text.replace("1", "9").replace("2", "9")
        elif tamper == "length":
            file.source_byte_length += 1
        elif tamper == "manifest":
            snapshot.inventory_manifest = {**snapshot.inventory_manifest, "commit_sha": "f" * 40}
        elif tamper == "missing_file":
            db.delete(chunk)
            db.flush()
            db.delete(file)
        else:
            db.delete(chunk)
    with factory() as db:
        job = db.get(InvestigationJob, job_id)
        with pytest.raises(SnapshotUnavailable):
            validate_snapshot(db, snapshot_id=snapshot_id, repository_id=902, tenant_id=job.tenant_id,
                commit="a" * 40, job_id=job_id)


def test_text_only_collection_never_calls_parser(monkeypatch):
    args = fixture()
    class Blob:
        def blob(self, token, full_name, blob_sha, expected_size):
            for candidate, item in zip(args["plan"].files, args["collection"].files, strict=True):
                if candidate.blob_sha == blob_sha:
                    return "".join(chunk.text for chunk in item.chunks).encode()
            raise AssertionError("unexpected blob")
    def no_parser(*args, **kwargs):
        raise AssertionError("native parser must not run")
    monkeypatch.setattr("app.modules.ingestion.code_collect.analyze_source", no_parser)
    result = collect_source(Blob(), "test-token", "example/synthetic", args["plan"], text_only=True)
    assert len(result.files) == 2 and all(file.parser_status == "explicit_text_only" for file in result.files)
    assert all(file.source_coverage == "COMPLETE_FILE" for file in result.files)
    with pytest.raises(ValueError, match="invalid_text_only_mode"):
        collect_source(Blob(), "test-token", "example/synthetic", args["plan"], text_only=True, supervised=True)


def test_partial_scope_uses_existing_revocation_fence(client, factory, github_auth):
    job_id, snapshot_id, old_id = partial_setup(client, factory, github_auth)
    with factory.begin() as db:
        repo = db.get(Repository, 902)
        revoke_snapshot(db, repo, snapshot_id, "security")
    with factory() as db:
        job = db.get(InvestigationJob, job_id)
        assert db.get(CodeSnapshot, old_id).published is True
        with pytest.raises(SnapshotUnavailable):
            validate_snapshot(db, snapshot_id=snapshot_id, repository_id=902, tenant_id=job.tenant_id,
                commit="a" * 40, job_id=job_id)
        with pytest.raises(SnapshotUnavailable):
            readable_snapshot(db, job)
