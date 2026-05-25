from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.state import AgentState
from src.services.llm import llm_complete_json

logger = structlog.get_logger(__name__)


async def coder_node(
    state: AgentState, config: dict[str, Any] | None = None
) -> dict:
    schema_graph = state.get("schema_graph") or {}
    query = state["user_query"]

    schema_json = json.dumps(schema_graph, indent=2)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a SQL generator. Generate parameterized queries ($1, $2, ...).\n"
                "Use ONLY table and column names from the provided schema.\n"
                "Never invent column names. Never use raw string interpolation.\n"
                "Wrap identifiers with double quotes.\n"
                "Return JSON: {\"sql\": \"query\", \"explanation\": \"what it does\", "
                "\"target_system\": \"postgresql\", \"parameters\": [\"val1\", \"val2\"]}"
            ),
        },
        {
            "role": "user",
            "content": f"Schema:\n{schema_json}\n\nGenerate SQL for: {query}",
        },
    ]

    result, tokens = await llm_complete_json(messages, model="openai/gpt-4o")

    generated_code = result.get("sql", "")
    target_system = result.get("target_system", "postgresql")

    logger.info("code_generated", target=target_system, code_len=len(generated_code))

    return {
        "generated_code": generated_code,
        "target_system": target_system,
        "tokens_used": state.get("tokens_used", 0) + tokens,
        "node_traces": [
            {
                "node": "coder",
                "code_length": len(generated_code),
                "target": target_system,
                "model": "gpt-4o",
                "tokens": tokens,
            }
        ],
    }
