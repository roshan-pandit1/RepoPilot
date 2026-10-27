import hashlib
import hmac
import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.update(APP_ENV="test", DATABASE_URL="sqlite://", DEMO_AUTH_ENABLED="true",
                  DEMO_API_TOKEN="test-token-" + "x" * 40,
                  GITHUB_WEBHOOK_SECRET="test-secret-" + "x" * 40)

from app.core.config import get_settings  # noqa: E402
from app.domain.models import Base  # noqa: E402
from app.infra.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture
def factory():
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} \
        if url == "sqlite://" else {}
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    seed(sessions)
    yield sessions
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(factory):
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def payload():
    return {"action": "opened", "installation": {"id": 1001},
            "repository": {"id": 2001, "private": False},
            "issue": {"id": 3001, "number": 1, "title": "Signed demo issue", "body": "Details",
                      "state": "open", "updated_at": "2026-01-02T12:00:00Z"}}


def signed(payload, delivery_id=None, event="issues"):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    signature = hmac.new(get_settings().github_webhook_secret.get_secret_value().encode(),
                         raw, hashlib.sha256).hexdigest()
    return {"content": raw, "headers": {"X-Hub-Signature-256": "sha256=" + signature,
            "X-GitHub-Delivery": delivery_id or str(uuid4()), "X-GitHub-Event": event,
            "Content-Type": "application/json"}}


@pytest.fixture
def auth():
    return {"Authorization": "Bearer " + get_settings().demo_api_token.get_secret_value()}
