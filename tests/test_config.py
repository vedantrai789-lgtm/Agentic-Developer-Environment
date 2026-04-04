
import pytest


def test_settings_loads_from_env(settings):
    """Settings instance should load values correctly."""
    assert settings.anthropic_api_key == "sk-ant-test-key-not-real"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.database_url_sync.startswith("postgresql+psycopg2://")
    assert settings.redis_url.startswith("redis://")


def test_settings_defaults():
    """Settings should have sensible defaults for optional fields."""
    from ade.core.config import Settings

    s = Settings(anthropic_api_key="sk-ant-test")
    assert s.default_codegen_model == "claude-sonnet-4-20250514"
    assert s.default_rerank_model == "claude-haiku-235-20250301"
    assert s.llm_cache_ttl_seconds == 3600
    assert s.sandbox_timeout_seconds == 60
    assert s.embedding_dimension == 1024


def test_settings_validates_database_url():
    """Settings should reject invalid database_url driver."""
    from ade.core.config import Settings

    with pytest.raises(ValueError, match="asyncpg"):
        Settings(
            anthropic_api_key="sk-ant-test",
            database_url="postgresql://bad-driver@localhost/db",
        )


def test_settings_validates_database_url_sync():
    """Settings should reject invalid database_url_sync driver."""
    from ade.core.config import Settings

    with pytest.raises(ValueError, match="psycopg2"):
        Settings(
            anthropic_api_key="sk-ant-test",
            database_url_sync="mysql://wrong@localhost/db",
        )


def test_get_settings_singleton():
    """get_settings should return the same instance (cached)."""
    from ade.core.config import get_settings

    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
