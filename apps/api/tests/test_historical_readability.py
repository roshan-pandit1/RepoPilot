"""Historical evidence requires trusted publication and an intact completion manifest."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.domain.models import (CodeChunk, CodeSnapshot, InvestigationEvidence, InvestigationEvidenceManifest,
                               InvestigationJob, InvestigationReport, Repository, SnapshotPublication, now)
from app.modules.ingestion.code_persistence import revoke_snapshot
from app.modules.investigation.report_worker import process_report
from app.workers.tasks import process_investigation
from test_auth_enrollment import csrf, github_auth as github_auth, sign_in
from test_investigation_evidence import context, stub_retrieval, submit
from test_investigation_reports import report_url, request_report


def prepared(client, factory, github, monkeypatch, *, skipped=0, publication=True, report=False):
    snapshot_id, chunk_id = context(client, factory, github)
    with factory.begin() as db:
        snapshot = db.get(CodeSnapshot, snapshot_id)
        snapshot.file_count, snapshot.chunk_count, snapshot.skipped_count = 1, 1, skipped
        if publication:
            db.add(SnapshotPublication(snapshot_id=snapshot.id, repository_id=902, tenant_id=snapshot.tenant_id,
                commit_sha=snapshot.commit_sha, file_count=1, chunk_count=1, skipped_count=skipped))
    stub_retrieval(monkeypatch, factory, chunk_id)
    job_id = submit(client)
    process_investigation(job_id, factory, github)
    if report:
        report_job = request_report(client, job_id)
        process_report(report_job, factory, github)
        assert client.get(report_url(job_id)).status_code == 200
    return job_id, snapshot_id, chunk_id


def supersede(factory, snapshot_id):
    with factory.begin() as db:
        old = db.get(CodeSnapshot, snapshot_id)
        old.published = False
        db.flush()
        db.add(CodeSnapshot(id=str(uuid4()), repository_id=old.repository_id, tenant_id=old.tenant_id,
                            commit_sha='b' * 40, published=True))


@pytest.mark.parametrize('skipped', [0, 1])
def test_completed_historical_evidence_and_report(client, factory, github_auth, monkeypatch, skipped):
    job, snapshot, _ = prepared(client, factory, github_auth, monkeypatch, skipped=skipped, report=True)
    supersede(factory, snapshot)
    status = client.get(f'/v1/repositories/902/investigations/{job}')
    evidence = client.get(f'/v1/repositories/902/investigations/{job}/evidence?include_snippets=true')
    report = client.get(report_url(job))
    assert status.status_code == evidence.status_code == report.status_code == 200
    assert status.json()['snapshot_partial'] is bool(skipped)
    assert evidence.json()['items'][0]['url'].endswith('/src/tasks.py#L7-L8')
    assert report.json()['report']['snapshot_partial'] is bool(skipped)
    assert client.post(report_url(job), headers=csrf(client)).status_code == 409


@pytest.mark.parametrize('damage', ['missing', 'changed', 'count', 'digest', 'commit', 'revoked', 'metadata'])
def test_historical_tampering_fails_closed(client, factory, github_auth, monkeypatch, damage):
    job, snapshot, chunk = prepared(client, factory, github_auth, monkeypatch, skipped=1, report=True)
    supersede(factory, snapshot)
    with factory.begin() as db:
        manifest = db.get(InvestigationEvidenceManifest, job)
        if damage == 'missing':
            db.delete(db.scalar(select(InvestigationEvidence).where(InvestigationEvidence.job_id == job)))
        elif damage == 'changed':
            db.get(CodeChunk, chunk).source_text = 'def process_sync():\n    return 42\n'
        elif damage == 'count':
            manifest.evidence_count = 0
        elif damage == 'digest':
            manifest.digest = 'f' * 64
        elif damage == 'commit':
            db.get(CodeSnapshot, snapshot).commit_sha = 'f' * 40
        elif damage == 'revoked':
            repo = db.scalar(select(Repository).where(Repository.id == 902).with_for_update())
            revoke_snapshot(db, repo, snapshot, 'security')
        else:
            db.get(CodeSnapshot, snapshot).skipped_count = 0
    assert client.get(f'/v1/repositories/902/investigations/{job}').json()['retrieval_status'] == 'snapshot_unavailable'
    assert client.get(f'/v1/repositories/902/investigations/{job}/evidence').status_code == 409
    assert client.get(report_url(job)).status_code == 409


def test_unproven_and_legacy_snapshots_remain_closed(client, factory, github_auth, monkeypatch):
    job, snapshot, _ = prepared(client, factory, github_auth, monkeypatch, publication=False)
    supersede(factory, snapshot)
    assert client.get(f'/v1/repositories/902/investigations/{job}/evidence').status_code == 409
    with factory.begin() as db:
        db.delete(db.get(InvestigationEvidenceManifest, job))
    assert client.get(report_url(job)).status_code == 409


def test_legacy_without_manifest_remains_closed_even_with_publication(client, factory, github_auth, monkeypatch):
    job, snapshot, _ = prepared(client, factory, github_auth, monkeypatch)
    with factory.begin() as db:
        db.delete(db.get(InvestigationEvidenceManifest, job))
    supersede(factory, snapshot)
    assert client.get(f'/v1/repositories/902/investigations/{job}/evidence').status_code == 409


def test_late_publication_cannot_authenticate_never_published_snapshot(client, factory, github_auth, monkeypatch):
    job, snapshot, _ = prepared(client, factory, github_auth, monkeypatch, publication=False)
    with factory.begin() as db:
        s = db.get(CodeSnapshot, snapshot)
        db.add(SnapshotPublication(snapshot_id=s.id, repository_id=s.repository_id, tenant_id=s.tenant_id,
            commit_sha=s.commit_sha, file_count=s.file_count, chunk_count=s.chunk_count,
            skipped_count=s.skipped_count, published_at=now()))
    supersede(factory, snapshot)
    assert client.get(f'/v1/repositories/902/investigations/{job}/evidence').status_code == 409


def test_new_investigation_requires_current_eligible_snapshot(client, factory, github_auth, monkeypatch):
    job, snapshot, _ = prepared(client, factory, github_auth, monkeypatch)
    with factory.begin() as db:
        db.get(CodeSnapshot, snapshot).published = False
    assert client.post('/v1/repositories/902/issues/5/investigations', headers=csrf(client)).status_code == 409
    assert client.get(f'/v1/repositories/902/investigations/{job}/evidence').status_code == 200


def test_new_investigation_rejects_revoked_current_snapshot(client, factory, github_auth, monkeypatch):
    _, snapshot, _ = prepared(client, factory, github_auth, monkeypatch)
    with factory.begin() as db:
        publication = db.get(SnapshotPublication, snapshot)
        publication.revoked_at, publication.revocation_reason = now(), 'integrity'
    assert client.post('/v1/repositories/902/issues/5/investigations', headers=csrf(client)).status_code == 409


def test_historical_code_intelligence_reuses_verified_evidence(client, factory, github_auth, monkeypatch):
    job, snapshot, _ = prepared(client, factory, github_auth, monkeypatch, skipped=1)
    supersede(factory, snapshot)
    response = client.get(f'/v1/repositories/902/investigations/{job}/code-intelligence')
    assert response.status_code == 200
    assert response.json()['snapshot_id'] == snapshot


def test_revoked_or_foreign_user_cannot_read_historical_evidence(client, factory, github_auth, monkeypatch):
    job, snapshot, _ = prepared(client, factory, github_auth, monkeypatch)
    supersede(factory, snapshot)
    github_auth.include_repository = False
    assert client.get(f'/v1/repositories/902/investigations/{job}/evidence').status_code == 404
    github_auth.include_repository = True
    assert client.post('/v1/auth/logout', headers=csrf(client)).status_code == 200
    github_auth.user_id = github_auth.account_id = 78
    sign_in(client)
    assert client.get(f'/v1/repositories/902/investigations/{job}/evidence').status_code == 404


def test_historical_report_rejects_forged_citation(client, factory, github_auth, monkeypatch):
    job, snapshot, _ = prepared(client, factory, github_auth, monkeypatch, report=True)
    supersede(factory, snapshot)
    with factory.begin() as db:
        report = db.scalar(select(InvestigationReport).where(InvestigationReport.investigation_id == job))
        payload = dict(report.payload)
        import copy
        payload = copy.deepcopy(payload)
        payload['hypotheses'][0]['evidence'][0]['chunk_id'] = str(uuid4())
        report.payload = payload
    assert client.get(report_url(job)).status_code == 409


def test_duplicate_delivery_keeps_one_manifest(client, factory, github_auth, monkeypatch):
    job, snapshot, _ = prepared(client, factory, github_auth, monkeypatch)
    process_investigation(job, factory, github_auth)
    with factory() as db:
        assert len(db.scalars(select(InvestigationEvidenceManifest).where(
            InvestigationEvidenceManifest.job_id == job)).all()) == 1
        assert db.get(InvestigationJob, job).attempts == 1
    supersede(factory, snapshot)
    assert client.get(f'/v1/repositories/902/investigations/{job}/evidence').status_code == 200


def test_postgres_concurrent_delivery_commits_one_manifest(client, factory, github_auth, monkeypatch):
    if factory.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('PostgreSQL row locking required')
    snapshot, chunk = context(client, factory, github_auth)
    stub_retrieval(monkeypatch, factory, chunk)
    job = submit(client)
    claimed, release = Event(), Event()
    def hold():
        claimed.set()
        assert release.wait(10)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(process_investigation, job, factory, github_auth, hold)
        assert claimed.wait(10)
        second = pool.submit(process_investigation, job, factory, github_auth)
        second.result(timeout=10)
        release.set()
        first.result(timeout=10)
    with factory() as db:
        assert db.get(InvestigationJob, job).status == 'completed'
        assert len(db.scalars(select(InvestigationEvidenceManifest).where(
            InvestigationEvidenceManifest.job_id == job)).all()) == 1
        assert len(db.scalars(select(InvestigationEvidence).where(InvestigationEvidence.job_id == job)).all()) == 1
