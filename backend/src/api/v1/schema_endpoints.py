"""Schema reflection endpoints — introspect external DB, cache in Redis + Postgres."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import authenticate, require_tenant
from src.db.models import Connection, SchemaCache
from src.db.session import get_db
from src.services.schema_cache import cache_schema, get_cached_schema, invalidate_schema_cache
from src.services.schema_reflection import reflect_schema_for_connection, test_connection

router = APIRouter(prefix="/schema", tags=["schema"])


@router.post("/connections/{connection_id}/reflect")
async def reflect_schema(
    connection_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _auth: str = Depends(authenticate),
    tenant_id: str = Depends(require_tenant),
) -> dict[str, Any]:
    result = await session.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    # Decrypt connection string + introspect external DB schema
    schema_graph = await reflect_schema_for_connection(
        connection.encrypted_connection_string
    )

    connection.last_reflected_at = schema_graph.get("reflected_at")

    # Persist to Postgres as durable cache (survives Redis eviction)
    cache_entry = SchemaCache(
        connection_id=connection.id,
        tenant_id=uuid.UUID(tenant_id),
        schema_graph=json.dumps(schema_graph),
        version=schema_graph.get("schema_version", 1),
    )
    session.add(cache_entry)

    # Also push to Redis for fast reads (1h TTL)
    background_tasks.add_task(
        cache_schema, tenant_id, str(connection_id), schema_graph
    )

    await session.commit()
    return schema_graph


@router.get("/connections/{connection_id}")
async def get_schema(
    connection_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _auth: str = Depends(authenticate),
    tenant_id: str = Depends(require_tenant),
) -> dict[str, Any]:
    # Try Redis first (fast path), fall back to Postgres
    cached = await get_cached_schema(tenant_id, str(connection_id))
    if cached:
        return cached

    # Redis miss — load from Postgres cache (latest version)
    result = await session.execute(
        select(SchemaCache)
        .where(SchemaCache.connection_id == connection_id)
        .order_by(SchemaCache.created_at.desc())
        .limit(1)
    )
    cache_entry = result.scalar_one_or_none()
    if cache_entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No schema cache found. Reflect the connection first.",
        )

    # Backfill Redis cache from Postgres for subsequent fast reads
    schema_graph: dict[str, Any] = json.loads(cache_entry.schema_graph)
    await cache_schema(tenant_id, str(connection_id), schema_graph)
    return schema_graph


@router.post("/connections/{connection_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_schema(
    connection_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _auth: str = Depends(authenticate),
    tenant_id: str = Depends(require_tenant),
) -> dict[str, str]:
    await invalidate_schema_cache(tenant_id, str(connection_id))

    result = await session.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    background_tasks.add_task(
        _refresh_schema_background,
        str(connection_id),
        connection.encrypted_connection_string,
        tenant_id,
    )

    return {"message": "Schema refresh queued"}


@router.post("/connections/{connection_id}/test")
async def test_connection_endpoint(
    connection_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _auth: str = Depends(authenticate),
    _tenant: str = Depends(require_tenant),
) -> dict[str, bool]:
    result = await session.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    ok = await test_connection(connection.encrypted_connection_string)
    return {"success": ok}


async def _refresh_schema_background(
    connection_id: str,
    encrypted_conn_string: bytes,
    tenant_id: str,
) -> None:
    """Background task — re-reflect schema + update Redis cache. Errors logged, not raised."""
    import structlog

    logger = structlog.get_logger(__name__)
    try:
        schema_graph = await reflect_schema_for_connection(encrypted_conn_string)
        await cache_schema(tenant_id, connection_id, schema_graph)
        logger.info("schema refresh complete", connection_id=connection_id)
    except Exception as e:
        # Background task failure — logged but not surfaced to client.
        # Client sees stale cache until next manual refresh.
        logger.error("schema refresh failed", connection_id=connection_id, error=str(e))
