# Data Flow — Read vs Write Lifecycle Traces

> Complete trace of user actions across both layers: Client App Runtime Loop + LangGraph Data-Plumbing.

## Layer 1: Client App Runtime Loop

```
End-User clicks "Reconcile" / types prompt in Client App
  │
  ▼
Client App Frontend captures Event & Session metadata
  ├── user_prompt: "Show unpaid invoices for Q2"
  ├── user_role: "finance_manager"
  ├── session_id: "sess_abc123"
  └── org_id: "retail_zone_4"
  │
  ▼  POST /api/v1/agent/query (HTTPS + X-API-Key header)
  │
FastAPI Secure Gateway
  ├── Auth Middleware: validate X-API-Key → resolve tenant_id
  ├── Tenant Middleware: set context var current_tenant_id
  ├── Rate Limiter: check token bucket for tenant
  └── Route Handler: build AgentState
  │
  ▼
┌─────────────────────────────────────────────┐
│ LangGraph Orchestration State               │
│ tenant_id: "org_retail_zone_4"              │
│ user_query: "Show unpaid invoices for Q2"   │
│ schema_graph: (fetched from Redis cache)    │
│ retry_count: 0                              │
└─────────────────────────────────────────────┘
  │
  ▼  ClassifyIntent → "read"
  │
  ▼
┌─────────────────────────────────────────────┐
│ Researcher Node                              │
│ 1. pgvector hybrid search                   │
│    WHERE tenant_id = 'org_retail_zone_4'    │
│ 2. Top-10 chunks with similarity scores     │
│ 3. Context assembly with [1]..[10] markers  │
│ 4. LLM generates answer with citations      │
└─────────────────────────────────────────────┘
  │
  ▼
Response:
{
  "answer": "In Q2 there are 47 unpaid invoices totaling $128,450... [1] [3] [7]",
  "citations": [...],
  "tokens_used": 1450,
  "latency_ms": 820
}
  │
  ▼  Return to Client App Frontend
  │
Client App renders:
  ├── Answer text with clickable [1] [3] [7] badges
  ├── Citation side panel (click badge → show source chunk)
  └── Token counter updated
```

## Layer 2: Write Action Trace

```
End-User clicks "Update Inventory" in Client App
  │
  ▼
Client App Frontend
  ├── user_prompt: "Set inventory for SKU-123 to 500 units"
  ├── user_role: "warehouse_manager"
  └── org_id: "retail_zone_4"
  │
  ▼  POST /api/v1/agent/query (HTTPS + X-API-Key)
  │
FastAPI Secure Gateway (same auth flow)
  │
  ▼
LangGraph State:
  tenant_id: "org_retail_zone_4"
  user_query: "Set inventory for SKU-123 to 500 units"
  schema_graph:
    tables:
      - name: inventory
        columns:
          - name: sku (varchar, PK)
          - name: quantity (integer)
          - name: warehouse_id (integer, FK→warehouses.id)
  │
  ▼  ClassifyIntent → "write"
  │
  ▼
┌─────────────────────────────────────────────┐
│ Coder Node                                   │
│ Schema-grounded code generation:            │
│                                             │
│ UPDATE inventory                            │
│ SET quantity = $1                           │
│ WHERE sku = $2                              │
│   AND warehouse_id =                        │
│     (SELECT id FROM warehouses              │
│      WHERE tenant_id = $3);                 │
│                                             │
│ Parameters: [500, "SKU-123", tenant_id]     │
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ Reviewer Node (Docker Sandbox)               │
│                                             │
│ 1. Create ephemeral container:              │
│    - Network: disabled                      │
│    - Memory: 256MB                          │
│    - Storage: tmpfs 64MB                    │
│    - Timeout: 30s                           │
│                                             │
│ 2. Dry-run validation:                      │
│    ✓ Syntax: valid SQL                      │
│    ✓ Table 'inventory' exists in schema     │
│    ✓ Column 'quantity' exists               │
│    ✓ Column 'sku' exists                    │
│    ✓ FK to 'warehouses.id' valid            │
│    ✓ No dangerous operations (DROP, etc.)   │
│    ✓ Parameterized query (no injection)     │
│                                             │
│ 3. Result: PASS                             │
│                                             │
│ 4. Destroy container                        │
└─────────────────────────────────────────────┘
  │
  ▼  review_passed = True
  │
┌─────────────────────────────────────────────┐
│ MCP Executor                                 │
│                                             │
│ JSON-RPC 2.0 Request:                       │
│ {                                           │
│   "jsonrpc": "2.0",                         │
│   "method": "execute_query",                │
│   "params": {                               │
│     "sql": "UPDATE inventory SET ...",      │
│     "params": [500, "SKU-123", tenant_id]   │
│   },                                        │
│   "id": "550e8400-e29b-..."                 │
│ }                                           │
│                                             │
│ → POST to client's MCP Server endpoint      │
│                                             │
│ Response:                                   │
│ {                                           │
│   "jsonrpc": "2.0",                         │
│   "result": {                               │
│     "rows_affected": 1,                     │
│     "status": "success"                     │
│   },                                        │
│   "id": "550e8400-e29b-..."                 │
│ }                                           │
└─────────────────────────────────────────────┘
  │
  ▼
Response to Client:
{
  "answer": "Inventory updated: SKU-123 now has 500 units.",
  "execution_result": {
    "rows_affected": 1,
    "status": "success"
  },
  "tokens_used": 2100,
  "latency_ms": 1450
}
```

## Write Action — Failure & Self-Healing Trace

```
Coder Node generates:
  "UPDATE inventory SET qty = 500 WHERE sku = 'SKU-123'"
  │
  ▼
Reviewer Node:
  ✗ Column 'qty' does not exist in table 'inventory'
    Available columns: sku, quantity, warehouse_id, last_updated
  │
  ▼  review_passed = False, retry_count = 0
  │
┌─────────────────────────────────────────────┐
│ Self-Healing Node                            │
│                                             │
│ Error context:                              │
│   "Column 'qty' does not exist.             │
│    Available: sku, quantity, warehouse_id"  │
│                                             │
│ LLM generates fix:                          │
│   "Replace 'qty' with 'quantity'."          │
│                                             │
│ Also detects:                               │
│   "SKU-123 should be parameterized,         │
│    not string-interpolated."                │
│                                             │
│ Fixed code:                                 │
│   UPDATE inventory                          │
│   SET quantity = $1                         │
│   WHERE sku = $2;                           │
│                                             │
│ retry_count = 1                             │
└─────────────────────────────────────────────┘
  │
  ▼  Route back to Coder Node
  │
Coder Node: receives fixed code, sets as generated_code
  │
  ▼
Reviewer Node: re-validates → PASS
  │
  ▼
MCP Executor: executes successfully
```

## Webhook → Agent Trace

```
External System (Odoo) fires webhook:
  POST /api/v1/webhooks/org_retail_zone_4/hook_inventory
  {
    "event": "inventory_low",
    "product_sku": "SKU-456",
    "current_stock": 5,
    "reorder_point": 50,
    "warehouse_id": "wh_west"
  }
  │
  ▼
Event Gateway:
  1. Validate X-API-Key → tenant_id resolved
  2. Load behavior rules for tenant
  3. Match rule "low_inventory_restock":
     - Condition: payload.current_stock < payload.reorder_point
     - 5 < 50 → MATCH
  4. Create Event record (status: "queued")
  5. Publish to Redis: tenant:org_retail_zone_4:events
  6. Return 200: {"event_id": "evt_789", "status": "queued"}
  │
  ▼  WebSocket push: {"event_id": "evt_789", "status": "queued"}
  │
  ▼
ARQ Worker picks up event from Redis:
  1. Deserialize event payload
  2. Start LangGraph agent loop
  3. ClassifyIntent → "write" (need to create purchase order)
  4. Coder Node → generates Odoo API call:
     POST /api/purchase_orders
     {
       "product_sku": "SKU-456",
       "quantity": 500,
       "warehouse_id": "wh_west",
       "reason": "auto_restock_low_inventory"
     }
  5. Reviewer Node → validates API payload structure
  6. MCP Executor → sends to Odoo MCP Server
  │
  ▼  WebSocket push throughout:
  │  {"status": "processing", "step": "classifying_intent"}
  │  {"status": "processing", "step": "generating_code"}
  │  {"status": "processing", "step": "reviewing"}
  │  {"status": "processing", "step": "executing"}
  │  {"status": "completed", "result": {...}}
  │
  ▼
Frontend Events Monitor:
  ├── Live event feed shows real-time status
  ├── Click event → expand details + agent trace
  └── Success: green badge, failure: red badge with error
```
