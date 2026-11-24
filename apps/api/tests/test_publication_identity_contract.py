"""Synthetic publication identities differ while source processing remains stable."""

from datetime import timedelta
from hashlib import sha1
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.domain.models import (
    AuthSession,
    CodeChunk,
    CodeSnapshot,
    IndexedFile,
    Installation,
    InvestigationEvidence,
    InvestigationJob,
    Repository,
    SnapshotPublication,
    Tenant,
    now,
)
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.code_collect import collect_source
from app.modules.ingestion.code_persistence import publish_snapshot
from app.modules.ingestion.code_snapshot import Candidate, SnapshotPlan
from app.modules.investigation.retrieval import InvalidEvidence, fingerprint_chunk, load_verified_evidence

SOURCE = 'package p\r\nimport "fmt"\r\n// café\r\nfunc greet() { fmt.Println("hi") }\r\n'.encode()
PATH = "src/greet.go"
BLOB = sha1(b"blob " + str(len(SOURCE)).encode() + b"\0" + SOURCE).hexdigest()


class SyntheticBlob:
    def blob(self, token, full_name, blob_sha, expected_size):
        assert (token, full_name, blob_sha, expected_size) == ("fixture", "demo/repopilot-sandbox", BLOB, len(SOURCE))
        return SOURCE


@pytest.fixture
def publication_pair(factory):
    source = SyntheticBlob()
    plans = [
        SnapshotPlan(commit * 40, (Candidate(PATH, BLOB, len(SOURCE)),), multilingual=True)
        for commit in ("a", "b")
    ]
    collections = [collect_source(source, "fixture", "demo/repopilot-sandbox", plan) for plan in plans]
    assert collections[0] == collections[1]
    assert collections[0].files[0].parser_status == "parsed"
    snapshot_ids = []
    for plan, collection in zip(plans, collections):
        with factory.begin() as db:
            snapshot = publish_snapshot(db, db.get(Repository, 2001), plan, collection)
            snapshot_ids.append(snapshot.id)
    return tuple(snapshot_ids)


def snapshot_contents(db, snapshot_id):
    snapshot = db.get(CodeSnapshot, snapshot_id)
    file = db.scalar(select(IndexedFile).where(IndexedFile.snapshot_id == snapshot_id))
    chunks = db.scalars(select(CodeChunk).where(CodeChunk.file_id == file.id).order_by(CodeChunk.start_line)).all()
    publication = db.get(SnapshotPublication, snapshot_id)
    return snapshot, file, chunks, publication


def test_republication_preserves_processing_but_not_opaque_ids(factory, publication_pair):
    with factory() as db:
        first = snapshot_contents(db, publication_pair[0])
        second = snapshot_contents(db, publication_pair[1])
        first_snapshot, first_file, first_chunks, first_publication = first
        second_snapshot, second_file, second_chunks, second_publication = second
        assert not first_snapshot.published and second_snapshot.published
        assert first_publication.commit_sha == "a" * 40
        assert second_publication.commit_sha == "b" * 40
        assert (first_file.path, first_file.content_hash, first_file.language, first_file.parser_version,
                first_file.parser_status, first_file.import_ranges) == (
                    second_file.path, second_file.content_hash, second_file.language, second_file.parser_version,
                    second_file.parser_status, second_file.import_ranges)
        assert [(c.symbol, c.symbol_kind, c.start_line, c.end_line, c.source_text) for c in first_chunks] == [
            (c.symbol, c.symbol_kind, c.start_line, c.end_line, c.source_text) for c in second_chunks]
        assert first_chunks and len(first_chunks) == len(second_chunks)
        ids = [first_snapshot.id, second_snapshot.id, first_file.id, second_file.id]
        ids += [chunk.id for chunk in first_chunks + second_chunks]
        assert len(ids) == len(set(ids)) and all(UUID(value).version == 4 for value in ids)
        for left, right in zip(first_chunks, second_chunks):
            assert (left.file_id, left.repository_id, left.tenant_id) == (first_file.id, 2001, first_file.tenant_id)
            assert (right.file_id, right.repository_id, right.tenant_id) == (second_file.id, 2001, second_file.tenant_id)
            assert fingerprint_chunk(left, first_file) == fingerprint_chunk(left, first_file)
            assert fingerprint_chunk(left, first_file) != fingerprint_chunk(right, second_file)
            left_url = github_citation("demo/repopilot-sandbox", first_snapshot.commit_sha, first_file.path,
                                       left.start_line, left.end_line)
            right_url = github_citation("demo/repopilot-sandbox", second_snapshot.commit_sha, second_file.path,
                                        right.start_line, right.end_line)
            assert left_url.endswith(f"/{'a' * 40}/{PATH}#L{left.start_line}-L{left.end_line}")
            assert right_url.endswith(f"/{'b' * 40}/{PATH}#L{right.start_line}-L{right.end_line}")


def test_publication_ownership_rejects_cross_tenant_file_and_chunk(factory, publication_pair):
    with factory.begin() as db:
        other_tenant_id = db.get(Repository, 2001).tenant_id + 1_000_000
        db.add(Tenant(id=other_tenant_id, name="Other synthetic tenant"))
        db.flush()
        db.add(Installation(id=1002, tenant_id=other_tenant_id, active=True))
        db.flush()
        db.add(Repository(id=2002, tenant_id=other_tenant_id, installation_id=1002,
                          full_name="other/synthetic", enabled=True))
    with factory() as db:
        _, first_file, _, _ = snapshot_contents(db, publication_pair[0])
        file_id = first_file.id
    with pytest.raises(IntegrityError), factory.begin() as db:
        db.add(IndexedFile(id=str(uuid4()), snapshot_id=publication_pair[0], repository_id=2002,
                           tenant_id=other_tenant_id,
                           path=PATH, content_hash="a" * 64))
        db.flush()
    with pytest.raises(IntegrityError), factory.begin() as db:
        db.add(CodeChunk(id=str(uuid4()), file_id=file_id, repository_id=2002, tenant_id=other_tenant_id,
                         start_line=1, end_line=1, source_text="synthetic"))
        db.flush()


def test_evidence_rejects_chunk_from_other_snapshot_in_same_repository(factory, publication_pair):
    with factory.begin() as db:
        first_snapshot, first_file, first_chunks, _ = snapshot_contents(db, publication_pair[0])
        _, second_file, second_chunks, _ = snapshot_contents(db, publication_pair[1])
        session_id = "f" * 64
        db.add(AuthSession(id_hash=session_id, user_id=get_settings().demo_user_id, tenant_id=first_snapshot.tenant_id,
                           github_token_ciphertext="synthetic", csrf_hash="e" * 64,
                           expires_at=now() + timedelta(hours=1)))
        db.flush()
        job = InvestigationJob(id=str(uuid4()), repository_id=2001, tenant_id=first_snapshot.tenant_id,
                               user_id=get_settings().demo_user_id, session_hash=session_id, issue_id=1, issue_number=1,
                               operation="code_evidence", snapshot_id=first_snapshot.id,
                               snapshot_commit_sha=first_snapshot.commit_sha,
                               source_repository_name="demo/repopilot-sandbox",
                               query_version="terms-v2", query_limit=1, per_query_limit=10, evidence_limit=10,
                               query_body_limit=100, issue_updated_at=now(), context_retrieved_at=now(),
                               status="running")
        db.add(job)
        db.flush()
        evidence = InvestigationEvidence(id=str(uuid4()), job_id=job.id, snapshot_id=first_snapshot.id,
                                         repository_id=2001, tenant_id=first_snapshot.tenant_id,
                                         chunk_id=second_chunks[0].id, rank=1, query_id="fixture",
                                         query_hash="d" * 64, chunk_fingerprint=fingerprint_chunk(second_chunks[0],
                                                                                                  second_file),
                                         query_rank=1, method="keyword")
        db.add(evidence)
        db.flush()
        with pytest.raises(InvalidEvidence):
            load_verified_evidence(db, job, first_snapshot)
        evidence.chunk_id = first_chunks[0].id
        evidence.chunk_fingerprint = fingerprint_chunk(first_chunks[0], first_file)
        db.flush()
        rows = load_verified_evidence(db, job, first_snapshot)
        assert len(rows) == 1 and rows[0][1].id == first_chunks[0].id
