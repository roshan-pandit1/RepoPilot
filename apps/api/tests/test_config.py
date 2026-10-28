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


def test_oauth_requires_valid_key_origin_and_https_in_production():
    from cryptography.fernet import Fernet

    config = {"github_oauth_enabled": True, "github_app_id": 1, "github_client_id": "client",
              "github_client_secret": "secret", "github_token_encryption_key": Fernet.generate_key().decode(),
              "web_origin": "http://localhost:3000",
              "github_callback_url": "http://localhost:3000/api/auth/callback"}
    with pytest.raises(ValidationError, match="requires HTTPS"):
        Settings(app_env="production", demo_auth_enabled=False, **config)
    with pytest.raises(ValidationError, match="fixed web origin"):
        Settings(app_env="test", github_callback_url="http://attacker.test/api/auth/callback",
                 **{k: v for k, v in config.items() if k != "github_callback_url"})
    with pytest.raises(ValidationError, match="Fernet"):
        Settings(app_env="test", github_token_encryption_key="invalid",
                 **{k: v for k, v in config.items() if k != "github_token_encryption_key"})
