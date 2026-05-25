from __future__ import annotations

import structlog

from src.agents.state import AgentState

logger = structlog.get_logger(__name__)


async def format_response_node(
    state: AgentState, config: dict | None = None
) -> dict:
    intent = state.get("intent", "read")
    final_response = state.get("final_response") or ""
    error = state.get("error") or ""
    citations = state.get("citations", [])
    execution_result = state.get("execution_result") or {}
    tokens_used = state.get("tokens_used", 0)
    node_traces = state.get("node_traces", [])

    if error and not final_response:
        final_response = error

    if intent == "write" and execution_result:
        result_status = execution_result.get("status", "unknown")
        enriched_response = f"{final_response}\n\n[Execution: {result_status}]"
    else:
        enriched_response = final_response

    logger.info(
        "response_formatted",
        intent=intent,
        response_len=len(enriched_response),
        citations=len(citations),
        tokens=tokens_used,
    )

    return {
        "final_response": enriched_response,
        "node_traces": node_traces + [{"node": "format_response", "intent": intent}],
    }
