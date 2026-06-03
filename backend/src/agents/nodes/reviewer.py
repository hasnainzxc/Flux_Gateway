"""Reviewer node — sandbox validation of generated SQL/code before execution."""

from __future__ import annotations

from typing import Any

import structlog

from src.agents.state import AgentState
from src.services.sandbox import sandbox_service

logger = structlog.get_logger(__name__)


async def reviewer_node(
    state: AgentState, config: dict[str, Any] | None = None
) -> dict:
    """
    Validate generated code in Docker sandbox. Checks for:
    - Dangerous ops (DROP, TRUNCATE, ALTER)
    - SQL injection patterns
    - Schema mismatches (column doesn't exist)
    Falls back to regex validation if Docker unavailable.
    """
    code = state.get("generated_code", "") or ""
    schema_graph = state.get("schema_graph") or {}
    tenant_id = state["tenant_id"]

    # Empty code = nothing to validate, fail fast
    if not code.strip():
        return {
            "review_passed": False,
            "review_errors": ["No code generated to review"],
            "node_traces": [
                {"node": "reviewer", "passed": False, "error_count": 1, "errors": ["No code generated to review"]}
            ],
        }

    # Run sandbox validation — Docker or regex fallback
    result = await sandbox_service.validate_sql(tenant_id, code, schema_graph)

    logger.info(
        "review_complete",
        passed=result.passed,
        error_count=len(result.errors),
        code_len=len(code),
        sandbox_used=result.stdout != "",
    )

    return {
        "review_passed": result.passed,
        "review_errors": result.errors,
        "node_traces": [
            {
                "node": "reviewer",
                "passed": result.passed,
                "error_count": len(result.errors),
                "errors": result.errors if result.errors else None,
            }
        ],
    }
