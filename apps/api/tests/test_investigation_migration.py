"""Upgrade a disposable 0007 SQLite database containing a completed legacy job."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_legacy_job_survives_evidence_migration(tmp_path):
    api = Path(__file__).resolve().parents[1]
    database = tmp_path / 'migration.db'
    env = {**os.environ, 'APP_ENV': 'test', 'DATABASE_URL': f'sqlite:///{database}',
           'GITHUB_WEBHOOK_SECRET': 'fixture-' + 'x' * 40, 'DEMO_AUTH_ENABLED': 'false',
           'GITHUB_OAUTH_ENABLED': 'false', 'EMBEDDING_PROVIDER': 'disabled'}
    def alembic(*args):
        return subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=api, env=env,
                              capture_output=True, text=True, check=True)
    alembic('upgrade', '0007')
    with sqlite3.connect(database) as db:
        db.executescript("""
          INSERT INTO tenants(id,name) VALUES (1,'fixture');
          INSERT INTO users(id,github_user_id,login) VALUES (1,1,'fixture');
          INSERT INTO memberships(tenant_id,user_id) VALUES (1,1);
          INSERT INTO installations(id,tenant_id,active) VALUES (10,1,1);
          INSERT INTO repositories(id,tenant_id,installation_id,full_name,enabled) VALUES (20,1,10,'fixture/public',1);
          INSERT INTO auth_sessions(id_hash,user_id,tenant_id,github_token_ciphertext,csrf_hash,expires_at)
            VALUES ('fixture',1,1,'fixture','fixture','2030-01-01 00:00:00');
          INSERT INTO investigation_jobs(id,repository_id,tenant_id,user_id,session_hash,issue_id,issue_number,
            issue_updated_at,context_retrieved_at,status,attempts,created_at,updated_at,completed_at)
            VALUES ('legacy',20,1,1,'fixture',30,2,'2026-01-01','2026-01-01',
                    'completed',1,'2026-01-01','2026-01-01','2026-01-01');
          INSERT INTO investigation_outbox(job_id,repository_id,tenant_id,status,attempts,next_dispatch_at)
            VALUES ('legacy',20,1,'processed',2,'2026-01-01');
        """)
    alembic('upgrade', '0008')
    with sqlite3.connect(database) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute("INSERT INTO code_snapshots(id,repository_id,tenant_id,commit_sha,published,created_at,file_count,chunk_count,skipped_count) VALUES ('snap',20,1,?,1,'2026-01-01',1,1,0)", ('a' * 40,))
        db.execute("INSERT INTO indexed_files(id,snapshot_id,repository_id,tenant_id,path,content_hash) VALUES ('file','snap',20,1,'x.py',?)", ('b' * 64,))
        db.execute("INSERT INTO code_chunks(id,file_id,repository_id,tenant_id,symbol,start_line,end_line,source_text) VALUES ('chunk','file',20,1,'f',1,1,'def f(): pass')")
        db.execute("INSERT INTO investigation_jobs(id,repository_id,tenant_id,user_id,session_hash,issue_id,issue_number,issue_updated_at,context_retrieved_at,status,attempts,created_at,updated_at,completed_at,operation,snapshot_id,snapshot_commit_sha,source_repository_name,query_version,query_limit,per_query_limit,evidence_limit,query_body_limit) VALUES ('v4c',20,1,1,'fixture',31,3,'2026-01-01','2026-01-01','completed',1,'2026-01-01','2026-01-01','2026-01-01','code_evidence','snap',?,'fixture/public','terms-v1',3,10,20,4000)", ('a' * 40,))
        db.execute("INSERT INTO investigation_evidence(id,job_id,snapshot_id,repository_id,tenant_id,chunk_id,rank,query_id,query_hash,chunk_fingerprint,query_rank,method,created_at) VALUES ('ev','v4c','snap',20,1,'chunk',1,'fixture',?,?,1,'keyword','2026-01-01')", ('c' * 64, 'd' * 64))
    alembic('upgrade', 'head')
    with sqlite3.connect(database) as db:
        row = db.execute('select status, attempts, operation, snapshot_id from investigation_jobs where id=?', ('legacy',)).fetchone()
        assert row == ('completed', 1, 'mock_orchestration', None)
        assert db.execute("SELECT status, snapshot_id FROM investigation_jobs WHERE id='v4c'").fetchone() == ('completed', 'snap')
        assert db.execute("SELECT chunk_id FROM investigation_evidence WHERE id='ev'").fetchone() == ('chunk',)
        assert db.execute('select status,attempts from investigation_outbox where job_id=?', ('legacy',)).fetchone() == ('processed', 2)
        sql = db.execute("select sql from sqlite_master where name='investigation_jobs'").fetchone()[0]
        assert "issue_number > 0 AND issue_id > 0 AND attempts >= 0" in sql
        assert "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')" in sql
    assert 'No new upgrade operations detected.' in alembic('check').stdout


def test_postgres_legacy_job_survives_migration():
    """Exercise an actual 0007->0008 upgrade within a dedicated disposable PostgreSQL schema."""
    from uuid import uuid4
    import pytest
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema

    raw_url = os.environ.get('TEST_DATABASE_URL')
    if not raw_url:
        pytest.skip('Disposable PostgreSQL is required')
    url = make_url(raw_url)
    if url.get_backend_name() != 'postgresql' or not (url.database or '').startswith(
            ('repopilot_4c_disposable_', 'repopilot_4d_disposable_', 'repopilot_4e_disposable_',
             'repopilot_4f_checks_', 'repopilot_5b1_checks_', 'repopilot_5b2a_')):
        pytest.skip('Requires a dedicated checkpoint disposable PostgreSQL database')
    schema = 'legacy4c_' + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    scoped_url = url.update_query_dict({'options': f'-csearch_path={schema},public'})
    env = {**os.environ, 'APP_ENV': 'test', 'DATABASE_URL': scoped_url.render_as_string(hide_password=False),
           'GITHUB_WEBHOOK_SECRET': 'fixture-' + 'x' * 40, 'DEMO_AUTH_ENABLED': 'false',
           'GITHUB_OAUTH_ENABLED': 'false', 'EMBEDDING_PROVIDER': 'disabled'}
    api = Path(__file__).resolve().parents[1]
    with admin.begin() as db:
        assert db.execute(text('select current_database()')).scalar_one() == url.database
        db.execute(CreateSchema(schema))
    scoped = create_engine(scoped_url, hide_parameters=True)
    try:
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', '0007'], cwd=api, env=env,
                       capture_output=True, text=True, check=True)
        with scoped.begin() as db:
            for sql in (
                "INSERT INTO tenants(id,name) VALUES (1,'fixture')",
                "INSERT INTO users(id,github_user_id,login) VALUES (1,1,'fixture')",
                "INSERT INTO memberships(tenant_id,user_id) VALUES (1,1)",
                "INSERT INTO installations(id,tenant_id,active) VALUES (10,1,true)",
                "INSERT INTO repositories(id,tenant_id,installation_id,full_name,enabled) VALUES (20,1,10,'fixture/public',true)",
                "INSERT INTO auth_sessions(id_hash,user_id,tenant_id,github_token_ciphertext,csrf_hash,expires_at) VALUES ('fixture',1,1,'fixture','fixture','2030-01-01')",
                "INSERT INTO investigation_jobs(id,repository_id,tenant_id,user_id,session_hash,issue_id,issue_number,issue_updated_at,context_retrieved_at,status,attempts,created_at,updated_at,completed_at) VALUES ('legacy',20,1,1,'fixture',30,2,'2026-01-01','2026-01-01','completed',1,'2026-01-01','2026-01-01','2026-01-01')",
                "INSERT INTO investigation_outbox(job_id,repository_id,tenant_id,status,attempts,next_dispatch_at) VALUES ('legacy',20,1,'processed',2,'2026-01-01')",
            ):
                db.execute(text(sql))
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', '0008'], cwd=api, env=env,
                       capture_output=True, text=True, check=True)
        with scoped.begin() as db:
            row = db.execute(text("SELECT status, attempts, operation, snapshot_id FROM investigation_jobs WHERE id='legacy'")).one()
            assert tuple(row) == ('completed', 1, 'mock_orchestration', None)
            assert tuple(db.execute(text("SELECT status,attempts FROM investigation_outbox WHERE job_id='legacy'")).one()) == ('processed', 2)
            for sql in (
                "INSERT INTO code_snapshots(id,repository_id,tenant_id,commit_sha,published,created_at,file_count,chunk_count,skipped_count) VALUES ('snap',20,1,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',true,'2026-01-01',1,1,0)",
                "INSERT INTO indexed_files(id,snapshot_id,repository_id,tenant_id,path,content_hash) VALUES ('file','snap',20,1,'x.py','hash')",
                "INSERT INTO code_chunks(id,file_id,repository_id,tenant_id,symbol,start_line,end_line,source_text) VALUES ('chunk','file',20,1,'f',1,1,'def f(): pass')",
                "INSERT INTO investigation_jobs(id,repository_id,tenant_id,user_id,session_hash,issue_id,issue_number,issue_updated_at,context_retrieved_at,status,attempts,created_at,updated_at,completed_at,operation,snapshot_id,snapshot_commit_sha,source_repository_name,query_version,query_limit,per_query_limit,evidence_limit,query_body_limit) VALUES ('v4c',20,1,1,'fixture',31,3,'2026-01-01','2026-01-01','completed',1,'2026-01-01','2026-01-01','2026-01-01','code_evidence','snap','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','fixture/public','terms-v1',3,10,20,4000)",
                "INSERT INTO investigation_evidence(id,job_id,snapshot_id,repository_id,tenant_id,chunk_id,rank,query_id,query_hash,chunk_fingerprint,query_rank,method,created_at) VALUES ('ev','v4c','snap',20,1,'chunk',1,'fixture','hash','hash',1,'keyword','2026-01-01')",
            ):
                db.execute(text(sql))
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', '0009'], cwd=api, env=env,
                       capture_output=True, text=True, check=True)
        with scoped.begin() as db:
            assert tuple(db.execute(text("SELECT status,snapshot_id FROM investigation_jobs WHERE id='v4c'")).one()) == ('completed', 'snap')
            assert db.execute(text("SELECT chunk_id FROM investigation_evidence WHERE id='ev'")).scalar_one() == 'chunk'
            assert tuple(db.execute(text("SELECT status,attempts FROM investigation_outbox WHERE job_id='legacy'")).one()) == ('processed', 2)
            db.execute(text("INSERT INTO investigation_report_jobs(id,investigation_id,snapshot_id,repository_id,tenant_id,user_id,session_hash,status,attempts,created_at,updated_at) VALUES ('report-job','v4c','snap',20,1,1,'fixture','completed',1,'2026-01-01','2026-01-01')"))
            db.execute(text("INSERT INTO investigation_report_outbox(job_id,repository_id,tenant_id,status,attempts,next_dispatch_at) VALUES ('report-job',20,1,'processed',2,'2026-01-01')"))
            db.execute(text("INSERT INTO investigation_reports(id,report_job_id,investigation_id,snapshot_id,repository_id,tenant_id,commit_sha,provider,model,payload,cost_microusd,input_truncated,created_at) VALUES ('report','report-job','v4c','snap',20,1,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','mock','deterministic-v1',CAST(:payload AS JSON),0,false,'2026-01-01')"), {'payload': '{"summary":"Legacy fixture","hypotheses":[],"missing_evidence":[],"next_steps":[],"warnings":[]}'})
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=api, env=env,
                       capture_output=True, text=True, check=True)
        with scoped.connect() as db:
            assert tuple(db.execute(text("SELECT status,attempts FROM investigation_report_jobs WHERE id='report-job'")).one()) == ('completed', 1)
            assert tuple(db.execute(text("SELECT provider,model,snapshot_id FROM investigation_reports WHERE id='report'")).one()) == ('mock', 'deterministic-v1', 'snap')
            assert db.execute(text("SELECT payload FROM investigation_reports WHERE id='report'")).scalar_one()['summary'] == 'Legacy fixture'
            assert db.execute(text("SELECT chunk_id FROM investigation_evidence WHERE id='ev'")).scalar_one() == 'chunk'
            assert tuple(db.execute(text("SELECT status,attempts FROM investigation_outbox WHERE job_id='legacy'")).one()) == ('processed', 2)
    finally:
        scoped.dispose()
        with admin.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
        admin.dispose()
