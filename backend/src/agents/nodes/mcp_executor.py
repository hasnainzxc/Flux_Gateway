"""MCP executor node — real write-back execution against tenant's PostgreSQL database."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select

from src.agents.state import AgentState
from src.db.models import Connection
from src.services.mcp_client import mcp_client

logger = structlog.get_logger(__name__)


async def mcp_exec_node(
    state: AgentState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Execute validated SQL against the tenant's connected PostgreSQL database.

    Only reached after sandbox review passes (safe code only).
    Decrypts the stored connection string, executes inside a transaction,
    and returns structured result for downstream formatting.
    """
    generated_code = state.get("generated_code", "") or ""
    connection_id = state.get("connection_id")
    review_passed = state.get("review_passed", False)
    target_system = state.get("target_system", "unknown")

    # No code to execute — nothing to do
    if not generated_code.strip():
        logger.info("mcp_exec_no_code")
        return {
            "execution_result": {
                "status": "failed",
                "error": "No generated code to execute",
                "statement": "",
                "dry_run": True,
            },
            "node_traces": [
                {
                    "node": "mcp_exec",
                    "status": "failed",
                    "error": "No generated code",
                }
            ],
        }

    # No connection configured — dry-run fallback
    if not connection_id:
        logger.info("mcp_exec_no_connection", target=target_system)
        result = await mcp_client.execute_write(
            encrypted_connection_string=b"",
            statement=generated_code,
            review_passed=bool(review_passed),
        )
        return {
            "execution_result": {
                "status": result.status,
                "rows_affected": result.rows_affected,
                "error": result.error,
                "statement": result.statement,
                "dry_run": result.dry_run,
            },
            "node_traces": [
                {
                    "node": "mcp_exec",
                    "status": result.status,
                    "target": target_system,
                    "dry_run": result.dry_run,
                }
            ],
        }

    # Fetch encrypted connection string from DB
    session = None
    if config and config.get("configurable"):
        session = config["configurable"].get("session")

    encrypted_conn_str: bytes = b""
    if session is not None:
        try:
            import uuid as _uuid

            conn_result = await session.execute(
                select(Connection).where(
                    Connection.id == _uuid.UUID(str(connection_id))
                )
            )
            connection = conn_result.scalar_one_or_none()
            if connection is not None:
                encrypted_conn_str = connection.encrypted_connection_string
                logger.info(
                    "mcp_connection_loaded",
                    connection_id=str(connection_id),
                    db_type=connection.db_type,
                )
            else:
                logger.warning("mcp_connection_not_found", connection_id=str(connection_id))
        except Exception as exc:
            logger.warning("mcp_connection_fetch_error", error=str(exc)[:200])

    # Execute the validated SQL
    result = await mcp_client.execute_write(
        encrypted_connection_string=encrypted_conn_str,
        statement=generated_code,
        review_passed=bool(review_passed),
    )

    logger.info(
        "mcp_exec_complete",
        status=result.status,
        rows_affected=result.rows_affected,
        dry_run=result.dry_run,
    )

    return {
        "execution_result": {
            "status": result.status,
            "rows_affected": result.rows_affected,
            "error": result.error,
            "statement": result.statement,
            "dry_run": result.dry_run,
        },
        "node_traces": [
            {
                "node": "mcp_exec",
                "status": result.status,
                "target": target_system,
                "rows_affected": result.rows_affected,
                "dry_run": result.dry_run,
            }
        ],
    }
