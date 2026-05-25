from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_tenant
from src.core.security_middleware import check_rate_limit, log_audit_event
from src.db.models import SchemaCache
from src.db.session import get_db
from src.services.llm import llm_complete

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    connection_id: str | None = Field(default=None)

    model_config = {"extra": "forbid"}


class QueryResponse(BaseModel):
    answer: str
    tokens_used: int | None = None
    latency_ms: float | None = None


@router.post("/", response_model=QueryResponse)
async def schema_query(
    payload: QueryRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(require_tenant),
) -> QueryResponse:
    import time as time_module

    await check_rate_limit(tenant_id)

    start = time_module.perf_counter()

    schema_context = ""
    if payload.connection_id:
        result = await session.execute(
            select(SchemaCache)
            .where(SchemaCache.connection_id == payload.connection_id)
            .order_by(SchemaCache.created_at.desc())
            .limit(1)
        )
        cache = result.scalar_one_or_none()
        if cache:
            schema_context = (
                "You have access to the following database schema:\n"
                + cache.schema_graph[:8000]
            )

    system_prompt = (
        "You are a data analyst assistant. Answer questions about the user's database.\n"
        "Use ONLY the table and column names provided. Never invent names.\n"
        "Respond clearly and concisely."
    )

    if schema_context:
        system_prompt += "\n\n" + schema_context

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": payload.prompt},
    ]

    answer = await llm_complete(messages)
    elapsed = (time_module.perf_counter() - start) * 1000

    await log_audit_event(
        tenant_id=tenant_id,
        event_type="schema_query",
        details={
            "prompt": payload.prompt[:500],
            "connection_id": payload.connection_id,
            "latency_ms": round(elapsed, 2),
        },
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )

    return QueryResponse(
        answer=answer,
        latency_ms=round(elapsed, 2),
    )
