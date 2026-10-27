from functools import lru_cache
from typing import Literal

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
    demo_user_id: int = 1
    demo_tenant_id: int = 1

    @model_validator(mode="after")
    def secure_defaults(self):
        if len(self.github_webhook_secret.get_secret_value()) < 32:
            raise ValueError("Webhook secret must contain at least 32 characters")
        if self.demo_auth_enabled:
            if self.app_env == "production":
                raise ValueError("Demo authentication is forbidden in production")
            if len(self.demo_api_token.get_secret_value()) < 32:
                raise ValueError("Demo token must contain at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
