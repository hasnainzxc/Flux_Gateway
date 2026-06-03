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
    if not secret:
        return True
    if not signature_header:
        return False
    expected = hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    sig = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, sig)


async def ingest_webhook(
    session: AsyncSession,
    tenant_id: str,
    hook_id: str,
    event_type: str,
    payload: dict,
) -> EventLog:
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
    result = await session.execute(
        select(WebhookConfig).where(
            WebhookConfig.hook_id == hook_id,
            WebhookConfig.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
