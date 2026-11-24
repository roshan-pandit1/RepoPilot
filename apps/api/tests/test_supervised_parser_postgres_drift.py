"""Migration and drift checks within one marker-verified disposable database."""

import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from evaluation.tree_sitter_pg_harness import MARKER, ROLE, validate_target


def test_supervised_integration_postgres_upgrade_and_schema_drift():
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("reviewed disposable PostgreSQL is required")
    url = make_url(raw_url)
    assert url.host == "127.0.0.1" and url.port and url.username == ROLE
    validate_target(raw_url, url.database, url.port)
    schema = "h11_drift_" + uuid4().hex
    assert re.fullmatch(r"h11_drift_[0-9a-f]{32}", schema)
    admin = create_engine(url, hide_parameters=True)
    created = False

    def require_marker(connection):
        row = connection.execute(text("SELECT current_database(), current_user, "
                                      "shobj_description(oid, 'pg_database') FROM pg_database "
                                      "WHERE datname = current_database()" )).one()
        assert tuple(row) == (url.database, ROLE, MARKER)

    try:
        with admin.begin() as connection:
            require_marker(connection)
            assert not connection.execute(text("SELECT 1 FROM pg_namespace WHERE nspname=:name"),
                                          {"name": schema}).scalar()
            connection.execute(CreateSchema(schema))
        created = True
        scoped_url = url.update_query_dict({"options": f"-csearch_path={schema},public"})
        env = {**os.environ, "APP_ENV": "test", "DATABASE_URL": scoped_url.render_as_string(hide_password=False),
               "ALEMBIC_VERSION_TABLE_SCHEMA": schema,
               "GITHUB_WEBHOOK_SECRET": "synthetic-" + "x" * 40, "DEMO_AUTH_ENABLED": "false",
               "GITHUB_OAUTH_ENABLED": "false", "EMBEDDING_PROVIDER": "disabled"}
        api = Path(__file__).resolve().parents[1]
        upgrade = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=api, env=env,
                                 capture_output=True, text=True, timeout=120, check=False)
        assert upgrade.returncode == 0, f"disposable Alembic upgrade failed: exit {upgrade.returncode}"
        current = subprocess.run([sys.executable, "-m", "alembic", "current"], cwd=api, env=env,
                                 capture_output=True, text=True, timeout=60, check=False)
        assert current.returncode == 0 and "0018" in current.stdout
        check = subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=api, env=env,
                               capture_output=True, text=True, timeout=120, check=False)
        assert check.returncode == 0, f"disposable Alembic drift check failed: exit {check.returncode}; {check.stdout[-2000:]}"
        assert "No new upgrade operations detected" in check.stdout
    finally:
        if created:
            with admin.begin() as connection:
                require_marker(connection)
                connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
