from __future__ import annotations

import json
from typing import Any

from src.core.redis_client import get_redis

SCHEMA_CACHE_PREFIX = "schema"
SCHEMA_CACHE_TTL = 3600


async def cache_schema(tenant_id: str, connection_id: str, schema_graph: dict[str, Any]) -> None:
    redis = await get_redis()
    key = f"{SCHEMA_CACHE_PREFIX}:{tenant_id}:{connection_id}"
    await redis.set(key, json.dumps(schema_graph), ex=SCHEMA_CACHE_TTL)


async def get_cached_schema(tenant_id: str, connection_id: str) -> dict[str, Any] | None:
    redis = await get_redis()
    key = f"{SCHEMA_CACHE_PREFIX}:{tenant_id}:{connection_id}"
    cached = await redis.get(key)
    if cached is None:
        return None
    result: dict[str, Any] = json.loads(cached)
    return result


async def invalidate_schema_cache(tenant_id: str, connection_id: str) -> None:
    redis = await get_redis()
    key = f"{SCHEMA_CACHE_PREFIX}:{tenant_id}:{connection_id}"
    await redis.delete(key)
