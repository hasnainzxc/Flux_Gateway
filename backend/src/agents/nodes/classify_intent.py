"""Intent classification node — LLM determines if query is read (SELECT) or write (INSERT/UPDATE/DELETE)."""

from __future__ import annotations

from typing import Any

import structlog

from src.agents.state import AgentState
from src.services.llm import llm_complete

logger = structlog.get_logger(__name__)


async def classify_intent_node(
    state: AgentState, config: dict[str, Any] | None = None
) -> dict:
    """
    Classify user query as 'read' or 'write' using cheap/fast model (gpt-4o-mini).
    Defaults to 'read' on ambiguous output (safer — read-only path).
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a request classifier. Determine if the user wants to:\n"
                "- 'read': retrieve, query, search, analyze, or find data\n"
                "- 'write': insert, update, delete, modify, create, or change data\n"
                "Respond with exactly one word: read or write."
            ),
        },
        {"role": "user", "content": state["user_query"]},
    ]

    response, tokens = await llm_complete(
        messages, model="openai/gpt-4o-mini", temperature=0.0, max_tokens=10
    )
    intent_raw = response.strip().lower()

    # Normalize to read/write, default to read if unclear
    intent: str
    if intent_raw == "write":
        intent = "write"
    elif intent_raw == "read":
        intent = "read"
    else:
        intent = "read"

    logger.info("intent_classified", intent=intent, query=state["user_query"][:80])

    return {
        "intent": intent,
        "tokens_used": state.get("tokens_used", 0) + tokens,
        "node_traces": [
            {"node": "classify_intent", "intent": intent, "model": "gpt-4o-mini", "tokens": tokens}
        ],
    }
