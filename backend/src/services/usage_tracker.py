"""Usage tracking — aggregate monthly metrics per tenant (tokens, runs, storage)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.db.models.event import UsageRecord

logger = get_logger(__name__)


def _current_period() -> tuple[datetime, datetime]:
    """Get current billing period boundaries (1st of month -> 1st of next month)."""
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Handle December -> January rollover (year increment)
    if now.month == 12:
        end = start.replace(year=now.year + 1, month=1)
    else:
        end = start.replace(month=now.month + 1)
    return start, end


async def track_usage(
    session: AsyncSession,
    tenant_id: str,
    *,
    tokens_input: int = 0,
    tokens_output: int = 0,
    agent_runs: int = 0,
    webhook_events: int = 0,
    sandbox_executions: int = 0,
    rag_queries: int = 0,
    storage_bytes: int = 0,
) -> None:
    """
    Increment usage counters for current billing period.
    Creates new record if first usage this month, else atomic UPDATE += delta.
    """
    period_start, period_end = _current_period()

    result = await session.execute(
        select(UsageRecord).where(
            UsageRecord.tenant_id == tenant_id,
            UsageRecord.period_start == period_start,
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        # First usage this period — create new record
        record = UsageRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            agent_runs=agent_runs,
            webhook_events=webhook_events,
            sandbox_executions=sandbox_executions,
            rag_queries=rag_queries,
            storage_bytes=storage_bytes,
        )
        session.add(record)
    else:
        # Atomic increment — safe under concurrent writes
        await session.execute(
            update(UsageRecord)
            .where(UsageRecord.id == record.id)
            .values(
                tokens_input=UsageRecord.tokens_input + tokens_input,
                tokens_output=UsageRecord.tokens_output + tokens_output,
                agent_runs=UsageRecord.agent_runs + agent_runs,
                webhook_events=UsageRecord.webhook_events + webhook_events,
                sandbox_executions=UsageRecord.sandbox_executions + sandbox_executions,
                rag_queries=UsageRecord.rag_queries + rag_queries,
                storage_bytes=UsageRecord.storage_bytes + storage_bytes,
            )
        )

    await session.flush()
    logger.debug("usage_tracked", tenant_id=tenant_id, period=str(period_start))


async def get_usage_summary(
    session: AsyncSession,
    tenant_id: str,
) -> dict:
    """Get current billing period usage. Returns zeros if no usage yet."""
    period_start, period_end = _current_period()

    result = await session.execute(
        select(UsageRecord).where(
            UsageRecord.tenant_id == tenant_id,
            UsageRecord.period_start == period_start,
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "tokens_input": 0,
            "tokens_output": 0,
            "agent_runs": 0,
            "webhook_events": 0,
            "sandbox_executions": 0,
            "rag_queries": 0,
            "storage_bytes": 0,
        }

    return {
        "period_start": record.period_start.isoformat(),
        "period_end": record.period_end.isoformat(),
        "tokens_input": record.tokens_input,
        "tokens_output": record.tokens_output,
        "agent_runs": record.agent_runs,
        "webhook_events": record.webhook_events,
        "sandbox_executions": record.sandbox_executions,
        "rag_queries": record.rag_queries,
        "storage_bytes": record.storage_bytes,
    }


async def get_usage_history(
    session: AsyncSession,
    tenant_id: str,
    months: int = 6,
) -> list[dict]:
    """Get historical usage for last N months, oldest first."""
    result = await session.execute(
        select(UsageRecord)
        .where(UsageRecord.tenant_id == tenant_id)
        .order_by(UsageRecord.period_start.desc())
        .limit(months)
    )
    records = result.scalars().all()
    return [
        {
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "tokens_input": r.tokens_input,
            "tokens_output": r.tokens_output,
            "agent_runs": r.agent_runs,
            "webhook_events": r.webhook_events,
            "sandbox_executions": r.sandbox_executions,
            "rag_queries": r.rag_queries,
            "storage_bytes": r.storage_bytes,
        }
        for r in reversed(records)
    ]
