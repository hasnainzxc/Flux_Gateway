from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict


class AgentState(TypedDict):
    tenant_id: str
    user_query: str
    user_role: str
    connection_id: str | None

    intent: Literal["read", "write", "unknown"]

    schema_graph: dict[str, Any] | None

    retrieved_chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]

    generated_code: str | None
    target_system: str | None

    review_passed: bool | None
    review_errors: list[str]
    retry_count: int
    max_retries: int

    final_response: str | None
    execution_result: dict[str, Any] | None
    error: str | None

    tokens_used: int
    latency_ms: float
    node_traces: list[dict[str, Any]]
