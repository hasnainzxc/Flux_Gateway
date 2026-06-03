"""Agent state schema — shared state passed through all LangGraph nodes."""

from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict


class AgentState(TypedDict):
    """
    Mutable state bag passed through every node in the agent graph.
    Each node reads relevant fields, returns partial dict to update.
    """

    # Input context
    tenant_id: str
    user_query: str
    user_role: str
    connection_id: str | None

    # Intent classification result
    intent: Literal["read", "write", "unknown"]

    # Schema metadata for SQL generation/validation
    schema_graph: dict[str, Any] | None

    # RAG search results
    retrieved_chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]

    # Generated SQL/code
    generated_code: str | None
    target_system: str | None

    # Sandbox review + retry state
    review_passed: bool | None
    review_errors: list[str]
    retry_count: int
    max_retries: int

    # Output
    final_response: str | None
    execution_result: dict[str, Any] | None
    error: str | None

    # Telemetry
    tokens_used: int
    latency_ms: float
    node_traces: list[dict[str, Any]]
