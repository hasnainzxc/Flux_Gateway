"""Rate limiting (sliding window) + audit logging via Redis."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import HTTPException, status

from src.core.redis_client import get_redis

# 100 reqs per 60s window per tenant — adjust per plan tier later
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 100


async def check_rate_limit(tenant_id: str) -> None:
    """
    Sliding-window rate limiter using Redis INCR.
    Each window is a separate key; auto-expires after 2x window to handle edge cases.
    Raises 429 if tenant exceeds RATE_LIMIT_MAX in current window.
    """
    redis = await get_redis()
    now = int(time.time())
    # Bucket by floor(now / window) — all reqs in same 60s share a key.
    # NOTE: this is fixed-window, not true sliding. Burst at boundary can allow 2x limit.
    window_key = now // RATE_LIMIT_WINDOW
    key = f"ratelimit:{tenant_id}:{window_key}"

    # INCR is atomic — safe under concurrent requests
    current = await redis.incr(key)
    if current == 1:
        # First hit in window — set TTL to 2x window so key self-cleans
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
    """
    Append audit entry to Redis list. Capped at 10k entries (ltrim) to prevent unbounded growth.
    For production, consider shipping to a proper log store (ELK, Datadog, etc.).
    """
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
    # lpush + ltrim = capped list, newest first
    await redis.lpush("audit_log", json.dumps(entry))
    await redis.ltrim("audit_log", 0, 9999)
