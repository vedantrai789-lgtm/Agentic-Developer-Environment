import os
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

# Set test env vars before any imports from ade
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key-not-real")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ade:ade_password@localhost:5432/ade_db")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg2://ade:ade_password@localhost:5432/ade_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture
def settings():
    """Return a Settings instance with test values."""
    from ade.core.config import Settings

    return Settings(
        anthropic_api_key="sk-ant-test-key-not-real",
        database_url="postgresql+asyncpg://ade:ade_password@localhost:5432/ade_test",
        database_url_sync="postgresql+psycopg2://ade:ade_password@localhost:5432/ade_test",
        redis_url="redis://localhost:6379/1",
    )


@pytest.fixture
def fake_redis():
    """Return a fakeredis instance for testing without a real Redis server."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_anthropic_client():
    """Return a mocked AsyncAnthropic client."""
    client = AsyncMock()

    # Mock a successful response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Hello, world!")]
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    client.messages.create = AsyncMock(return_value=mock_response)

    return client


@pytest.fixture
def mock_llm(settings, fake_redis, mock_anthropic_client):
    """Return a ClaudeLLM instance with mocked dependencies."""
    from ade.core.llm import ClaudeLLM

    llm = ClaudeLLM(settings=settings)
    llm.client = mock_anthropic_client

    # Patch Redis to use fakeredis
    with (
        patch("ade.core.llm.cache_get", new_callable=AsyncMock) as mock_cache_get,
        patch("ade.core.llm.cache_set", new_callable=AsyncMock) as mock_cache_set,
    ):
        mock_cache_get.return_value = None  # cache miss by default
        llm._mock_cache_get = mock_cache_get
        llm._mock_cache_set = mock_cache_set
        yield llm
