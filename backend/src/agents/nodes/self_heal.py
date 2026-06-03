"""Self-heal node — retry loop for failed SQL generation. LLM fixes errors from reviewer."""

from __future__ import annotations

import structlog

from src.agents.state import AgentState
from src.services.llm import llm_complete

logger = structlog.get_logger(__name__)


async def self_heal_node(
    state: AgentState, config: dict | None = None
) -> dict:
    """
    Attempt to fix code that failed sandbox review.
    Increments retry_count, asks LLM to correct based on error messages.
    Returns to coder_node for re-review, or gives up after max_retries.
    """
    code = state.get("generated_code", "") or ""
    errors = state.get("review_errors", [])
    retry_count = state.get("retry_count", 0) + 1
    max_retries = state.get("max_retries", 3)

    # Bail out if we've exhausted retry budget
    if retry_count > max_retries:
        logger.warning("self_heal_max_retries", retries=retry_count)
        return {
            "retry_count": retry_count,
            "error": (
                f"Max retries ({max_retries}) exceeded. "
                f"Last errors: {'; '.join(errors)}"
            ),
            "final_response": (
                f"Unable to generate a safe query after {max_retries} attempts. "
                f"Errors: {'; '.join(errors)}"
            ),
            "node_traces": [
                {
                    "node": "self_heal",
                    "status": "max_retries_exceeded",
                    "retry_count": retry_count,
                }
            ],
        }

    # Format errors as bullet list for LLM context
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

    # Use gpt-4o (not mini) for self-heal — needs to understand complex SQL errors
    fixed_code, tokens = await llm_complete(messages, model="openai/gpt-4o", max_tokens=2000)
    fixed_code = fixed_code.strip()

    logger.info("self_heal_applied", retry=retry_count, new_len=len(fixed_code))

    # Reset review state — coder_node will re-submit to reviewer
    return {
        "generated_code": fixed_code,
        "retry_count": retry_count,
        "review_passed": False,  # needs re-review
        "review_errors": [],  # cleared — reviewer will repopulate
        "tokens_used": state.get("tokens_used", 0) + tokens,
        "node_traces": [
            {
                "node": "self_heal",
                "retry": retry_count,
                "new_code_length": len(fixed_code),
                "model": "gpt-4o",
                "tokens": tokens,
            }
        ],
    }
