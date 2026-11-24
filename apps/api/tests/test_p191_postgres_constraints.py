"""Opt-in PostgreSQL tenant, origin, partial-snapshot and uniqueness constraints.

Never point this test at application data. It creates and drops all mapped tables.
P191_POSTGRES_TEST_URL must use the P19.1 private socket-only test cluster.
"""
import os
import re
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.domain.models import (
    AuthSession, Base, CodeSnapshot, InvestigationIssueOrigin, InvestigationJob,
    Membership, PartialSnapshotScope, Repository, Tenant, User, now,
)


@pytest.fixture
def postgres_factory():
    url = os.environ.get("P191_POSTGRES_TEST_URL")
    if not url:
        pytest.skip("P191_POSTGRES_TEST_URL requires an explicitly disposable PostgreSQL cluster")
    parsed = make_url(url)
    host = parsed.query.get("host", "")
    match = re.fullmatch(r"/private/tmp/(p191_[0-9a-f]{12})_sock", host)
    if (parsed.drivername != "postgresql+psycopg" or parsed.username != "p191admin"
            or not parsed.password or parsed.database != "p191_tests" or parsed.host is not None
            or parsed.query.get("port") != "57488" or not match):
        raise RuntimeError("P19.1 PostgreSQL test target rejected before connection")
    expected_data = str(Path("/Users/roshan/Library/Application Support/RepoPilot") / match.group(1) / "data")
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as db:
        actual = db.execute(text("select current_database(),current_user,inet_server_addr(),"
                                 "current_setting('data_directory'),current_setting('unix_socket_directories')")).one()
        if tuple(actual) != ("p191_tests", "p191admin", None, expected_data, host):
            raise RuntimeError("P19.1 PostgreSQL test server identity mismatch")
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add_all([Tenant(id=1, name="fixture-a"), Tenant(id=2, name="fixture-b"),
                    User(id=1, github_user_id=901, login="fixture-user")])
        db.flush()
        db.add(Membership(tenant_id=1, user_id=1))
        db.flush()
        # Repository requires an installation bound to the same tenant.
        from app.domain.models import Installation
        db.add(Installation(id=1001, tenant_id=1, active=True))
        db.flush()
        db.add(Repository(id=2001, tenant_id=1, installation_id=1001,
                          full_name="fixture/fork", enabled=True))
        db.add(AuthSession(id_hash="a" * 64, user_id=1, tenant_id=1,
                           github_token_ciphertext="synthetic", csrf_hash="b" * 64,
                           expires_at=now() + timedelta(hours=1)))
    try:
        yield factory
    finally:
        # Recheck the server and database before destructive test cleanup.
        with engine.connect() as db:
            actual = db.execute(text("select current_database(),current_user,inet_server_addr(),"
                                     "current_setting('data_directory'),current_setting('unix_socket_directories')")).one()
            if tuple(actual) != ("p191_tests", "p191admin", None, expected_data, host):
                raise RuntimeError("P19.1 PostgreSQL cleanup target changed")
        Base.metadata.drop_all(engine)
        engine.dispose()


def job(snapshot_id=None, origin_id=3001, number=17):
    values = dict(id=str(uuid4()), repository_id=2001, tenant_id=1, user_id=1,
                  session_hash="a" * 64, issue_id=4001, issue_number=number,
                  issue_origin_repository_id=origin_id, issue_updated_at=now(),
                  context_retrieved_at=now(), status="queued")
    if snapshot_id is not None:
        values.update(operation="code_evidence", snapshot_id=snapshot_id,
                      snapshot_commit_sha="c" * 40, source_repository_name="fixture/fork",
                      query_version="terms-v2", query_limit=1, per_query_limit=1,
                      evidence_limit=1, query_body_limit=100)
    return InvestigationJob(**values)


def snapshot(*, published=False):
    return CodeSnapshot(id=str(uuid4()), repository_id=2001, tenant_id=1, commit_sha="c" * 40,
                        published=published, inventory_coverage="PARTIAL_INVENTORY",
                        inventory_manifest={"paths": ["src/fixture.py"]},
                        inventory_manifest_sha256="d" * 64)


def origin(job_id, *, tenant=1, issue_id=4001):
    return InvestigationIssueOrigin(job_id=job_id, repository_id=2001, tenant_id=tenant,
        origin_repository_id=3001, origin_repository_name="fixture/upstream", issue_id=issue_id,
        issue_number=17, issue_url="https://github.com/fixture/upstream/issues/17",
        issue_title="Synthetic issue", issue_body_sha256="e" * 64,
        issue_updated_at=now(), verified_at=now(), relationship="direct_public_parent")


def test_origin_fk_accepts_exact_owner_identity(postgres_factory):
    task = job()
    with postgres_factory.begin() as db:
        db.add(task)
        db.flush()
        db.add(origin(task.id))
    with postgres_factory() as db:
        assert db.get(InvestigationIssueOrigin, task.id).origin_repository_id == 3001


@pytest.mark.parametrize("alteration", ["tenant", "issue_id"])
def test_origin_fk_rejects_cross_tenant_and_wrong_issue(postgres_factory, alteration):
    task = job()
    with postgres_factory.begin() as db:
        db.add(task)
    with pytest.raises(IntegrityError) as error:
        with postgres_factory.begin() as db:
            db.add(origin(task.id, tenant=2 if alteration == "tenant" else 1,
                          issue_id=4002 if alteration == "issue_id" else 4001))
            db.flush()
    assert error.value.orig.diag.constraint_name == "fk_investigation_issue_origin_owner"


def test_partial_inventory_cannot_be_published(postgres_factory):
    with pytest.raises(IntegrityError) as error:
        with postgres_factory.begin() as db:
            db.add(snapshot(published=True))
            db.flush()
    assert error.value.orig.diag.constraint_name == "ck_snapshot_inventory_coverage"


@pytest.mark.parametrize("alteration", ["tenant", "manifest"])
def test_partial_scope_fk_rejects_cross_tenant_and_wrong_manifest(postgres_factory, alteration):
    snap = snapshot()
    task = job(snapshot_id=snap.id)
    with postgres_factory.begin() as db:
        db.add(snap)
        db.flush()
        db.add(task)
    with pytest.raises(IntegrityError) as error:
        with postgres_factory.begin() as db:
            db.add(PartialSnapshotScope(job_id=task.id, snapshot_id=snap.id, repository_id=2001,
                tenant_id=2 if alteration == "tenant" else 1,
                manifest_sha256="f" * 64 if alteration == "manifest" else "d" * 64))
            db.flush()
    assert error.value.orig.diag.constraint_name in {
        "fk_partial_scope_investigation_owner", "fk_partial_scope_inventory_owner"}


def test_partial_scope_accepts_bound_owner_and_manifest(postgres_factory):
    snap = snapshot()
    task = job(snapshot_id=snap.id)
    with postgres_factory.begin() as db:
        db.add(snap)
        db.flush()
        db.add(task)
        db.flush()
        db.add(PartialSnapshotScope(job_id=task.id, snapshot_id=snap.id,
                                    repository_id=2001, tenant_id=1, manifest_sha256="d" * 64))
    with postgres_factory() as db:
        assert db.get(PartialSnapshotScope, task.id).snapshot_id == snap.id


def test_active_uniqueness_distinguishes_origin_and_legacy_same_repo(postgres_factory):
    legacy = job(origin_id=None)
    with postgres_factory.begin() as db:
        db.add(legacy)
        db.add(job(origin_id=3001))
    with pytest.raises(IntegrityError) as error:
        with postgres_factory.begin() as db:
            db.add(job(origin_id=2001))
            db.flush()
    assert error.value.orig.diag.constraint_name == "uq_investigation_active"
    with pytest.raises(IntegrityError) as error:
        with postgres_factory.begin() as db:
            db.add(job(origin_id=3001))
            db.flush()
    assert error.value.orig.diag.constraint_name == "uq_investigation_active"
