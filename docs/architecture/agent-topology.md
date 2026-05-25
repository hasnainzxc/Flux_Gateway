# Agent Topology — LangGraph State Machine

> Detailed node definitions, transitions, and state shape.

## State Machine Diagram

```
                               ┌──────────┐
                               │  __start__ │
                               └─────┬────┘
                                     │
                                     ▼
                           ┌──────────────────┐
                           │ classify_intent   │
                           │ (LLM: gpt-4o-mini)│
                           └────────┬─────────┘
                                    │
                       ┌────────────┴────────────┐
                       │ intent == "read"        │ intent == "write"
                       ▼                         ▼
              ┌──────────────────┐    ┌──────────────────┐
              │ researcher_node  │    │   coder_node      │
              │ (pgvector RAG)   │    │ (schema-grounded  │
              │                  │    │  code generation) │
              └────────┬─────────┘    └────────┬─────────┘
                       │                       │
                       │                       ▼
                       │            ┌──────────────────┐
                       │            │  reviewer_node    │
                       │            │ (sandbox dry-run) │
                       │            └────────┬─────────┘
                       │                     │
                       │         ┌───────────┴───────────┐
                       │         │ review_passed == true │ review_passed == false
                       │         ▼                       ▼
                       │  ┌──────────────────┐ ┌──────────────────┐
                       │  │  mcp_exec_node   │ │ self_heal_node   │
                       │  │ (execute on      │ │ (parse error →   │
                       │  │  target system)  │ │  fix → retry)    │
                       │  └────────┬─────────┘ └────────┬─────────┘
                       │           │                     │
                       │           │          ┌──────────┴──────────┐
                       │           │          │ retry_count < max  │ retry_count >= max
                       │           │          ▼                    ▼
                       │           │  ┌──────────────┐   ┌──────────────────┐
                       │           │  │ coder_node   │   │  error_response  │
                       │           │  │ (regenerate) │   │  (return error   │
                       │           │  └──────────────┘   │   to user)       │
                       │           │                     └────────┬─────────┘
                       │           │                              │
                       └───────────┴──────────────────────────────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │ format_response   │
                         │ (add citations,   │
                         │  telemetry, etc.) │
                         └────────┬─────────┘
                                  │
                                  ▼
                              ┌──────────┐
                              │ __end__  │
                              └──────────┘
```

## State Shape

```python
class Chunk(TypedDict):
    id: str
    content: str
    doc_name: str
    page: int
    score: float

class AgentState(TypedDict):
    # ── Request context ──
    tenant_id: str
    user_query: str
    user_role: str
    session_id: str
    
    # ── Routing ──
    intent: Literal["read", "write", "unknown"]
    
    # ── Schema context (injected at graph entry) ──
    schema_graph: dict | None       # Full JSON schema for tenant's connection
    connection_id: str | None       # Which DB/API to interact with
    
    # ── READ path ──
    retrieved_chunks: list[Chunk]   # Top-K RAG results
    citations: list[dict]           # Citation metadata for response
    
    # ── WRITE path ──
    generated_code: str | None      # Generated SQL/API code
    target_system: str | None       # "postgresql", "mysql", "odoo_api"
    
    # ── Review ──
    review_passed: bool | None
    review_errors: list[str]
    retry_count: int
    max_retries: int                # Default: 3
    
    # ── Output ──
    final_response: str | None
    execution_result: dict | None   # Raw result from MCP execution
    error: str | None
    
    # ── Telemetry ──
    tokens_used: int
    latency_ms: float
    node_traces: list[dict]         # Per-node timing
```

## Node Implementations Reference

### classify_intent_node
- **Model**: gpt-4o-mini (cheap, fast)
- **Input**: `state.user_query`
- **Output**: `state.intent` ∈ {"read", "write"}
- **Prompt**: Binary classification with examples
- **Fallback**: If LLM fails, default to "read" (safer)

### researcher_node
- **Input**: `state.user_query`, `state.tenant_id`
- **Services**: `rag_service.hybrid_search()`, `llm.invoke()`
- **Output**: `state.retrieved_chunks`, `state.final_response`, `state.citations`
- **RAG pipeline**: Embed → vector search + BM25 → RRF fusion → context assembly → LLM answer
- **Citations**: Inline [1] markers + metadata array

### coder_node
- **Input**: `state.user_query`, `state.schema_graph`
- **Model**: gpt-4o (accurate, expensive)
- **Output**: `state.generated_code`
- **Prompt**: Schema-grounded, strict column name usage, parameterized queries

### reviewer_node
- **Input**: `state.generated_code`, `state.schema_graph`
- **Service**: `sandbox_service`
- **Output**: `state.review_passed`, `state.review_errors`
- **Sandbox**: Ephemeral Docker, no network, tmpfs, 256MB RAM, 30s timeout
- **Checks**: Syntax validity, table/column existence, no dangerous operations (DROP, TRUNCATE, etc.)

### self_heal_node
- **Input**: `state.generated_code`, `state.review_errors`, `state.retry_count`
- **Model**: gpt-4o
- **Output**: `state.generated_code` (fixed), `state.retry_count` (incremented)
- **Max retries**: 3
- **On max retries**: Set `state.error` with context, route to error_response

### mcp_exec_node
- **Input**: `state.generated_code`, `state.connection_id`, `state.tenant_id`
- **Service**: `mcp_client`
- **Output**: `state.execution_result`
- **Protocol**: JSON-RPC 2.0 over HTTPS to client's MCP Server

### format_response_node
- **Input**: All state fields
- **Output**: `state.final_response` (formatted)
- **Additions**: Citation formatting, token count, latency, log to event_log

## Edge Conditions

```python
def route_after_classify(state: AgentState) -> str:
    if state["intent"] == "read":
        return "researcher_node"
    elif state["intent"] == "write":
        return "coder_node"
    else:
        return "format_response_node"  # Unknown → return error

def route_after_review(state: AgentState) -> str:
    if state["review_passed"]:
        return "mcp_exec_node"
    else:
        return "self_heal_node"

def route_after_heal(state: AgentState) -> str:
    if state["retry_count"] < state["max_retries"]:
        return "coder_node"
    else:
        return "format_response_node"  # Max retries → error to user
```

## Build Graph

```python
from langgraph.graph import StateGraph, END

def build_agent_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("researcher_node", researcher_node)
    workflow.add_node("coder_node", coder_node)
    workflow.add_node("reviewer_node", reviewer_node)
    workflow.add_node("self_heal_node", self_heal_node)
    workflow.add_node("mcp_exec_node", mcp_exec_node)
    workflow.add_node("format_response_node", format_response_node)
    
    # Set entry
    workflow.set_entry_point("classify_intent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "researcher_node": "researcher_node",
            "coder_node": "coder_node",
            "format_response_node": "format_response_node",
        }
    )
    
    workflow.add_edge("researcher_node", "format_response_node")
    workflow.add_edge("coder_node", "reviewer_node")
    
    workflow.add_conditional_edges(
        "reviewer_node",
        route_after_review,
        {
            "mcp_exec_node": "mcp_exec_node",
            "self_heal_node": "self_heal_node",
        }
    )
    
    workflow.add_conditional_edges(
        "self_heal_node",
        route_after_heal,
        {
            "coder_node": "coder_node",
            "format_response_node": "format_response_node",
        }
    )
    
    workflow.add_edge("mcp_exec_node", "format_response_node")
    workflow.add_edge("format_response_node", END)
    
    return workflow.compile()
```

## Model Selection Strategy

| Task | Model | Rationale |
|------|-------|-----------|
| Intent classification | gpt-4o-mini | Simple binary, cheap |
| Research/RAG answer | gpt-4o | Needs accuracy + citations |
| Code generation | gpt-4o | High stakes, needs precision |
| Code fix (self-heal) | gpt-4o | Needs to understand errors |
| Sandbox review | N/A (rule-based) | Deterministic validation |

## Future: Multi-Agent Extensions

- **Supervisor Agent**: Routes complex multi-step tasks across sub-agents
- **Specialist Agents**: Inventory agent, Support agent, Report agent (fine-tuned per domain)
- **Human-in-the-Loop**: Conditional interrupt before high-risk writes
- **Agent Memory**: Conversation history across sessions (per user/tenant)
