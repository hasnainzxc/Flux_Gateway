"""Webhook CRUD + ingest endpoint. HMAC signature verification, event queueing via arq."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import authenticate
from src.db.models.event import WebhookConfig
from src.db.session import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    name: str
    source: str


class WebhookUpdate(BaseModel):
    name: str | None = None
    source: str | None = None
    is_active: bool | None = None


class WebhookIngest(BaseModel):
    event_type: str
    payload: dict[str, Any] = {}


@router.get("")
async def list_webhooks(
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(WebhookConfig)
        .where(WebhookConfig.tenant_id == tenant_id)
        .order_by(WebhookConfig.created_at.desc())
    )
    hooks = result.scalars().all()
    return [
        {
            "id": str(h.id),
            "name": h.name,
            "hook_id": h.hook_id,
            "source": h.source,
            "is_active": h.is_active,
            "has_secret": h.secret is not None,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in hooks
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_webhook(
    data: WebhookCreate,
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    # hook_id = public URL slug (e.g. /ingest/abc123), secret = HMAC signing key
    hook_id = secrets.token_urlsafe(16)
    secret = secrets.token_hex(32)  # returned once on create, never again

    hook = WebhookConfig(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=data.name,
        hook_id=hook_id,
        secret=secret,
        source=data.source,
        is_active=True,
    )
    session.add(hook)
    await session.commit()
    await session.refresh(hook)

    return {
        "id": str(hook.id),
        "name": hook.name,
        "hook_id": hook.hook_id,
        "secret": secret,
        "source": hook.source,
        "is_active": hook.is_active,
        "created_at": hook.created_at.isoformat() if hook.created_at else None,
    }


@router.patch("/{hook_id}")
async def update_webhook(
    hook_id: uuid.UUID,
    data: WebhookUpdate,
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await session.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == hook_id,
            WebhookConfig.tenant_id == tenant_id,
        )
    )
    hook = result.scalar_one_or_none()
    if hook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if data.name is not None:
        hook.name = data.name
    if data.source is not None:
        hook.source = data.source
    if data.is_active is not None:
        hook.is_active = data.is_active

    await session.commit()
    await session.refresh(hook)

    return {
        "id": str(hook.id),
        "name": hook.name,
        "hook_id": hook.hook_id,
        "source": hook.source,
        "is_active": hook.is_active,
    }


@router.delete("/{hook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    hook_id: uuid.UUID,
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> None:
    result = await session.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == hook_id,
            WebhookConfig.tenant_id == tenant_id,
        )
    )
    hook = result.scalar_one_or_none()
    if hook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await session.delete(hook)
    await session.commit()


@router.post("/ingest/{hook_id}", status_code=status.HTTP_202_ACCEPTED)
async def ingest_webhook(
    hook_id: str,
    request: Request,
    data: WebhookIngest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from src.services.webhook_service import ingest_webhook as do_ingest
    from src.services.webhook_service import resolve_webhook_config, verify_signature

    # Look up webhook config by public hook_id — must be active
    config = await resolve_webhook_config(session, hook_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Webhook not found or inactive")

    # Verify HMAC-SHA256 signature — prevents unauthorized event injection
    body = await request.body()
    sig_header = request.headers.get("X-Signature-256")
    if not verify_signature(body, config.secret or "", sig_header):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Create EventLog record + match behavior rules + publish to Redis pub/sub
    event = await do_ingest(
        session=session,
        tenant_id=str(config.tenant_id),
        hook_id=hook_id,
        event_type=data.event_type,
        payload=data.payload,
    )
    await session.commit()

    # Enqueue async processing via arq worker — runs agent pipeline on the event
    from arq import create_pool
    from arq.connections import RedisSettings

    from src.core.config import settings

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("process_event", str(event.id), str(config.tenant_id))
    await pool.close()  # close pool handle, not the underlying Redis conn

    return {
        "event_id": str(event.id),
        "status": "queued",
        "matched_rules": event.matched_rules,  # rules matched during ingest
    }
