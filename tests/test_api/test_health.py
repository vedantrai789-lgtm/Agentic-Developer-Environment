"""Tests for the /health endpoint."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_health_endpoint_healthy(client):
    """Health check should return healthy when DB and Redis are ok."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    mock_factory = AsyncMock()
    mock_factory.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    with (
        patch("ade.core.database.async_session_factory", return_value=mock_factory),
        patch("ade.core.redis_client.get_redis", return_value=mock_redis),
    ):
        resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] is True
    assert data["redis"] is True


@pytest.mark.asyncio
async def test_health_endpoint_degraded(client):
    """Health check should return degraded when services are down."""
    with (
        patch(
            "ade.core.database.async_session_factory",
            side_effect=Exception("DB down"),
        ),
        patch(
            "ade.core.redis_client.get_redis",
            side_effect=Exception("Redis down"),
        ),
    ):
        resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
