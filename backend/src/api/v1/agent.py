from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.graph import agent_graph
from src.agents.state import AgentState
from src.api.deps import require_tenant
from src.core.security_middleware import check_rate_limit, log_audit_event
from src.db.models import SchemaCache
from src.db.session import get_db

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentQueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    connection_id: str | None = Field(default=None)
    user_role: str = Field(default="analyst")
    max_retries: int = Field(default=3, ge=0, le=5)

    model_config = {"extra": "forbid"}


class CitationResponse(BaseModel):
    index: int
    chunk_id: str
    document_id: str
    score: float
    excerpt: str

    model_config = {"extra": "allow"}


class AgentQueryResponse(BaseModel):
    answer: str
    intent: str
    citations: list[dict] = []
    execution_result: dict | None = None
    tokens_used: int = 0
    latency_ms: float = 0
    query_id: str = ""
    node_traces: list[dict] = []

    model_config = {"extra": "allow"}


@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(
    payload: AgentQueryRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(require_tenant),
) -> AgentQueryResponse:
    await check_rate_limit(tenant_id)

    start = time.perf_counter()
    query_id = str(uuid.uuid4())

    schema_graph = None
    if payload.connection_id:
        result = await session.execute(
            select(SchemaCache)
            .where(SchemaCache.connection_id == payload.connection_id)
            .order_by(SchemaCache.created_at.desc())
            .limit(1)
        )
        cache = result.scalar_one_or_none()
        if cache:
            try:
                schema_graph = json.loads(cache.schema_graph)
            except (json.JSONDecodeError, TypeError):
                schema_graph = None

    initial_state: AgentState = {
        "tenant_id": tenant_id,
        "user_query": payload.prompt,
        "user_role": payload.user_role,
        "connection_id": payload.connection_id,
        "intent": "unknown",
        "schema_graph": schema_graph,
        "retrieved_chunks": [],
        "citations": [],
        "generated_code": None,
        "target_system": None,
        "review_passed": None,
        "review_errors": [],
        "retry_count": 0,
        "max_retries": payload.max_retries,
        "final_response": None,
        "execution_result": None,
        "error": None,
        "tokens_used": 0,
        "latency_ms": 0,
        "node_traces": [],
    }

    result_state = await agent_graph.ainvoke(initial_state)

    elapsed = (time.perf_counter() - start) * 1000

    await log_audit_event(
        tenant_id=tenant_id,
        event_type="agent_query",
        details={
            "query_id": query_id,
            "prompt": payload.prompt[:500],
            "intent": result_state.get("intent", "unknown"),
            "tokens_used": result_state.get("tokens_used", 0),
            "latency_ms": round(elapsed, 2),
            "connection_id": payload.connection_id,
        },
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )

    return AgentQueryResponse(
        answer=result_state.get("final_response", ""),
        intent=result_state.get("intent", "unknown"),
        citations=result_state.get("citations", []),
        execution_result=result_state.get("execution_result"),
        tokens_used=result_state.get("tokens_used", 0),
        latency_ms=round(elapsed, 2),
        query_id=query_id,
        node_traces=result_state.get("node_traces", []),
    )


@router.get("/queries/{query_id}")
async def get_agent_query(
    query_id: str,
    tenant_id: str = Depends(require_tenant),
) -> dict:
    return {
        "query_id": query_id,
        "status": "not_implemented",
        "message": "Agent query history will be persisted in a future update",
    }


@router.get("/queries")
async def list_agent_queries(
    tenant_id: str = Depends(require_tenant),
) -> dict:
    return {
        "queries": [],
        "message": "Agent query history will be persisted in a future update",
    }
