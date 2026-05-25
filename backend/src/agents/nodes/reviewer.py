from __future__ import annotations

import re
from typing import Any

import structlog

from src.agents.state import AgentState

logger = structlog.get_logger(__name__)

DANGEROUS_PATTERNS = [
    (r"\bDROP\b", "DROP operations are not permitted"),
    (r"\bTRUNCATE\b", "TRUNCATE operations are not permitted"),
    (r"\bALTER\b", "ALTER operations are not permitted"),
    (r"\bCREATE\b", "CREATE operations are not permitted"),
    (r"\bGRANT\b", "GRANT operations are not permitted"),
    (r"\bREVOKE\b", "REVOKE operations are not permitted"),
    (r"COPY\s+.*\s+FROM", "COPY FROM operations are not permitted"),
    (r";\s*--", "Potential SQL injection via comment"),
    (r"\bOR\s+1\s*=\s*1\b", "Tautology injection pattern detected"),
    (r"\bOR\s+'[^']*'\s*=\s*'[^']*'\b", "Tautology string injection pattern detected"),
]


def _check_dangerous_ops(code: str) -> list[str]:
    errors: list[str] = []
    for pattern, message in DANGEROUS_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            errors.append(f"Dangerous: {message}")
    return errors


def _check_parameterized(code: str) -> list[str]:
    if re.search(r"\$\d+", code):
        return []
    is_read_only = re.search(
        r"SELECT\b", code, re.IGNORECASE
    ) and not re.search(r"(INSERT|UPDATE|DELETE)", code, re.IGNORECASE)
    if is_read_only:
        return []
    return ["Non-parameterized write query. Use $1, $2 notation for values."]


def _check_columns_exist(code: str, schema_graph: dict) -> list[str]:
    errors: list[str] = []
    if not schema_graph or "tables" not in schema_graph:
        return errors

    valid_columns: dict[str, set[str]] = {}
    for table in schema_graph["tables"]:
        tname = table["name"]
        valid_columns[tname] = {col["name"].lower() for col in table.get("columns", [])}

    column_refs = re.findall(r'"(\w+)"\s*\.\s*"(\w+)"', code)
    column_refs += re.findall(r"\b(\w+)\.(\w+)\b", code)

    for tbl, col in column_refs:
        tbl_lower = tbl.lower()
        col_lower = col.lower()
        if tbl_lower in valid_columns and col_lower not in valid_columns[tbl_lower]:
            errors.append(
                f"Column '{col}' does not exist in table '{tbl}'. "
                f"Available: {sorted(valid_columns[tbl_lower])}"
            )

    return errors


async def reviewer_node(
    state: AgentState, config: dict[str, Any] | None = None
) -> dict:
    code = state.get("generated_code", "") or ""
    schema_graph = state.get("schema_graph") or {}

    errors: list[str] = []

    if not code.strip():
        errors.append("No code generated to review")

    errors.extend(_check_dangerous_ops(code))
    errors.extend(_check_parameterized(code))
    errors.extend(_check_columns_exist(code, schema_graph))

    review_passed = len(errors) == 0

    logger.info(
        "review_complete",
        passed=review_passed,
        error_count=len(errors),
        code_len=len(code),
    )

    return {
        "review_passed": review_passed,
        "review_errors": errors,
        "node_traces": [
            {
                "node": "reviewer",
                "passed": review_passed,
                "error_count": len(errors),
                "errors": errors if errors else None,
            }
        ],
    }
