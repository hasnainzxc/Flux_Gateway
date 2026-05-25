from __future__ import annotations

import structlog

from src.agents.state import AgentState

logger = structlog.get_logger(__name__)


async def mcp_exec_node(state: AgentState) -> dict:
    code = state.get("generated_code", "")
    target_system = state.get("target_system", "unknown")

    logger.info("mcp_exec_placeholder", target=target_system, code_len=len(code or ""))

    execution_result = {
        "status": "simulated",
        "message": "MCP execution placeholder — real execution will be wired in Stage 3 Week 11",
        "target_system": target_system,
        "query_preview": (code or "")[:200],
    }

    return {
        "execution_result": execution_result,
        "node_traces": [
            {
                "node": "mcp_exec",
                "status": "simulated",
                "target": target_system,
            }
        ],
    }
