from __future__ import annotations

import uuid
from datetime import UTC, datetime

from arq.connections import RedisSettings
from structlog import get_logger

from src.core.config import settings

logger = get_logger(__name__)


async def process_event(ctx: dict, event_id: str, tenant_id: str) -> dict:
    from src.db.session import async_session_factory
    from src.services.websocket_manager import manager

    async with async_session_factory() as session:
        from sqlalchemy import select, update

        from src.db.models.event import EventLog

        result = await session.execute(
            select(EventLog).where(EventLog.id == uuid.UUID(event_id))
        )
        event = result.scalar_one_or_none()

        if event is None:
            logger.error("event_not_found", event_id=event_id)
            return {"status": "error", "message": "event not found"}

        await session.execute(
            update(EventLog)
            .where(EventLog.id == event.id)
            .values(status="processing")
        )
        await session.commit()

        await manager.send_event_update(tenant_id, {
            "event_id": event_id,
            "status": "processing",
        })

        try:
            run_id = uuid.uuid4()
            await manager.send_agent_status(tenant_id, str(run_id), "started", {
                "event_id": event_id,
            })

            from src.agents.graph import run_agent
            agent_result = await run_agent(
                session=session,
                tenant_id=tenant_id,
                user_query=f"Process webhook event: {event.event_type}. Payload: {event.payload}",
            )

            completed_at = datetime.now(UTC)
            await session.execute(
                update(EventLog)
                .where(EventLog.id == event.id)
                .values(
                    status="completed",
                    agent_run_id=run_id,
                    result=agent_result,
                    completed_at=completed_at,
                )
            )
            await session.commit()

            await manager.send_event_update(tenant_id, {
                "event_id": event_id,
                "status": "completed",
                "result": agent_result,
                "completed_at": completed_at.isoformat(),
            })
            await manager.send_agent_status(tenant_id, str(run_id), "completed")

            from src.services.usage_tracker import track_usage
            await track_usage(
                session, tenant_id,
                agent_runs=1,
                webhook_events=1,
                tokens_input=agent_result.get("tokens_input", 0),
                tokens_output=agent_result.get("tokens_output", 0),
            )
            await session.commit()

            return {"status": "completed", "event_id": event_id, "run_id": str(run_id)}

        except Exception as exc:
            logger.exception("event_processing_failed", event_id=event_id)
            await session.execute(
                update(EventLog)
                .where(EventLog.id == event.id)
                .values(status="failed", error_message=str(exc))
            )
            await session.commit()

            await manager.send_event_update(tenant_id, {
                "event_id": event_id,
                "status": "failed",
                "error": str(exc),
            })
            return {"status": "failed", "event_id": event_id, "error": str(exc)}


async def run_agent_task(
    ctx: dict, tenant_id: str, query: str, connection_id: str | None = None
) -> dict:
    from src.db.session import async_session_factory
    from src.services.websocket_manager import manager

    run_id = str(uuid.uuid4())
    await manager.send_agent_status(tenant_id, run_id, "started")

    async with async_session_factory() as session:
        try:
            from src.agents.graph import run_agent
            result = await run_agent(
                session=session,
                tenant_id=tenant_id,
                user_query=query,
                connection_id=connection_id,
            )

            await manager.send_agent_status(tenant_id, run_id, "completed", {
                "answer": result.get("answer", ""),
            })

            from src.services.usage_tracker import track_usage
            await track_usage(
                session, tenant_id,
                agent_runs=1,
                tokens_input=result.get("tokens_input", 0),
                tokens_output=result.get("tokens_output", 0),
            )
            await session.commit()

            return {"run_id": run_id, **result}

        except Exception as exc:
            logger.exception("agent_task_failed", run_id=run_id)
            await manager.send_agent_status(tenant_id, run_id, "failed", {
                "error": str(exc),
            })
            return {"run_id": run_id, "status": "failed", "error": str(exc)}


async def startup(ctx: dict) -> None:
    from src.core.redis_client import get_redis
    logger.info("arq_worker_startup")
    await get_redis()


async def shutdown(ctx: dict) -> None:
    from src.core.redis_client import close_redis
    logger.info("arq_worker_shutdown")
    await close_redis()


class WorkerSettings:
    functions = [process_event, run_agent_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    max_tries = 3
    job_timeout = 300

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
