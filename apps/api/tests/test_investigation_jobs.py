from datetime import timedelta

import pytest
from sqlalchemy import select
from billiard.exceptions import SoftTimeLimitExceeded

from app.domain.models import CodeSnapshot, Installation, InvestigationJob, InvestigationOutbox, Repository, now
from app.workers.dispatcher import dispatch_once
from app.workers.tasks import TransientIngestionError, process_investigation
from test_auth_enrollment import csrf, github_auth as github_auth, sign_in
from test_issue_context import setup_issue as setup_github_issue

SUBMIT = '/v1/repositories/902/issues/5/investigations'


def setup_issue(client, github, factory):
    from uuid import uuid4
    setup_github_issue(client, github)
    with factory.begin() as db:
        repo = db.get(Repository, 902)
        db.add(CodeSnapshot(id=str(uuid4()), tenant_id=repo.tenant_id, repository_id=902,
                            commit_sha='a' * 40, published=True))


def submit(client):
    response = client.post(SUBMIT, headers=csrf(client))
    assert response.status_code == 202
    return response.json()['job_id']


def test_submit_outbox_duplicate_dispatch_and_terminal(client, factory, github_auth):
    assert client.post(SUBMIT).status_code == 401
    setup_issue(client, github_auth, factory)
    assert client.post(SUBMIT).status_code == 403
    assert client.post(SUBMIT, headers={**csrf(client), 'Origin': 'https://attacker.invalid'}).status_code == 403
    job = submit(client)
    assert submit(client) == job
    with factory() as db:
        assert db.get(InvestigationOutbox, job).status == 'pending'
        row = db.get(InvestigationJob, job)
        assert row.status == 'queued' and row.issue_id == 990 and row.attempts == 0
    sent = []
    dispatch_once(factory, lambda _: None, lambda _: None, lambda _: None, lambda _: None, sent.append)
    assert sent == [job]
    process_investigation(job, factory, github_auth)
    process_investigation(job, factory, github_auth)
    with factory() as db:
        assert db.get(InvestigationJob, job).status == 'completed'
        assert db.get(InvestigationJob, job).attempts == 1
        assert db.get(InvestigationOutbox, job).status == 'processed'
    status = client.get(f'/v1/repositories/902/investigations/{job}')
    assert status.status_code == 200 and status.json()['operation'] == 'code_evidence'
    assert 'sensitive-github-token' not in status.text


def test_revocation_and_cross_tenant(client, factory, github_auth):
    setup_issue(client, github_auth, factory)
    job = submit(client)
    with factory.begin() as db:
        db.get(Installation, 901).active = False
    process_investigation(job, factory, github_auth)
    with factory() as db:
        assert db.get(InvestigationJob, job).status == 'cancelled'
    assert client.get(f'/v1/repositories/902/investigations/{job}').status_code == 404
    with factory.begin() as db:
        db.get(Installation, 901).active = True
    assert client.post('/v1/auth/logout', headers=csrf(client)).status_code == 200
    github_auth.user_id = github_auth.account_id = 78
    sign_in(client)
    assert client.get(f'/v1/repositories/902/investigations/{job}').status_code == 404
    assert client.post(SUBMIT, headers=csrf(client)).status_code == 404


def test_retry_timeout_and_expired_lease(client, factory, github_auth):
    setup_issue(client, github_auth, factory)
    job = submit(client)
    def timed_out():
        raise SoftTimeLimitExceeded()
    with pytest.raises(TransientIngestionError):
        process_investigation(job, factory, github_auth, timed_out)
    with factory.begin() as db:
        row = db.get(InvestigationJob, job)
        assert row.status == 'queued' and row.error_code == 'worker_timeout'
        row.status, row.lease_token = 'running', 'crashed'
        row.lease_expires_at = now() - timedelta(seconds=1)
    process_investigation(job, factory, github_auth)
    with factory() as db:
        assert db.get(InvestigationJob, job).status == 'completed'
        assert db.get(InvestigationJob, job).attempts == 2


def test_revocation_during_work_and_duplicate_live_claim(client, factory, github_auth):
    setup_issue(client, github_auth, factory)
    job = submit(client)
    def revoke():
        process_investigation(job, factory, github_auth)
        with factory.begin() as db:
            db.get(Installation, 901).active = False
    process_investigation(job, factory, github_auth, revoke)
    with factory() as db:
        row = db.get(InvestigationJob, job)
        assert row.status == 'cancelled' and row.attempts == 1


def test_postgres_concurrent_claim(client, factory, github_auth):
    if factory.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('PostgreSQL locking required')
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    setup_issue(client, github_auth, factory)
    job = submit(client)
    started, release = Event(), Event()
    def work():
        started.set()
        assert release.wait(10)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(process_investigation, job, factory, github_auth, work)
        assert started.wait(10)
        second = pool.submit(process_investigation, job, factory, github_auth)
        second.result(timeout=10)
        release.set()
        first.result(timeout=10)
    with factory() as db:
        assert db.scalar(select(InvestigationJob).where(InvestigationJob.id == job)).attempts == 1


def test_invalid_issue_and_retry_exhaustion(client, factory, github_auth):
    setup_issue(client, github_auth, factory)
    assert client.post('/v1/repositories/902/issues/0/investigations', headers=csrf(client)).status_code == 422
    job = submit(client)
    github_auth.fail = True
    for _ in range(5):
        with pytest.raises(TransientIngestionError):
            process_investigation(job, factory, github_auth)
    with factory() as db:
        row = db.get(InvestigationJob, job)
        assert row.status == 'failed' and row.error_code == 'attempts_exhausted' and row.attempts == 5
        assert db.get(InvestigationOutbox, job).status == 'processed'
    process_investigation(job, factory, github_auth)


def test_outbox_insert_failure_rolls_back_job(client, factory, github_auth):
    from sqlalchemy import event
    from sqlalchemy.exc import SQLAlchemyError

    setup_issue(client, github_auth, factory)
    def fail_insert(mapper, connection, target):
        raise SQLAlchemyError('private fixture detail')
    event.listen(InvestigationOutbox, 'before_insert', fail_insert)
    try:
        response = client.post(SUBMIT, headers=csrf(client))
        assert response.status_code == 503
        assert 'private fixture detail' not in response.text
    finally:
        event.remove(InvestigationOutbox, 'before_insert', fail_insert)
    with factory() as db:
        assert db.scalar(select(InvestigationJob)) is None
        assert db.scalar(select(InvestigationOutbox)) is None
