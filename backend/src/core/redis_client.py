"""Singleton async Redis client — lazy init on first call, reused app-wide."""

from __future__ import annotations

import redis.asyncio as aioredis

from src.core.config import settings

# Module-level singleton — None until first get_redis() call
redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create the shared Redis connection pool."""
    global redis_client
    if redis_client is None:
        # decode_responses=True -> all GET results come back as str, not bytes
        redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return redis_client


async def close_redis() -> None:
    """Drain connections and reset singleton — called during app shutdown."""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
