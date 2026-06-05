"""Centralized app config — reads from .env or env vars via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All app settings with sane dev defaults. Override via env vars or .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # DB + cache — asyncpg driver for async SQLAlchemy, Redis for caching/rate-limit/pub-sub
    database_url: str = "postgresql+asyncpg://flux:flux_dev@localhost:5432/flux_gateway"
    redis_url: str = "redis://:flux_redis_dev@localhost:6379/0"

    # Auth — CHANGE THESE in production. secret_key signs JWTs (HS256).
    secret_key: str = "changeme-in-production"
    environment: str = "development"

    # LLM provider (OpenRouter wraps OpenAI/Anthropic/etc.)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # OIDC / SSO
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""

    # Fernet key for encrypting connection strings + credentials at rest
    secret_encryption_key: str = ""

    # Docker sandbox for SQL validation / code execution.
    # Containers run with no network, read-only FS, capped mem/CPU.
    sandbox_enabled: bool = True
    sandbox_image: str = "python:3.12-slim"
    sandbox_timeout: int = 30  # seconds before container killed
    sandbox_memory_limit: str = "256m"
    sandbox_cpu_quota: int = 50000  # 50% of one CPU core (100000 = 100%)

    # MCP write-back — executes validated SQL against tenant's PostgreSQL database.
    # Default OFF (dry-run only) — set true to enable real database writes.
    mcp_execute_enabled: bool = False
    mcp_statement_timeout: int = 30  # seconds

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


# Singleton — imported everywhere
settings = Settings()
