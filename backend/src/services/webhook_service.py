"""Webhook ingestion — verify signatures, match rules, queue events, push to WebSocket."""

from __future__ import annotations

import hashlib
import hmac
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.db.models.event import EventLog, WebhookConfig
from src.services.behavior_rules import match_rules
from src.services.event_bus import publish_event

logger = get_logger(__name__)


def verify_signature(payload_body: bytes, secret: str, signature_header: str | None) -> bool:
    """
    Verify HMAC-SHA256 signature. If no secret configured, allow (dev mode).
    Uses constant-time compare to prevent timing attacks.
    """
    if not secret:
        return True  # no secret = dev mode, accept all
    if not signature_header:
        return False  # secret required but no signature provided
    # Compute expected HMAC and compare in constant time
    expected = hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    sig = signature_header.removeprefix("sha256=")  # strip "sha256=" prefix if present
    return hmac.compare_digest(expected, sig)  # constant-time compare — prevents timing attacks


async def ingest_webhook(
    session: AsyncSession,
    tenant_id: str,
    hook_id: str,
    event_type: str,
    payload: dict,
) -> EventLog:
    """
    Process inbound webhook:
    1. Create EventLog record (status=queued)
    2. Match against behavior rules
    3. Publish to Redis pub/sub for real-time WebSocket updates
    Returns the created EventLog.
    """
    event = EventLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        hook_id=hook_id,
        event_type=event_type,
        payload=payload,
        matched_rules=[],
        priority=50,
        status="queued",
    )

    matched = await match_rules(session, tenant_id, event_type, payload)
    if matched:
        event.matched_rules = [r.name for r in matched]
        event.priority = max(r.priority for r in matched)

    session.add(event)
    await session.flush()

    # Notify WebSocket subscribers in real-time
    await publish_event(tenant_id, {
        "type": "event_received",
        "data": {
            "event_id": str(event.id),
            "event_type": event_type,
            "status": "queued",
            "matched_rules": event.matched_rules,
            "priority": event.priority,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        },
    })

    logger.info(
        "webhook_ingested",
        event_id=str(event.id),
        tenant_id=tenant_id,
        event_type=event_type,
        matched_count=len(matched),
    )
    return event


async def resolve_webhook_config(
    session: AsyncSession,
    hook_id: str,
) -> WebhookConfig | None:
    """Look up webhook config by public hook_id. Only active hooks pass."""
    result = await session.execute(
        select(WebhookConfig).where(
            WebhookConfig.hook_id == hook_id,
            WebhookConfig.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
