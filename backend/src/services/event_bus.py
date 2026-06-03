"""Redis pub/sub event bus — tenant-scoped channels for real-time event streaming."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

from structlog import get_logger

from src.core.redis_client import get_redis

logger = get_logger(__name__)

# Each tenant gets their own Redis channel
CHANNEL_PREFIX = "flux:events:"


def _channel(tenant_id: str) -> str:
    """Build Redis pub/sub channel name for tenant — each tenant is isolated."""
    return f"{CHANNEL_PREFIX}{tenant_id}"


async def publish_event(tenant_id: str, event: dict[str, Any]) -> None:
    """Publish event to tenant's Redis channel. Subscribers (WebSocket workers) pick it up."""
    redis = await get_redis()
    channel = _channel(tenant_id)
    await redis.publish(channel, json.dumps(event))
    logger.debug("event_published", tenant_id=tenant_id, event_type=event.get("type"))


async def subscribe_tenant(
    tenant_id: str,
    callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> asyncio.Task[None]:
    """
    Subscribe to tenant's channel, invoke callback on each message.
    Returns asyncio.Task — cancel to stop listening. Handles cleanup on cancel.
    """
    redis = await get_redis()
    pubsub = redis.pubsub()
    channel = _channel(tenant_id)
    await pubsub.subscribe(channel)

    async def _listener() -> None:
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await callback(data)
                    except Exception:
                        logger.exception("event_callback_error", tenant_id=tenant_id)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    task = asyncio.create_task(_listener())
    logger.info("event_subscribed", tenant_id=tenant_id)
    return task
