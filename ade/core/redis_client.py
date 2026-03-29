import hashlib
import json

import redis.asyncio as aioredis

from ade.core.config import get_settings

_redis_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Get or create the Redis connection pool singleton."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            max_connections=20,
            decode_responses=True,
        )
    return _redis_pool


async def cache_get(key: str) -> str | None:
    """Get a cached value by key."""
    r = get_redis()
    return await r.get(key)


async def cache_set(key: str, value: str, ttl: int | None = None) -> None:
    """Set a cached value with optional TTL in seconds."""
    r = get_redis()
    if ttl:
        await r.setex(key, ttl, value)
    else:
        await r.set(key, value)


async def cache_delete(key: str) -> None:
    """Delete a cached value by key."""
    r = get_redis()
    await r.delete(key)


def make_llm_cache_key(
    model: str,
    messages: list[dict],
    system: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """Build a deterministic cache key for an LLM request."""
    payload = {
        "model": model,
        "messages": messages,
        "system": system,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"llm:{model}:{digest}"
