from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import authenticate
from src.db.session import get_db
from src.services.usage_tracker import get_usage_history, get_usage_summary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary")
async def usage_summary(
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await get_usage_summary(session, tenant_id)


@router.get("/history")
async def usage_history(
    months: int = Query(6, ge=1, le=24),
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await get_usage_history(session, tenant_id, months)
