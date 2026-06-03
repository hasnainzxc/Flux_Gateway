"""Researcher node — RAG-powered answer generation for read intents."""

from __future__ import annotations

from typing import Any

import structlog

from src.agents.state import AgentState
from src.services.llm import llm_complete
from src.services.rag_query import build_context_from_results, hybrid_search

logger = structlog.get_logger(__name__)


async def researcher_node(
    state: AgentState, config: dict[str, Any] | None = None
) -> dict:
    """
    Read-path node: hybrid search (vector + BM25) -> build context -> LLM answer with citations.
    Gets DB session from config (passed by graph.ainvoke, not FastAPI DI).
    """
    tenant_id = state["tenant_id"]
    query = state["user_query"]

    # Extract DB session from LangGraph config — not available via FastAPI DI in workers
    session = None
    if config and "configurable" in config:
        session = config["configurable"].get("session")

    if session is None:
        return {
            "final_response": "Session not available for database access.",
            "retrieved_chunks": [],
            "citations": [],
            "tokens_used": state.get("tokens_used", 0),
            "node_traces": [{"node": "researcher", "chunks_found": 0, "error": "no_session"}],
        }

    # Hybrid search: vector (semantic) + BM25 (keyword), fused via RRF
    search_results = await hybrid_search(session, tenant_id, query, top_k=10)

    if not search_results:
        return {
            "final_response": (
                "No relevant documents found. "
                "Try uploading documents or asking about your database schema."
            ),
            "retrieved_chunks": [],
            "citations": [],
            "tokens_used": state.get("tokens_used", 0),
            "node_traces": [{"node": "researcher", "chunks_found": 0}],
        }

    context, citations = await build_context_from_results(search_results)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a data analyst. Answer using ONLY the provided context.\n"
                "Cite sources with [1], [2], etc. matching the context markers.\n"
                "If the context does not answer the question, say so clearly.\n"
                "Be concise and accurate."
            ),
        },
        {
            "role": "user",
            "content": f"Context:\n\n{context}\n\nQuestion: {query}",
        },
    ]

    answer, tokens = await llm_complete(messages, max_tokens=2000)

    logger.info("research_complete", chunks=len(search_results), citations=len(citations))

    return {
        "final_response": answer,
        "retrieved_chunks": search_results,
        "citations": citations,
        "tokens_used": state.get("tokens_used", 0) + tokens,
        "node_traces": [
            {
                "node": "researcher",
                "chunks_found": len(search_results),
                "citations": len(citations),
                "model": "gpt-4o",
                "tokens": tokens,
            }
        ],
    }
