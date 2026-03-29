import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ade.core.config import Settings
from ade.core.llm import ClaudeLLM


@pytest.fixture
def test_settings():
    return Settings(
        anthropic_api_key="sk-ant-test-key-not-real",
        database_url="postgresql+asyncpg://ade:ade@localhost:5432/ade_test",
        database_url_sync="postgresql+psycopg2://ade:ade@localhost:5432/ade_test",
    )


@pytest.fixture
def mock_api_response():
    """Create a mock Claude API response."""
    response = MagicMock()
    response.content = [MagicMock(text="Generated code here")]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    return response


@pytest.mark.asyncio
async def test_complete_cache_miss(test_settings, mock_api_response):
    """On cache miss, should call the API and cache the result."""
    llm = ClaudeLLM(settings=test_settings)
    llm.client = AsyncMock()
    llm.client.messages.create = AsyncMock(return_value=mock_api_response)

    with (
        patch("ade.core.llm.cache_get", new_callable=AsyncMock, return_value=None),
        patch("ade.core.llm.cache_set", new_callable=AsyncMock) as mock_set,
        patch.object(llm, "_log_usage", new_callable=AsyncMock),
    ):
        result = await llm.complete(
            messages=[{"role": "user", "content": "Write a function"}],
            model="claude-sonnet-4-20250514",
        )

    assert result.content == "Generated code here"
    assert result.cached is False
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    mock_set.assert_called_once()


@pytest.mark.asyncio
async def test_complete_cache_hit(test_settings):
    """On cache hit, should return cached response without calling API."""
    llm = ClaudeLLM(settings=test_settings)
    llm.client = AsyncMock()

    cached_data = json.dumps({
        "content": "Cached response",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 50,
        "output_tokens": 25,
        "latency_ms": 100.0,
    })

    with (
        patch("ade.core.llm.cache_get", new_callable=AsyncMock, return_value=cached_data),
        patch("ade.core.llm.cache_set", new_callable=AsyncMock) as mock_set,
    ):
        result = await llm.complete(
            messages=[{"role": "user", "content": "Hello"}],
            model="claude-sonnet-4-20250514",
        )

    assert result.content == "Cached response"
    assert result.cached is True
    # API should not be called
    llm.client.messages.create.assert_not_called()
    # Should not re-cache
    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_complete_skips_cache_when_disabled(test_settings, mock_api_response):
    """use_cache=False should skip cache lookup."""
    llm = ClaudeLLM(settings=test_settings)
    llm.client = AsyncMock()
    llm.client.messages.create = AsyncMock(return_value=mock_api_response)

    with (
        patch("ade.core.llm.cache_get", new_callable=AsyncMock) as mock_get,
        patch("ade.core.llm.cache_set", new_callable=AsyncMock),
        patch.object(llm, "_log_usage", new_callable=AsyncMock),
    ):
        result = await llm.complete(
            messages=[{"role": "user", "content": "Hello"}],
            use_cache=False,
        )

    assert result.cached is False
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_complete_uses_default_model(test_settings, mock_api_response):
    """When no model is specified, should use default_codegen_model."""
    llm = ClaudeLLM(settings=test_settings)
    llm.client = AsyncMock()
    llm.client.messages.create = AsyncMock(return_value=mock_api_response)

    with (
        patch("ade.core.llm.cache_get", new_callable=AsyncMock, return_value=None),
        patch("ade.core.llm.cache_set", new_callable=AsyncMock),
        patch.object(llm, "_log_usage", new_callable=AsyncMock),
    ):
        result = await llm.complete(
            messages=[{"role": "user", "content": "Hello"}],
        )

    assert result.model == "claude-sonnet-4-20250514"


@pytest.mark.asyncio
async def test_complete_passes_system_prompt(test_settings, mock_api_response):
    """System prompt should be passed to the API call."""
    llm = ClaudeLLM(settings=test_settings)
    llm.client = AsyncMock()
    llm.client.messages.create = AsyncMock(return_value=mock_api_response)

    with (
        patch("ade.core.llm.cache_get", new_callable=AsyncMock, return_value=None),
        patch("ade.core.llm.cache_set", new_callable=AsyncMock),
        patch.object(llm, "_log_usage", new_callable=AsyncMock),
    ):
        await llm.complete(
            messages=[{"role": "user", "content": "Hello"}],
            system="You are a code assistant",
        )

    call_kwargs = llm.client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "You are a code assistant"


@pytest.mark.asyncio
async def test_log_usage_failure_does_not_raise(test_settings, mock_api_response):
    """If _log_usage fails, complete() should still return successfully."""
    llm = ClaudeLLM(settings=test_settings)
    llm.client = AsyncMock()
    llm.client.messages.create = AsyncMock(return_value=mock_api_response)

    with (
        patch("ade.core.llm.cache_get", new_callable=AsyncMock, return_value=None),
        patch("ade.core.llm.cache_set", new_callable=AsyncMock),
        patch.object(
            llm, "_log_usage", new_callable=AsyncMock, side_effect=Exception("DB down")
        ),
    ):
        # Should not raise even though _log_usage fails
        result = await llm.complete(
            messages=[{"role": "user", "content": "Hello"}],
        )

    assert result.content == "Generated code here"
