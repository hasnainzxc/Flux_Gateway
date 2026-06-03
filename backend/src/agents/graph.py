"""
LangGraph agent orchestration — builds state machine with conditional routing:
classify -> (read: researcher | write: coder -> reviewer -> (pass: exec | fail: heal -> coder)) -> format
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.nodes import (
    classify_intent_node,
    coder_node,
    format_response_node,
    mcp_exec_node,
    researcher_node,
    reviewer_node,
    self_heal_node,
)
from src.agents.state import AgentState


def route_after_classify(state: AgentState) -> str:
    """Route based on intent: read -> researcher, write -> coder, unknown -> format (error)."""
    intent = state.get("intent", "read")
    if intent == "read":
        return "researcher_node"  # RAG search + LLM answer
    elif intent == "write":
        return "coder_node"  # SQL generation -> review -> exec
    # unknown intent -> skip to format with error
    return "format_response_node"


def route_after_review(state: AgentState) -> str:
    """Route based on sandbox review: passed -> exec, failed -> self-heal."""
    if state.get("review_passed"):
        return "mcp_exec_node"  # safe to execute against target system
    return "self_heal_node"  # LLM attempts to fix errors


def route_after_heal(state: AgentState) -> str:
    """Route after self-heal attempt: error or max retries -> format, else retry coder."""
    if state.get("error"):
        return "format_response_node"  # unrecoverable — surface error
    if state.get("retry_count", 0) >= state.get("max_retries", 3):
        return "format_response_node"  # exhausted retry budget
    return "coder_node"  # retry: re-generate -> re-review


def build_agent_graph() -> StateGraph:
    """
    Build + compile the agent state machine.
    Flow: classify -> (read|write|unknown) -> ... -> format -> END
    Write path includes retry loop: coder -> reviewer -> (pass: exec | fail: heal -> coder)
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("classify_intent_node", classify_intent_node)
    workflow.add_node("researcher_node", researcher_node)
    workflow.add_node("coder_node", coder_node)
    workflow.add_node("reviewer_node", reviewer_node)
    workflow.add_node("self_heal_node", self_heal_node)
    workflow.add_node("mcp_exec_node", mcp_exec_node)
    workflow.add_node("format_response_node", format_response_node)

    workflow.set_entry_point("classify_intent_node")

    # Conditional routing after intent classification
    workflow.add_conditional_edges(
        "classify_intent_node",
        route_after_classify,
        {
            "researcher_node": "researcher_node",
            "coder_node": "coder_node",
            "format_response_node": "format_response_node",
        },
    )

    workflow.add_edge("researcher_node", "format_response_node")
    workflow.add_edge("coder_node", "reviewer_node")

    # Conditional routing after sandbox review
    workflow.add_conditional_edges(
        "reviewer_node",
        route_after_review,
        {
            "mcp_exec_node": "mcp_exec_node",
            "self_heal_node": "self_heal_node",
        },
    )

    # Conditional routing after self-heal (retry loop or give up)
    workflow.add_conditional_edges(
        "self_heal_node",
        route_after_heal,
        {
            "coder_node": "coder_node",
            "format_response_node": "format_response_node",
        },
    )

    workflow.add_edge("mcp_exec_node", "format_response_node")
    workflow.add_edge("format_response_node", END)

    return workflow.compile()


async def run_agent(
    session: object,
    tenant_id: str,
    user_query: str,
    connection_id: str | None = None,
    user_role: str = "analyst",
    max_retries: int = 3,
) -> dict:
    """
    High-level agent entrypoint used by workers.
    Loads schema cache if connection_id provided, builds initial state, invokes graph.
    Returns normalized result dict for usage tracking + WebSocket updates.
    """
    import contextlib
    import json as _json

    from sqlalchemy import select as _select

    from src.db.models import SchemaCache

    # Load cached schema graph if connection specified
    schema_graph = None
    if connection_id:
        result = await session.execute(
            _select(SchemaCache)
            .where(SchemaCache.connection_id == connection_id)
            .order_by(SchemaCache.created_at.desc())
            .limit(1)
        )
        cache = result.scalar_one_or_none()
        if cache:
            with contextlib.suppress(ValueError, TypeError):
                schema_graph = _json.loads(cache.schema_graph)

    initial_state: AgentState = {
        "tenant_id": tenant_id,
        "user_query": user_query,
        "user_role": user_role,
        "connection_id": connection_id,
        "intent": "unknown",
        "schema_graph": schema_graph,
        "retrieved_chunks": [],
        "citations": [],
        "generated_code": None,
        "target_system": None,
        "review_passed": None,
        "review_errors": [],
        "retry_count": 0,
        "max_retries": max_retries,
        "final_response": None,
        "execution_result": None,
        "error": None,
        "tokens_used": 0,
        "latency_ms": 0,
        "node_traces": [],
    }

    graph = build_agent_graph()
    # Pass session via config so nodes can access DB without FastAPI dependency injection
    result_state = await graph.ainvoke(
        initial_state, config={"configurable": {"session": session}}
    )

    return {
        "answer": result_state.get("final_response", ""),
        "intent": result_state.get("intent", "unknown"),
        "citations": result_state.get("citations", []),
        "execution_result": result_state.get("execution_result"),
        "tokens_input": result_state.get("tokens_used", 0),
        "tokens_output": result_state.get("tokens_used", 0),
        "node_traces": result_state.get("node_traces", []),
    }
