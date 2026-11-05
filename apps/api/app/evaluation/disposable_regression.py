"""Run the disposable regression suite from an importable entry point."""
import os
import re
import sys
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.evaluation.provider_harness import network_fence


class Required:
    def __init__(self):
        self.cases = {}

    def pytest_runtest_logreport(self, report):
        if report.when == 'call':
            self.cases[report.nodeid] = report.outcome

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        reporter = session.config.pluginmanager.get_plugin('terminalreporter')
        required = ('test_postgres_search_returns_commit_citation',
            'test_postgres_keyword_search_handles_natural_language_and_identifiers',
            'test_postgres_keyword_camelcase_and_bounded_results',
            'test_postgres_v2_retrieval_deduplicates_and_fences_source',
            'test_queued_v1_job_keeps_legacy_queries_and_ranking',
            'test_v2_keeps_exact_symbols_and_adds_filtered_body_terms',
            'test_v2_stack_trace_identifier_and_vague_input_are_bounded',
            'test_snapshot_job_evidence_is_atomic_fenced_and_idempotent',
            'test_reindex_after_submit_never_switches_snapshot',
            'test_access_revoked_before_and_after_persistence',
            'test_cross_tenant_and_unauthenticated_evidence',
            'test_readonly_replay_rejects_mutations_and_write_locks',
            'test_comparison_rejects_mixed_provenance',
            'test_postgres_legacy_job_survives_migration')
        if (exitstatus != 0 or session.testscollected < 200
                or any(reporter.stats.get(x, []) for x in ('failed', 'skipped', 'error'))
                or not all(any(name in node and outcome == 'passed' for node, outcome in self.cases.items())
                           for name in required)):
            print('Disposable verification incomplete: failed, skipped or missing required cases.')
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def deny_http(*args, **kwargs):
    raise AssertionError('external_http_transport_forbidden')


def main():
    if sys.argv[1:] == ['--focused-sqlite']:
        if os.environ.get('TEST_DATABASE_URL'):
            raise SystemExit('Focused SQLite checks refuse TEST_DATABASE_URL.')
        db_port = 0
        args = ['-q', '-ra', '--tb=short', '--show-capture=no',
                'tests/test_code_intelligence.py::test_analysis_process_returns_result_or_stops_on_deadline',
                'tests/test_investigation_evidence.py::test_code_intelligence_requires_authorized_unchanged_evidence',
                'tests/test_investigation_evidence.py::test_code_intelligence_withholds_sensitive_source']
        plugins = []
    elif not sys.argv[1:]:
        url = make_url(os.environ['TEST_DATABASE_URL'])
        if (url.get_backend_name() != 'postgresql' or url.host != '127.0.0.1' or not url.port
                or url.username != 'repopilot_fixture' or url.query
                or not re.fullmatch(r'repopilot_5b2b_[0-9a-f]{16}', url.database or '')):
            raise SystemExit('Refusing unexpected database target.')
        with create_engine(url, hide_parameters=True).connect() as db:
            if (db.execute(text('select current_database()')).scalar_one() != url.database
                    or db.execute(text("select count(*) from pg_tables where schemaname='public'")).scalar_one()):
                raise SystemExit('Refusing nonempty or unexpected database.')
        db_port = url.port
        args = ['-q', '-ra', '--tb=short', '--show-capture=no',
                '--ignore=tests/test_investigation_evaluation_pg.py']
        plugins = [Required()]
    else:
        raise SystemExit('Unexpected regression runner arguments.')
    with (network_fence(db_port),
          patch.object(httpx.HTTPTransport, 'handle_request', deny_http),
          patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', deny_http)):
        return pytest.main(args, plugins=plugins)


if __name__ == '__main__':
    sys.exit(main())
