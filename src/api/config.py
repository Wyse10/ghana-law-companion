from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Ghana Law Companion API"
    app_version: str = "0.1.0"
    app_environment: str = "development"
    api_docs_enabled: bool = True
    groq_api_key: SecretStr | None = None
    api_key: SecretStr | None = None
    api_keys: str = ""
    require_api_key: bool = False
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 10
    cors_origins: str = ""
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = (
        "postgresql+psycopg://ghana_law:local-development-only"
        "@localhost:5432/ghana_law"
    )
    database_pool_min_size: int = 1
    database_pool_max_size: int = 10
    vector_store_backend: Literal["local", "postgres"] = "local"
    source_sha256: str | None = None
    vector_db_path: str = str(
        Path(__file__).resolve().parents[2] / "data" / "qdrant_db"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
