"""Task event publishing via Redis pub/sub."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def publish_task_event(
    task_id: str, event_type: str, data: dict | None = None
) -> None:
    """Publish a task event to Redis for WebSocket consumers."""
    try:
        from ade.core.redis_client import get_redis

        redis = get_redis()
        event = {
            "task_id": task_id,
            "event_type": event_type,
            "data": data or {},
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        await redis.publish(f"task:{task_id}:events", json.dumps(event))
    except Exception as e:
        logger.warning("Failed to publish task event: %s", e)
