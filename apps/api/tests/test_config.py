import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_demo_bypass():
    with pytest.raises(ValidationError, match="forbidden in production"):
        Settings(app_env="production", demo_auth_enabled=True)


def test_production_without_demo_is_valid():
    assert not Settings(app_env="production", demo_auth_enabled=False).demo_auth_enabled


def test_weak_secret_rejected():
    with pytest.raises(ValidationError, match="32 characters"):
        Settings(github_webhook_secret="short")
