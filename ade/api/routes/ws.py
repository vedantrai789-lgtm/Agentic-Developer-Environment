"""WebSocket endpoint for real-time task status streaming."""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

HEARTBEAT_INTERVAL = 30


async def task_websocket(websocket: WebSocket, task_id: str) -> None:
    """Stream task events to a WebSocket client via Redis pub/sub."""
    await websocket.accept()

    try:
        from ade.core.redis_client import get_redis

        redis = get_redis()
        pubsub = redis.pubsub()
        channel = f"task:{task_id}:events"
        await pubsub.subscribe(channel)

        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                        timeout=HEARTBEAT_INTERVAL,
                    )
                except asyncio.TimeoutError:
                    # No message in HEARTBEAT_INTERVAL seconds — send ping
                    await websocket.send_text(json.dumps({"event_type": "ping"}))
                    continue

                if message and message["type"] == "message":
                    data = message["data"]
                    await websocket.send_text(data)

                    # Check if this is a terminal event
                    try:
                        event = json.loads(data)
                        if event.get("event_type") in ("task_completed", "task_failed"):
                            break
                    except (json.JSONDecodeError, KeyError):
                        pass

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
