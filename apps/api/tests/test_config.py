import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_demo_bypass():
    with pytest.raises(ValidationError, match="forbidden in production"):
        Settings(app_env="production", demo_auth_enabled=True, embedding_provider="disabled")


def test_production_without_demo_is_valid():
    from cryptography.fernet import Fernet

    settings = Settings(
        _env_file=None, app_env="production", database_url="sqlite://",
        github_webhook_secret="fixture-webhook-secret-" + "x" * 32,
        demo_auth_enabled=False, embedding_provider="disabled", github_oauth_enabled=True, github_app_id=1,
        github_client_id="fixture-client", github_client_secret="fixture-secret",
        github_token_encryption_key=Fernet.generate_key().decode(),
        web_origin="https://repopilot.example",
        github_callback_url="https://repopilot.example/api/auth/callback",
    )
    assert not settings.demo_auth_enabled
    assert settings.github_oauth_enabled


def test_weak_secret_rejected():
    with pytest.raises(ValidationError, match="32 characters"):
        Settings(github_webhook_secret="short")


def test_oauth_requires_valid_key_origin_and_https_in_production():
    from cryptography.fernet import Fernet

    config = {"embedding_provider": "disabled", "github_oauth_enabled": True, "github_app_id": 1, "github_client_id": "client",
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
