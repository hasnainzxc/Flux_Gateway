from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import HTTPException, status

from src.core.redis_client import get_redis

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 100


async def check_rate_limit(tenant_id: str) -> None:
    redis = await get_redis()
    now = int(time.time())
    window_key = now // RATE_LIMIT_WINDOW
    key = f"ratelimit:{tenant_id}:{window_key}"

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, RATE_LIMIT_WINDOW * 2)

    if current > RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
        )


async def log_audit_event(
    tenant_id: str,
    event_type: str,
    details: dict,
    ip_address: str = "",
    user_agent: str = "",
) -> None:
    import json

    redis = await get_redis()
    entry = {
        "tenant_id": tenant_id,
        "event_type": event_type,
        "details": json.dumps(details),
        "ip_address": ip_address,
        "user_agent": user_agent,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    await redis.lpush("audit_log", json.dumps(entry))
    await redis.ltrim("audit_log", 0, 9999)
