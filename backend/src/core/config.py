from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://flux:flux_dev@localhost:5432/flux_gateway"
    redis_url: str = "redis://:flux_redis_dev@localhost:6379/0"
    secret_key: str = "changeme-in-production"
    environment: str = "development"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""

    secret_encryption_key: str = ""

    sandbox_enabled: bool = True
    sandbox_image: str = "python:3.12-slim"
    sandbox_timeout: int = 30
    sandbox_memory_limit: str = "256m"
    sandbox_cpu_quota: int = 50000

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


settings = Settings()
