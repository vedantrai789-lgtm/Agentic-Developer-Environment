from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required
    anthropic_api_key: str

    # Database
    database_url: str = "postgresql+asyncpg://ade:ade_password@localhost:5432/ade_db"
    database_url_sync: str = "postgresql+psycopg2://ade:ade_password@localhost:5432/ade_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Optional embeddings
    voyage_api_key: str | None = None

    # Model configuration
    default_codegen_model: str = "claude-sonnet-4-20250514"
    default_rerank_model: str = "claude-haiku-235-20250301"

    # LLM cache
    llm_cache_ttl_seconds: int = 3600

    # Sandbox
    sandbox_docker_image: str = "python:3.12-slim"
    sandbox_timeout_seconds: int = 60
    sandbox_memory_limit: str = "512m"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("database_url must use the asyncpg driver (postgresql+asyncpg://)")
        return v

    @field_validator("database_url_sync")
    @classmethod
    def validate_database_url_sync(cls, v: str) -> str:
        if not v.startswith("postgresql+psycopg2://") and not v.startswith("postgresql://"):
            raise ValueError("database_url_sync must use psycopg2 or plain postgresql driver")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
