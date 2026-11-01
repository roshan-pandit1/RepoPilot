"""Stage one synthetic, simulated experiment in a newly created disposable database.

No provider is instantiated, no approval or reservation is created, and no GitHub network
request or repository index job is made. The resulting identifiers are real fixture IDs.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def disposable_url(raw, run_id):
    if not re.fullmatch(r'[0-9a-f]{16}', run_id or ''):
        raise ValueError('invalid_run_id')
    try:
        url = make_url(raw)
    except Exception:
        raise ValueError('invalid_database') from None
    if (url.get_backend_name() != 'postgresql' or url.host != '127.0.0.1' or not url.port
            or url.username != 'repopilot_fixture' or url.query
            or url.database != f'repopilot_5b2b_{run_id}'):
        raise ValueError('invalid_database')
    return url


def assert_empty_database(engine, url):
    with engine.connect() as db:
        revision = db.execute(text('select version_num from alembic_version')).scalar_one()
        if (db.execute(text('select current_database()')).scalar_one() != url.database
                or revision not in ('0011', '0012', '0013')):
            raise ValueError('unexpected_database')
        preparer = engine.dialect.identifier_preparer
        for table in inspect(db).get_table_names(schema='public'):
            if table != 'alembic_version' and db.execute(
                    text('SELECT count(*) FROM public.' + preparer.quote(table))).scalar_one():
                raise ValueError('database_not_empty')
        return revision


def stage(root, url, run_id, *, review_directory):
    """Validate isolation and fence network even when called outside the CLI."""
    from app.evaluation.provider_harness import network_fence
    url = disposable_url(url, run_id)
    with network_fence(url.port or 0):
        return _stage(root, url, run_id, review_directory=review_directory)


def _stage(root, url, run_id, *, review_directory):
    from fastapi.testclient import TestClient
    from app.core.config import get_settings
    from app.domain.models import (AuthSession, CodeChunk, CodeSnapshot, IndexedFile, InvestigationEvidence,
        InvestigationExecutorApproval, InvestigationExperiment, InvestigationJob, InvestigationProviderSelection,
        InvestigationRealReport, InvestigationReport, InvestigationReportJob, InvestigationReportOutbox,
        InvestigationUsageReservation, Repository, now)
    from app.evaluation.experiment_executor import (canonical, digest, prepare_review,
        read_private, require_fake_configuration, write_private)
    from app.evaluation.disclosure_screen import screen_exact
    from app.evaluation.provider_harness import (COMMIT, EXPECTED_PATH, REPOSITORY, load_fixture, require)
    from app.evaluation.retrieval import citation_valid, match_label
    from app.infra.database import get_db
    from app.main import app
    from app.modules.github.client import get_github_client
    from app.modules.investigation.usage_ledger import INPUT_WINDOW, MODEL, OUTPUT_LIMIT
    from app.workers.tasks import process_investigation

    require_fake_configuration()
    dataset, case, source, chunks, source_file, omitted = load_fixture(root)
    engine = create_engine(url, hide_parameters=True)
    try:
        revision = assert_empty_database(engine, url)
        factory = sessionmaker(engine, expire_on_commit=False)
        sys.path.insert(0, str(root / 'apps/api/tests'))
        from test_auth_enrollment import FakeGitHub, csrf, sign_in

        class FixtureGitHub(FakeGitHub):
            def repositories(self, token, installation_id):
                require(installation_id == 901, 'fixture_installation_mismatch')
                return ([{'id': 902, 'full_name': REPOSITORY, 'private': False}]
                        if self.include_repository else [])

        github = FixtureGitHub()
        issue = {'id': 990, 'number': 5, 'title': case['title'], 'body': case['body'], 'state': 'open',
                 'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z',
                 'comments': 0, 'labels': []}
        github.issue = lambda *args: dict(issue)
        github.issue_comments = lambda *args: []
        def db_session():
            with factory() as db:
                yield db
        app.dependency_overrides[get_db] = db_session
        app.dependency_overrides[get_github_client] = lambda: github
        with TestClient(app) as client:
            sign_in(client)
            require(client.post('/v1/installations/901/enroll', headers=csrf(client)).status_code == 200,
                    'fixture_enrollment_failed')
            require(client.post('/v1/installations/901/repositories/902/select', headers=csrf(client)).status_code == 200,
                    'fixture_selection_failed')
            snapshot_id, file_id = str(uuid4()), str(uuid4())
            with factory.begin() as db:
                repo = db.get(Repository, 902)
                require(repo and repo.full_name == REPOSITORY, 'fixture_repository_mismatch')
                tenant_id = repo.tenant_id
                db.add(CodeSnapshot(id=snapshot_id, repository_id=902, tenant_id=tenant_id,
                    commit_sha=COMMIT, published=True, file_count=1, chunk_count=len(chunks), skipped_count=omitted))
                db.flush()
                db.add(IndexedFile(id=file_id, snapshot_id=snapshot_id, repository_id=902, tenant_id=tenant_id,
                    path=EXPECTED_PATH, content_hash=hashlib.sha256(source).hexdigest()))
                db.flush()
                for chunk in chunks:
                    db.add(CodeChunk(id=str(uuid4()), file_id=file_id, repository_id=902, tenant_id=tenant_id,
                        symbol=chunk.symbol, start_line=chunk.start_line, end_line=chunk.end_line, source_text=chunk.text))
            submitted = client.post('/v1/repositories/902/issues/5/investigations', headers=csrf(client))
            require(submitted.status_code == 202, 'fixture_investigation_failed')
            parent_id = submitted.json()['job_id']
            process_investigation(parent_id, factory, github)
            response = client.get(f'/v1/repositories/902/investigations/{parent_id}/evidence')
            require(response.status_code == 200, 'fixture_evidence_unavailable')
            evidence_result = response.json()
            evidence = evidence_result['items']
            require(evidence_result['snapshot_id'] == snapshot_id and evidence_result['commit_sha'] == COMMIT
                    and evidence and all(citation_valid(item, REPOSITORY, COMMIT) for item in evidence)
                    and any(match_label(item, case['relevance'][0]) for item in evidence), 'fixture_retrieval_mismatch')
            submitted = client.post(f'/v1/repositories/902/investigations/{parent_id}/report', headers=csrf(client))
            require(submitted.status_code == 202, 'fixture_report_job_failed')
            job_id = submitted.json()['report_job_id']
            experiment_id = str(uuid4())
            with factory.begin() as db:
                db.add(InvestigationExperiment(id=experiment_id, tenant_id=tenant_id, enabled=True,
                    mode='simulated', provider='openai', model=MODEL, budget_microusd=10_000_000,
                    investigation_budget_microusd=6_000_000, max_input_tokens=INPUT_WINDOW,
                    max_output_tokens=OUTPUT_LIMIT, max_concurrent=1, max_requests=1,
                    pricing_checked_at=now(), expires_at=now() + timedelta(minutes=55)))
                db.flush()
                db.add(InvestigationProviderSelection(job_id=job_id, repository_id=902,
                                                       tenant_id=tenant_id, experiment_id=experiment_id))
            payload, manifest = prepare_review(factory, root, experiment_id=experiment_id, job_id=job_id)
            # Rebuild independently from the exact issue/context contract used by the report worker.
            require(manifest['request_sha256'] == digest(canonical(payload)), 'request_hash_mismatch')
            write_private(review_directory, payload, manifest)
            require(read_private(review_directory, root, experiment_id=experiment_id, job_id=job_id)
                    == (payload, manifest), 'review_reconstruction_failed')
            screening = screen_exact(root, payload, manifest)
            with factory() as db:
                parent, task = db.get(InvestigationJob, parent_id), db.get(InvestigationReportJob, job_id)
                exp, session = db.get(InvestigationExperiment, experiment_id), db.get(AuthSession, task.session_hash)
                rows = db.scalars(select(InvestigationEvidence).where(
                    InvestigationEvidence.job_id == parent_id).order_by(InvestigationEvidence.rank)).all()
                counts = {'investigations': len(db.scalars(select(InvestigationJob)).all()),
                          'report_jobs': len(db.scalars(select(InvestigationReportJob)).all()),
                          'approvals': len(db.scalars(select(InvestigationExecutorApproval)).all()),
                          'reservations': len(db.scalars(select(InvestigationUsageReservation)).all()),
                          'reports': len(db.scalars(select(InvestigationRealReport)).all())
                                     + len(db.scalars(select(InvestigationReport)).all())}
                require(parent.status == 'completed' and task.status == 'queued' and task.attempts == 0
                        and db.get(InvestigationReportOutbox, job_id).status == 'pending'
                        and exp.mode == 'simulated' and exp.enabled and len(rows) == len(evidence)
                        and counts == {'investigations': 1, 'report_jobs': 1, 'approvals': 0,
                                       'reservations': 0, 'reports': 0}, 'unexpected_fixture_state')
                evidence_ids = [{'evidence_id': row.id, 'chunk_id': row.chunk_id, 'rank': row.rank} for row in rows]
                expiration = {'session_expires_at': session.expires_at.isoformat(),
                              'experiment_expires_at': exp.expires_at.isoformat()}
            result = {'run_id': run_id, 'database': url.database, 'migration': revision,
                'dataset': dataset['version'], 'case_id': case['issue_id'], 'source_commit': COMMIT,
                'source_blob': source_file.blob_sha, 'snapshot_id': snapshot_id, 'investigation_id': parent_id,
                'report_job_id': job_id, 'experiment_id': experiment_id, 'tenant_id': tenant_id,
                'repository_id': 902, 'evidence': evidence_ids, 'counts': counts,
                'experiment_mode': 'simulated', 'report_job_state': 'queued',
                'request_sha256': manifest['request_sha256'], 'manifest_sha256': digest(canonical(manifest)),
                'disclosure_screening': screening,
                'review_directory': str(review_directory), **expiration,
                'limitations': ['Synthetic disposable records only; no paid approval or provider request.',
                                'Human review and separate approval are required before any actual execution.']}
            return result
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        engine.dispose()


def main():
    from app.evaluation.experiment_executor import require_fake_configuration
    run_id = os.environ.get('REPOPILOT_5B2B_RUN_ID', '')
    url = disposable_url(os.environ.get('DATABASE_URL', ''), run_id)
    root = Path(os.environ['REPOPILOT_5B2B_ROOT']).resolve()
    require_fake_configuration()
    # All identities and secrets below are synthetic and used only in the disposable DB.
    fixture_key = base64.urlsafe_b64encode(hashlib.sha256(b'local-5b2b-synthetic-fernet-key').digest()).decode()
    os.environ.update(APP_ENV='test', DEMO_AUTH_ENABLED='false', GITHUB_OAUTH_ENABLED='true',
        GITHUB_APP_ID='123', GITHUB_CLIENT_ID='fixture', GITHUB_CLIENT_SECRET='synthetic-oauth-fixture',
        GITHUB_TOKEN_ENCRYPTION_KEY=fixture_key, GITHUB_CALLBACK_URL='http://localhost:3000/api/auth/callback',
        WEB_ORIGIN='http://localhost:3000', EMBEDDING_PROVIDER='disabled', EMBEDDING_ALLOW_PAID='false',
        INVESTIGATION_PROVIDER='mock', INVESTIGATION_REAL_ENABLED='false', INVESTIGATION_PAID_BACKGROUND_ENABLED='false')
    for name in ('INVESTIGATION_OPENAI_API_KEY', 'INVESTIGATION_EXPERIMENT_ID', 'OPENAI_API_KEY', 'EMBEDDING_API_KEY'):
        os.environ.pop(name, None)
    for name in ('httpx', 'httpx2'):
        logging.getLogger(name).setLevel(logging.WARNING)
    review = Path(tempfile.mkdtemp(prefix=f'repopilot-5b2b-{run_id}-'))
    result = stage(root, url, run_id, review_directory=review)
    output = root / 'apps/api/evaluation' / f'5b2b-readiness-{run_id}.json'
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    markdown = output.with_suffix('.md')
    with markdown.open('x', encoding='utf-8') as stream:
        stream.write('# Synthetic 5B2B experiment preflight\n\n'
            f"Run: `{run_id}`; database: `{result['database']}`; migration: `{result['migration']}`.\n\n"
            f"Case: `{result['case_id']}`; commit: `{result['source_commit']}`; "
            f"snapshot: `{result['snapshot_id']}`.\n\n"
            f"Investigation: `{result['investigation_id']}`; report job: `{result['report_job_id']}`; "
            f"experiment: `{result['experiment_id']}`.\n\n"
            f"Evidence items: {len(result['evidence'])}; report job: queued; experiment: simulated.\n\n"
            f"Request SHA-256: `{result['request_sha256']}`; manifest SHA-256: `{result['manifest_sha256']}`.\n\n"
            f"Private review directory: `{review}`.\n\n"
            f"Session expires: `{result['session_expires_at']}`; experiment expires: `{result['experiment_expires_at']}`.\n\n"
            'No paid approval, provider request, reservation or report was created. '
            'This is a synthetic fixture, not authorization for a paid request.\n')
    print(f'Synthetic preflight completed: run={run_id}; database={result["database"]}; '
          f'snapshot={result["snapshot_id"]}; evidence={len(result["evidence"])}.')
    print(f'Investigation={result["investigation_id"]}; report_job={result["report_job_id"]}; '
          f'experiment={result["experiment_id"]}; mode=simulated.')
    print(f'Request SHA-256={result["request_sha256"]}; manifest SHA-256={result["manifest_sha256"]}.')
    print(f'Private review directory: {review}; sanitized metadata: {output}, {markdown}.')
    print('No approval, reservation, provider request or report was created.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Synthetic preparation failed; the disposable database and artifacts were retained.') from None
