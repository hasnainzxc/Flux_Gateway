"""
MCP write-back client — real executor replacing the Stage-3 stub.

Executes already-validated SQL write statements against the tenant's connected
PostgreSQL database. Uses asyncpg for async DB access, runs inside an explicit
transaction, and enforces a configurable statement timeout.

The module is structured so the transport layer could later be swapped for a
JSON-RPC MCP protocol. For now it executes directly against the tenant DB via
asyncpg, using the encrypted connection string stored in the Connection model.

Safety guarantees:
- Only executes when review_passed is True (validated by sandbox reviewer).
- Runs inside an explicit transaction (auto-rollback on error).
- Supports dry-run / EXPLAIN mode controlled by MCP_EXECUTE_ENABLED config.
- Enforces a configurable statement timeout (MCP_STATEMENT_TIMEOUT).
- Default behavior is dry-run when MCP_EXECUTE_ENABLED is false.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import asyncpg
import structlog

from src.core.config import settings
from src.core.security import decrypt_value

logger = structlog.get_logger(__name__)


@dataclass
class MCPExecutionResult:
    """Result from MCP write-back execution."""

    status: str  # "executed" | "dry_run" | "failed"
    rows_affected: int | None = None
    error: str | None = None
    statement: str = ""
    dry_run: bool = True


class MCPClient:
    """
    Async service for executing validated SQL against a tenant's PostgreSQL DB.

    Decrypts the stored Fernet-encrypted connection string, connects via asyncpg,
    and executes the statement inside an explicit transaction.

    When MCP_EXECUTE_ENABLED is false, returns a dry_run result without touching
    the target database.
    """

    def __init__(
        self,
        execute_enabled: bool | None = None,
        statement_timeout: int | None = None,
    ) -> None:
        self._execute_enabled = (
            execute_enabled if execute_enabled is not None else settings.mcp_execute_enabled
        )
        self._statement_timeout = (
            statement_timeout if statement_timeout is not None else settings.mcp_statement_timeout
        )

    async def execute_write(
        self,
        encrypted_connection_string: bytes,
        statement: str,
        review_passed: bool,
        parameters: list[Any] | None = None,
    ) -> MCPExecutionResult:
        """
        Execute a validated SQL write statement against the tenant's DB.

        Args:
            encrypted_connection_string: Fernet-encrypted DSN from Connection model.
            statement: The validated SQL statement to execute.
            review_passed: Must be True — only sandbox-approved SQL reaches here.
            parameters: Optional list of parameter values for parameterized queries.

        Returns:
            MCPExecutionResult with status, rows_affected, and error info.
        """
        if not review_passed:
            return MCPExecutionResult(
                status="failed",
                error="Review did not pass — refusing to execute unvalidated SQL",
                statement=statement,
                dry_run=True,
            )

        if not self._execute_enabled:
            logger.info(
                "mcp_dry_run",
                reason="MCP_EXECUTE_ENABLED=false",
                statement_preview=statement[:120],
            )
            return MCPExecutionResult(
                status="dry_run",
                statement=statement,
                dry_run=True,
            )

        # Decrypt the connection string
        try:
            dsn = decrypt_value(encrypted_connection_string)
        except Exception as exc:
            logger.error("mcp_decrypt_failed", error=str(exc))
            return MCPExecutionResult(
                status="failed",
                error=f"Failed to decrypt connection string: {exc}",
                statement=statement,
                dry_run=True,
            )

        # Parse DSN to validate it's a PostgreSQL connection
        try:
            parsed = urlparse(dsn)
            if parsed.scheme not in ("postgresql", "postgres"):
                return MCPExecutionResult(
                    status="failed",
                    error=f"Unsupported database type: {parsed.scheme} (expected postgresql)",
                    statement=statement,
                    dry_run=True,
                )
        except Exception as exc:
            return MCPExecutionResult(
                status="failed",
                error=f"Invalid connection string: {exc}",
                statement=statement,
                dry_run=True,
            )

        # Execute inside explicit transaction with timeout
        return await self._execute_in_transaction(dsn, statement, parameters)

    async def _execute_in_transaction(
        self,
        dsn: str,
        statement: str,
        parameters: list[Any] | None = None,
    ) -> MCPExecutionResult:
        """Connect to target DB, run statement in transaction, return result."""
        conn: asyncpg.Connection | None = None
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn=dsn),
                timeout=self._statement_timeout,
            )
            assert conn is not None  # asyncpg.connect always returns a Connection

            # Set statement timeout at session level
            await conn.execute(f"SET statement_timeout = '{self._statement_timeout}s'")

            async with conn.transaction():
                if parameters:
                    result = await conn.execute(statement, *parameters)
                else:
                    result = await conn.execute(statement)

            # asyncpg execute returns status string like "INSERT 0 1" or "UPDATE 5"
            rows_affected = self._parse_rows_affected(result)

            logger.info(
                "mcp_executed",
                status=result,
                rows_affected=rows_affected,
            )

            return MCPExecutionResult(
                status="executed",
                rows_affected=rows_affected,
                statement=statement,
                dry_run=False,
            )

        except TimeoutError:
            logger.error("mcp_timeout", timeout=self._statement_timeout)
            return MCPExecutionResult(
                status="failed",
                error=f"Statement timeout after {self._statement_timeout}s",
                statement=statement,
                dry_run=False,
            )
        except asyncpg.PostgresError as exc:
            logger.error("mcp_postgres_error", error=str(exc)[:200])
            return MCPExecutionResult(
                status="failed",
                error=str(exc),
                statement=statement,
                dry_run=False,
            )
        except Exception as exc:
            logger.error("mcp_unexpected_error", error=str(exc)[:200])
            return MCPExecutionResult(
                status="failed",
                error=f"Unexpected error: {exc}",
                statement=statement,
                dry_run=False,
            )
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    await conn.close()

    @staticmethod
    def _parse_rows_affected(status: str) -> int | None:
        """
        Parse asyncpg command status string to extract rows affected.

        Examples: "INSERT 0 1" -> 1, "UPDATE 5" -> 5, "DELETE 3" -> 3,
                  "SELECT 10" -> 10, "" -> None
        """
        if not status:
            return None
        parts = status.split()
        # INSERT returns "INSERT 0 <count>", UPDATE/DELETE/SELECT return "<CMD> <count>"
        if parts[0] == "INSERT" and len(parts) >= 3:
            try:
                return int(parts[-1])
            except ValueError:
                return None
        if parts[0] in ("UPDATE", "DELETE", "SELECT") and len(parts) >= 2:
            try:
                return int(parts[-1])
            except ValueError:
                return None
        return None


# Singleton — imported by agent nodes
mcp_client = MCPClient()
