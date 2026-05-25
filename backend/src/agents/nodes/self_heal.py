from __future__ import annotations

import structlog

from src.agents.state import AgentState
from src.services.llm import llm_complete

logger = structlog.get_logger(__name__)


async def self_heal_node(state: AgentState) -> dict:
    code = state.get("generated_code", "") or ""
    errors = state.get("review_errors", [])
    retry_count = state.get("retry_count", 0) + 1
    max_retries = state.get("max_retries", 3)

    if retry_count > max_retries:
        logger.warning("self_heal_max_retries", retries=retry_count)
        return {
            "retry_count": retry_count,
            "error": f"Max retries ({max_retries}) exceeded. Last errors: {'; '.join(errors)}",
            "final_response": f"Unable to generate a safe query after {max_retries} attempts. Errors: {'; '.join(errors)}",
            "node_traces": [
                {
                    "node": "self_heal",
                    "status": "max_retries_exceeded",
                    "retry_count": retry_count,
                }
            ],
        }

    error_text = "\n".join(f"- {e}" for e in errors)

    messages = [
        {
            "role": "system",
            "content": (
                "You fix SQL queries that failed review. Generate a corrected version.\n"
                "Use parameterized queries ($1, $2). Use ONLY correct column names.\n"
                "Return ONLY the fixed SQL, no explanation."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Original query:\n{code}\n\n"
                f"Review errors:\n{error_text}\n\n"
                f"Fix the errors and return the corrected SQL."
            ),
        },
    ]

    fixed_code = await llm_complete(messages, model="openai/gpt-4o", max_tokens=2000)
    fixed_code = fixed_code.strip()

    logger.info("self_heal_applied", retry=retry_count, new_len=len(fixed_code))

    return {
        "generated_code": fixed_code,
        "retry_count": retry_count,
        "review_passed": False,
        "review_errors": [],
        "tokens_used": state.get("tokens_used", 0) + 300,
        "node_traces": [
            {
                "node": "self_heal",
                "retry": retry_count,
                "new_code_length": len(fixed_code),
                "model": "gpt-4o",
            }
        ],
    }
