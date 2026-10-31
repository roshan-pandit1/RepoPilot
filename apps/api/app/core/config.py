from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "production"
    database_url: str
    redis_url: str = "redis://redis:6379/0"
    github_webhook_secret: SecretStr
    demo_auth_enabled: bool = False
    demo_api_token: SecretStr = SecretStr("")
    github_oauth_enabled: bool = False
    github_app_id: int = 0
    github_client_id: str = ""
    github_client_secret: SecretStr = SecretStr("")
    github_token_encryption_key: SecretStr = SecretStr("")
    github_callback_url: str = ""
    web_origin: str = "http://localhost:3000"
    demo_user_id: int = 1
    demo_tenant_id: int = 1
    investigation_query_limit: int = 3
    investigation_per_query_limit: int = 10
    investigation_evidence_limit: int = 20
    issue_context_body_chars: int = 16000
    issue_context_comment_count: int = 10
    issue_context_comment_chars: int = 2000
    issue_context_total_chars: int = 30000
    issue_context_max_requests: int = 42
    embedding_provider: Literal["disabled", "fake", "openai"] = "disabled"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 32
    embedding_api_key: SecretStr = SecretStr("")
    embedding_allow_paid: bool = False
    investigation_provider: Literal["mock", "openai"] = "mock"
    investigation_real_enabled: bool = False
    investigation_paid_background_enabled: bool = False
    investigation_openai_api_key: SecretStr = SecretStr("")
    investigation_experiment_id: str = ""

    @model_validator(mode="after")
    def secure_defaults(self):
        if not (1 <= self.investigation_query_limit <= 3 and 1 <= self.investigation_per_query_limit <= 20
                and 1 <= self.investigation_evidence_limit <= 30):
            raise ValueError("Invalid investigation retrieval limits")
        if not (1 <= self.issue_context_body_chars <= 50000
                and 0 <= self.issue_context_comment_count <= 30
                and 1 <= self.issue_context_comment_chars <= 5000
                and 1 <= self.issue_context_total_chars <= 100000
                and 2 <= self.issue_context_max_requests <= 42):
            raise ValueError("Invalid issue context limits")
        if not 1 <= self.embedding_dimensions <= 2000:
            raise ValueError("Invalid embedding dimensions")
        if self.embedding_provider == "fake" and self.app_env == "production":
            raise ValueError("Fake embeddings are forbidden in production")
        if self.embedding_provider == "openai" and (not self.embedding_allow_paid or
                not self.embedding_api_key.get_secret_value() or not self.embedding_model):
            raise ValueError("Paid embedding provider requires explicit opt-in and credentials")
        if len(self.github_webhook_secret.get_secret_value()) < 32:
            raise ValueError("Webhook secret must contain at least 32 characters")
        if self.demo_auth_enabled:
            if self.app_env == "production":
                raise ValueError("Demo authentication is forbidden in production")
            if len(self.demo_api_token.get_secret_value()) < 32:
                raise ValueError("Demo token must contain at least 32 characters")
        if self.github_oauth_enabled:
            from cryptography.fernet import Fernet

            if self.github_app_id <= 0 or not self.github_client_id or not self.github_client_secret.get_secret_value():
                raise ValueError("GitHub OAuth client configuration required")
            try:
                Fernet(self.github_token_encryption_key.get_secret_value().encode())
            except (ValueError, TypeError):
                raise ValueError("Valid Fernet token encryption key required") from None
            origin = urlsplit(self.web_origin)
            callback = urlsplit(self.github_callback_url)
            if (origin.scheme not in {"http", "https"} or not origin.netloc
                    or origin.path not in {"", "/"} or origin.query or origin.fragment
                    or origin.username or origin.password):
                raise ValueError("Invalid web origin")
            if (callback.scheme != origin.scheme or callback.netloc != origin.netloc
                    or callback.path != "/api/auth/callback" or callback.query or callback.fragment):
                raise ValueError("Callback must be the fixed web origin auth callback")
            if self.app_env == "production" and origin.scheme != "https":
                raise ValueError("Production authentication requires HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
