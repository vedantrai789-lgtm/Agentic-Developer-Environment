from unittest.mock import patch

import fakeredis.aioredis
import pytest

from ade.core.redis_client import cache_delete, cache_get, cache_set, make_llm_cache_key


@pytest.fixture
def patched_redis():
    """Patch get_redis to return a fakeredis instance."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("ade.core.redis_client.get_redis", return_value=fake):
        yield fake


@pytest.mark.asyncio
async def test_cache_set_and_get(patched_redis):
    """cache_set followed by cache_get should return the value."""
    await cache_set("test_key", "test_value")
    result = await cache_get("test_key")
    assert result == "test_value"


@pytest.mark.asyncio
async def test_cache_set_with_ttl(patched_redis):
    """cache_set with TTL should store the value."""
    await cache_set("ttl_key", "ttl_value", ttl=60)
    result = await cache_get("ttl_key")
    assert result == "ttl_value"


@pytest.mark.asyncio
async def test_cache_get_miss(patched_redis):
    """cache_get should return None for missing keys."""
    result = await cache_get("nonexistent_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_delete(patched_redis):
    """cache_delete should remove the key."""
    await cache_set("del_key", "del_value")
    await cache_delete("del_key")
    result = await cache_get("del_key")
    assert result is None


def test_make_llm_cache_key_deterministic():
    """Same inputs should produce the same cache key."""
    messages = [{"role": "user", "content": "Hello"}]
    key1 = make_llm_cache_key("claude-sonnet-4-20250514", messages, system="Be helpful")
    key2 = make_llm_cache_key("claude-sonnet-4-20250514", messages, system="Be helpful")
    assert key1 == key2
    assert key1.startswith("llm:claude-sonnet-4-20250514:")


def test_make_llm_cache_key_varies_with_input():
    """Different inputs should produce different cache keys."""
    msg1 = [{"role": "user", "content": "Hello"}]
    msg2 = [{"role": "user", "content": "Goodbye"}]
    key1 = make_llm_cache_key("claude-sonnet-4-20250514", msg1)
    key2 = make_llm_cache_key("claude-sonnet-4-20250514", msg2)
    assert key1 != key2


def test_make_llm_cache_key_varies_with_model():
    """Different models should produce different cache keys."""
    messages = [{"role": "user", "content": "Hello"}]
    key1 = make_llm_cache_key("claude-sonnet-4-20250514", messages)
    key2 = make_llm_cache_key("claude-haiku-235-20250301", messages)
    assert key1 != key2
