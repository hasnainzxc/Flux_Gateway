# Action Sandbox & LangGraph Agent Orchestration

> **Module**: `backend/src/agents/`  
> **API**: `backend/src/api/v1/agent.py`  
> **Services**: `backend/src/services/sandbox.py`

## Purpose

Secure multi-agent circuit that reads data, generates code/SQL, validates in sandbox, and executes via MCP. Three independent agent nodes + reviewer gate = zero-hallucination, zero-danger execution.

## Agent Topology (LangGraph)

```
                         ┌─────────┐
                         │  START   │
                         └────┬─────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ ClassifyIntent    │ ◄── LLM Call
                    │ (READ vs WRITE)   │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │ READ                        │ WRITE
              ▼                             ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  Researcher Node │          │   Coder Node     │
    │  - pgvector RAG  │          │  - Schema Graph  │
    │  - Context fetch │          │  - SQL/API gen   │
    │  - Answer gen    │          └────────┬─────────┘
    └────────┬─────────┘                   │
             │                             ▼
             │                  ┌──────────────────┐
             │                  │  Reviewer Node   │
             │                  │  - Sandbox exec  │
             │                  │  - Syntax check  │
             │                  │  - Safety lint   │
             │                  └────────┬─────────┘
             │                           │
             │              ┌────────────┴────────────┐
             │              │ PASS                    │ FAIL
             │              ▼                         ▼
             │    ┌──────────────────┐    ┌──────────────────┐
             │    │  MCP Executor    │    │ Self-Healing     │
             │    │  - JSON-RPC call │    │ - Parse error    │
             │    │  - Execute on    │    │ - Generate fix   │
             │    │    target system │    │ - Route to Coder │
             │    └────────┬─────────┘    └────────┬─────────┘
             │             │                       │
             │             │              (retry ≤ 3 times)
             │             │                       │
             │             │              ┌────────┴─────────┐
             │             │              │ After 3 fails →  │
             │             │              │ Return error to  │
             │             │              │ user with context│
             │             │              └──────────────────┘
             │             │
             └─────────────┴──────────────────┐
                                              ▼
                                    ┌──────────────────┐
                                    │ Response Builder │
                                    │ - Format answer  │
                                    │ - Add citations  │
                                    └────────┬─────────┘
                                             │
                                             ▼
                                         ┌──────┐
                                         │ END  │
                                         └──────┘
```

## AgentState (TypedDict)

```python
from typing import TypedDict, Literal, NotRequired
from langgraph.graph import StateGraph

class Chunk(TypedDict):
    id: str
    content: str
    doc_name: str
    page: int
    score: float

class AgentState(TypedDict):
    # Request context
    tenant_id: str
    user_query: str
    user_role: str
    
    # Routing
    intent: Literal["read", "write", "unknown"]
    
    # Schema context (injected at start)
    schema_graph: dict | None
    
    # READ path
    retrieved_chunks: list[Chunk]
    citations: list[dict]
    
    # WRITE path
    generated_code: str | None
    target_system: str | None  # "postgresql", "odoo_api", etc.
    
    # Review
    review_passed: bool | None
    review_errors: list[str]
    retry_count: int
    max_retries: int  # default 3
    
    # Output
    final_response: str | None
    execution_result: dict | None
    error: str | None
```

## Node Implementations

### ClassifyIntent Node

```python
async def classify_intent(state: AgentState) -> AgentState:
    """LLM call to determine READ vs WRITE. Uses cheap/fast model."""
    prompt = f"""
    Classify this user request as "read" or "write":
    
    User: {state["user_query"]}
    
    READ: fetching data, searching, analyzing, reporting, answering questions
    WRITE: updating, creating, deleting, modifying, executing actions
    
    Respond with only "read" or "write".
    """
    
    response = await llm_fast.invoke(prompt)
    state["intent"] = response.strip().lower()
    return state
```

### Researcher Node (READ path)

```python
async def researcher_node(state: AgentState) -> AgentState:
    """Hybrid RAG search → context → answer generation."""
    
    # 1. Hybrid search
    results = await rag_service.hybrid_search(
        tenant_id=state["tenant_id"],
        query=state["user_query"],
        top_k=10,
    )
    state["retrieved_chunks"] = results
    
    # 2. Assemble context with citations
    context_parts = []
    for i, chunk in enumerate(results):
        context_parts.append(
            f"[{i+1}] Source: {chunk.doc_name}, Page {chunk.page}\n"
            f"{chunk.content}\n"
        )
    
    # 3. Generate answer with citations
    prompt = f"""
    Answer the user's question using ONLY the provided context.
    Cite sources using [1], [2] markers.
    
    Context:
    {"".join(context_parts)}
    
    Question: {state["user_query"]}
    
    Answer with citations:
    """
    
    response = await llm.invoke(prompt)
    state["final_response"] = response
    
    # 4. Build citation metadata
    state["citations"] = [
        {
            "id": chunk.id,
            "doc": chunk.doc_name,
            "page": chunk.page,
            "score": chunk.score,
            "excerpt": chunk.content[:200],
        }
        for chunk in results
    ]
    
    return state
```

### Coder Node (WRITE path)

```python
async def coder_node(state: AgentState) -> AgentState:
    """Generate code/SQL grounded in schema graph."""
    
    schema = json.dumps(state["schema_graph"], indent=2)
    
    prompt = f"""
    You have access to this database schema:
    {schema}
    
    Generate SQL to fulfill this request:
    {state["user_query"]}
    
    Rules:
    - Use ONLY table and column names from the schema above
    - Include proper WHERE clauses
    - Use parameterized queries (no string interpolation)
    - Add comments explaining each step
    
    Output ONLY the SQL, nothing else.
    """
    
    code = await llm.invoke(prompt)
    state["generated_code"] = code
    state["retry_count"] = 0
    return state
```

### Reviewer Node (Sandbox Validation)

```python
async def reviewer_node(state: AgentState) -> AgentState:
    """Execute code in ephemeral sandbox for validation."""
    
    code = state["generated_code"]
    schema = state["schema_graph"]
    
    # Spin up sandbox
    sandbox = await sandbox_service.create_sandbox(
        tenant_id=state["tenant_id"],
        code=code,
        schema_metadata=schema,  # schema structure, NO data
    )
    
    try:
        # Dry-run compilation
        result = await sandbox.execute(
            command="dry_run_validate",
            timeout=30,  # seconds
        )
        
        if result.success:
            state["review_passed"] = True
            state["review_errors"] = []
        else:
            state["review_passed"] = False
            state["review_errors"] = result.errors
            
    finally:
        # ALWAYS destroy sandbox
        await sandbox_service.destroy_sandbox(sandbox.id)
    
    return state
```

### Self-Healing Node

```python
async def self_healing_node(state: AgentState) -> AgentState:
    """Parse errors, generate fix, route back to Coder."""
    
    if state["retry_count"] >= state["max_retries"]:
        state["error"] = (
            f"Failed after {state['retry_count']} attempts. "
            f"Last errors: {state['review_errors']}"
        )
        return state
    
    errors = "\n".join(state["review_errors"])
    
    prompt = f"""
    The following code failed validation with these errors:
    
    Code:
    {state["generated_code"]}
    
    Errors:
    {errors}
    
    Generate a FIXED version of the code. Explain what you changed.
    """
    
    fixed_code = await llm.invoke(prompt)
    state["generated_code"] = fixed_code
    state["retry_count"] += 1
    return state
```

## Sandbox Service

```python
# Docker-based sandbox
class DockerSandboxService:
    IMAGE = "flux-sandbox:latest"  # Minimal Python + linting tools
    
    async def create_sandbox(
        self, 
        tenant_id: str, 
        code: str,
        schema_metadata: dict,
    ) -> Sandbox:
        container = await docker.containers.run(
            self.IMAGE,
            command="sleep infinity",  # keep alive for commands
            detach=True,
            network_disabled=True,     # NO network
            mem_limit="256m",
            cpu_quota=50000,           # 0.5 CPU
            tmpfs={"/tmp": "size=64m"},
            labels={
                "tenant_id": tenant_id,
                "purpose": "code-review",
            },
            remove=True,  # auto-remove on stop
        )
        return Sandbox(id=container.id, container=container)
    
    async def execute(self, sandbox: Sandbox, command: str, timeout: int = 30) -> SandboxResult:
        exec_result = await sandbox.container.exec_run(
            f"python -c 'import ast; ast.parse({command!r})'",
            timeout=timeout,
        )
        return SandboxResult(
            success=exec_result.exit_code == 0,
            stdout=exec_result.output.decode(),
            stderr=exec_result.output.decode() if exec_result.exit_code != 0 else "",
        )
    
    async def destroy_sandbox(self, sandbox_id: str):
        container = await docker.containers.get(sandbox_id)
        await container.stop()
        await container.remove(force=True)

# WASM alternative (lighter, faster, no Docker dependency)
class WASMSandboxService:
    async def create_sandbox(self, tenant_id: str, code: str) -> Sandbox:
        # Use wasmtime-py or similar
        # Compile code to WASM
        # Execute in isolated runtime
        pass
```

## MCP Client Integration

```python
class MCPClient:
    """Formats validated payloads as JSON-RPC and communicates with target MCP Server."""
    
    async def execute(
        self,
        tenant_id: str,
        connection_id: str,
        payload: dict,  # validated SQL or API call
    ) -> MCPResult:
        # 1. Get connection details (decrypted)
        connection = await connection_service.get_decrypted(tenant_id, connection_id)
        
        # 2. Build JSON-RPC request
        rpc_request = {
            "jsonrpc": "2.0",
            "method": "execute_query" if connection.db_type == "postgresql" else "api_call",
            "params": payload,
            "id": str(uuid4()),
        }
        
        # 3. Send to MCP Server (runs on client infrastructure)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                connection.mcp_endpoint,
                json=rpc_request,
                headers={"Authorization": f"Bearer {connection.mcp_token}"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                result = await resp.json()
        
        return MCPResult(success=True, data=result)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/agent/query` | Submit NL query → full agent loop |
| GET | `/api/v1/agent/queries/{id}` | Get query result + citations |
| GET | `/api/v1/agent/queries` | List tenant's query history |
| POST | `/api/v1/agent/execute` | Execute validated code on target system |

## Future Enhancements

- Multi-step agent workflows (chained tool calls)
- Human-in-the-loop approval for high-risk writes
- Agent memory (conversation history per session)
- Custom tool definitions (tenant can define their own tools)
- Agent performance analytics (success rate, latency, cost)
