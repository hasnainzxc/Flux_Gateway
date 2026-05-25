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
    intent = state.get("intent", "read")
    if intent == "read":
        return "researcher_node"
    elif intent == "write":
        return "coder_node"
    return "format_response_node"


def route_after_review(state: AgentState) -> str:
    if state.get("review_passed"):
        return "mcp_exec_node"
    return "self_heal_node"


def route_after_heal(state: AgentState) -> str:
    if state.get("error"):
        return "format_response_node"
    if state.get("retry_count", 0) >= state.get("max_retries", 3):
        return "format_response_node"
    return "coder_node"


def build_agent_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("classify_intent_node", classify_intent_node)
    workflow.add_node("researcher_node", researcher_node)
    workflow.add_node("coder_node", coder_node)
    workflow.add_node("reviewer_node", reviewer_node)
    workflow.add_node("self_heal_node", self_heal_node)
    workflow.add_node("mcp_exec_node", mcp_exec_node)
    workflow.add_node("format_response_node", format_response_node)

    workflow.set_entry_point("classify_intent_node")

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

    workflow.add_conditional_edges(
        "reviewer_node",
        route_after_review,
        {
            "mcp_exec_node": "mcp_exec_node",
            "self_heal_node": "self_heal_node",
        },
    )

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


agent_graph = build_agent_graph()
