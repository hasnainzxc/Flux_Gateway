from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import authenticate
from src.db.models.event import EventLog
from src.db.session import get_db

router = APIRouter(prefix="/events", tags=["events"])


class EventListResponse(BaseModel):
    events: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


@router.get("", response_model=EventListResponse)
async def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    event_type: str | None = None,
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> EventListResponse:
    query = select(EventLog).where(EventLog.tenant_id == tenant_id)
    count_query = select(func.count()).select_from(EventLog).where(EventLog.tenant_id == tenant_id)

    if status_filter:
        query = query.where(EventLog.status == status_filter)
        count_query = count_query.where(EventLog.status == status_filter)
    if event_type:
        query = query.where(EventLog.event_type == event_type)
        count_query = count_query.where(EventLog.event_type == event_type)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(EventLog.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    events = result.scalars().all()

    return EventListResponse(
        events=[
            {
                "id": str(e.id),
                "tenant_id": str(e.tenant_id),
                "hook_id": e.hook_id,
                "event_type": e.event_type,
                "payload": e.payload,
                "matched_rules": e.matched_rules,
                "priority": e.priority,
                "status": e.status,
                "agent_run_id": str(e.agent_run_id) if e.agent_run_id else None,
                "result": e.result,
                "error_message": e.error_message,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            }
            for e in events
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{event_id}")
async def get_event(
    event_id: uuid.UUID,
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await session.execute(
        select(EventLog).where(
            EventLog.id == event_id,
            EventLog.tenant_id == tenant_id,
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "id": str(event.id),
        "tenant_id": str(event.tenant_id),
        "hook_id": event.hook_id,
        "event_type": event.event_type,
        "payload": event.payload,
        "matched_rules": event.matched_rules,
        "priority": event.priority,
        "status": event.status,
        "agent_run_id": str(event.agent_run_id) if event.agent_run_id else None,
        "result": event.result,
        "error_message": event.error_message,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "completed_at": event.completed_at.isoformat() if event.completed_at else None,
    }


@router.post("/{event_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_event(
    event_id: uuid.UUID,
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await session.execute(
        select(EventLog).where(
            EventLog.id == event_id,
            EventLog.tenant_id == tenant_id,
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed events can be retried")

    from arq import create_pool
    from arq.connections import RedisSettings

    from src.core.config import settings as app_settings

    pool = await create_pool(RedisSettings.from_dsn(app_settings.redis_url))
    await pool.enqueue_job("process_event", str(event.id), tenant_id)
    await pool.close()

    return {"status": "queued", "event_id": str(event.id)}
