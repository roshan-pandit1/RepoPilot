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
    worker_readiness_queue: str = "celery"
    github_webhook_secret: SecretStr
    demo_auth_enabled: bool = False
    demo_api_token: SecretStr = SecretStr("")
    github_oauth_enabled: bool = False
    github_app_id: int = 0
    github_installation_auth_enabled: bool = False
    github_app_private_key: SecretStr = SecretStr("")
    github_client_id: str = ""
    github_client_secret: SecretStr = SecretStr("")
    github_token_encryption_key: SecretStr = SecretStr("")
    github_callback_url: str = ""
    web_origin: str = "http://localhost:3000"
    demo_user_id: int = 1
    demo_tenant_id: int = 1
    index_multilingual_enabled: bool = False
    index_multilingual_supervised_parser_enabled: bool = False
    pr_reviews_enabled: bool = False
    pr_typescript_review_enabled: bool = False
    pr_typescript_node_path: str = ""
    pr_typescript_node_sha256: str = ""
    pr_typescript_compiler_path: str = ""
    pr_typescript_compiler_sha256: str = ""
    patch_proposals_enabled: bool = False
    patch_synthetic_execution_enabled: bool = False
    patch_max_files: int = 5
    patch_max_changed_lines: int = 300
    patch_max_bytes: int = 262144
    patch_provider_max_input_bytes: int = 524288
    patch_provider_max_output_bytes: int = 307200
    patch_provider_timeout_seconds: int = 30
    patch_worker_lease_seconds: int = 120
    patch_generation_provider: Literal["unavailable", "ollama"] = "unavailable"
    patch_local_model_enabled: bool = False
    patch_local_model_name: str = ""
    patch_local_model_digest: str = ""
    patch_local_model_endpoint: str = "http://127.0.0.1:11434"
    patch_local_model_strategy: Literal["direct_diff", "source_edits"] = "source_edits"
    investigation_query_limit: int = 3
    investigation_per_query_limit: int = 10
    investigation_evidence_limit: int = 20
    issue_context_body_chars: int = 16000
    issue_context_comment_count: int = 10
    issue_context_comment_chars: int = 2000
    issue_context_total_chars: int = 30000
    issue_context_max_requests: int = 42
    embedding_provider: Literal["disabled", "fake", "openai", "local"] = "disabled"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 32
    embedding_api_key: SecretStr = SecretStr("")
    embedding_allow_paid: bool = False
    embedding_local_enabled: bool = False
    embedding_local_path: str = ""
    embedding_local_revision: str = ""
    embedding_local_tokenizer_revision: str = ""
    embedding_local_model_sha256: str = ""
    embedding_local_tokenizer_sha256: str = ""
    investigation_provider: Literal["mock", "openai"] = "mock"
    investigation_real_enabled: bool = False
    investigation_paid_background_enabled: bool = False
    investigation_openai_api_key: SecretStr = SecretStr("")
    investigation_openai_organization: SecretStr = SecretStr("")
    investigation_openai_project: SecretStr = SecretStr("")
    investigation_count_external_enabled: bool = False
    investigation_experiment_id: str = ""

    @model_validator(mode="after")
    def secure_defaults(self):
        if self.pr_typescript_review_enabled and self.app_env == "production":
            raise ValueError("TypeScript review is not approved for production")
        if (not 1 <= self.patch_worker_lease_seconds <= 120
                or (self.app_env != "test" and self.patch_worker_lease_seconds != 120)):
            raise ValueError("Short patch worker leases require a test environment")
        if not self.worker_readiness_queue or len(self.worker_readiness_queue) > 128 or any(
                c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
                for c in self.worker_readiness_queue):
            raise ValueError("Invalid worker readiness queue")
        if self.patch_synthetic_execution_enabled and self.app_env != "test":
            raise ValueError("Synthetic patch execution is restricted to test environments")
        if not (1 <= self.patch_max_files <= 5 and 1 <= self.patch_max_changed_lines <= 300
                and 1 <= self.patch_max_bytes <= 262144):
            raise ValueError("Invalid patch safety limits")
        if not (1 <= self.patch_provider_max_input_bytes <= 524288
                and 1 <= self.patch_provider_max_output_bytes <= 307200
                and 1 <= self.patch_provider_timeout_seconds <= 30):
            raise ValueError("Invalid patch provider limits")
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
        if self.github_installation_auth_enabled:
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

            try:
                key = load_pem_private_key(self.github_app_private_key.get_secret_value().encode(), password=None)
                if self.github_app_id <= 0 or not isinstance(key, RSAPrivateKey) or key.key_size < 2048:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError("GitHub App installation authentication requires a valid RSA signing key") from None
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
