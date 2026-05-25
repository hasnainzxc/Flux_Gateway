# System Architecture Overview

> Full system diagram and data flow across all layers.

## High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLIENT INFRASTRUCTURE                               │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │ Production DB │  │ Internal Docs│  │ Business App │                      │
│  │ (PG/MySQL)   │  │ (S3/Folders) │  │ (Odoo/HubSpot)│                     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                      │
│         │                 │                  │                               │
│         │    MCP Server   │   File Upload    │   Webhooks                    │
│         │    (read-only   │                  │                               │
│         │     metadata)   │                  │                               │
└─────────┼─────────────────┼──────────────────┼──────────────────────────────┘
          │                 │                  │
          ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FLUX GATEWAY PLATFORM                                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      FASTAPI API GATEWAY                             │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │    │
│  │  │ Auth MW  │ │Tenant MW│ │Rate Limit│ │ CORS     │ │ Logging  │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     CORE SERVICES                                    │    │
│  │                                                                      │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │    │
│  │  │ Schema Engine   │  │ RAG Engine      │  │ Agent Sandbox   │       │    │
│  │  │                 │  │                 │  │                 │       │    │
│  │  │ - DB Reflection │  │ - Ingestion     │  │ - LangGraph     │       │    │
│  │  │ - JSON Graph    │  │ - Hybrid Search │  │ - Docker/WASM   │       │    │
│  │  │ - Cache (Redis) │  │ - Citations     │  │ - MCP Client    │       │    │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │    │
│  │                                                                      │    │
│  │  ┌─────────────────────────────────────────────────────────────┐     │    │
│  │  │                    EVENT GATEWAY                             │     │    │
│  │  │  - Webhook ingestion    - WebSocket manager                  │     │    │
│  │  │  - Behavior rules       - Async worker pool                  │     │    │
│  │  │  - Redis Pub/Sub        - Live status streaming              │     │    │
│  │  └─────────────────────────────────────────────────────────────┘     │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        DATA LAYER                                     │   │
│  │                                                                       │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │   │
│  │  │ PostgreSQL 16   │  │ Redis 7         │  │ Docker Engine   │       │   │
│  │  │ + pgvector      │  │                 │  │                 │       │   │
│  │  │                 │  │ - Schema Cache  │  │ - Sandbox       │       │   │
│  │  │ - Tenant Data   │  │ - Pub/Sub       │  │   Containers    │       │   │
│  │  │ - Vector Store  │  │ - Rate Limiting │  │ - Ephemeral     │       │   │
│  │  │ - Event Log     │  │ - Worker Queue  │  │   (tmpfs only)  │       │   │
│  │  │ - Credential    │  │                 │  │                 │       │   │
│  │  │   Store (enc)   │  │                 │  │                 │       │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTPS + WebSocket
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND DASHBOARD (Next.js 16)                       │
│                                                                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │
│  │Dashboard  │ │Connections│ │Schema     │ │Agent Chat │ │Events     │    │
│  │Home       │ │Manager    │ │Explorer   │ │Interface  │ │Monitor    │    │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘    │
│                                                                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │
│  │Document   │ │Usage/     │ │Settings   │ │Live Logs  │ │Agent      │    │
│  │Manager    │ │Billing    │ │           │ │(WS Stream)│ │Run History│    │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘    │
│                                                                              │
│  Design: Next.js 16 + Tailwind v4 + shadcn/ui + Magic UI + Motion.dev        │
│  Font: Geist (Sans + Mono) | Dark-first CSS variables                        │
│  Testing: Playwright MCP                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Read Query (Detailed)

```
1. User types "Show me all orders from last month over $1000" in Agent Chat
                                    │
2. Frontend SDK captures: prompt + session metadata (user_role, org_id)
                                    │
3. POST /api/v1/agent/query → FastAPI Gateway
   ├── Auth middleware: validate API key → resolve tenant_id
   ├── Tenant middleware: inject tenant_id into request scope
   └── Route handler: create AgentState with tenant_id + schema_graph
                                    │
4. LangGraph State Machine:
   ├── ClassifyIntent Node: LLM → "read"
   ├── Researcher Node:
   │   ├── pgvector hybrid search (WHERE tenant_id = X)
   │   ├── Top-10 chunks retrieved with scores
   │   ├── Context assembled with [1], [2] citation markers
   │   └── LLM generates answer from context
   └── Response Builder: answer + citation metadata
                                    │
5. Response returned to frontend:
   {
     "answer": "Last month there were 342 orders over $1000... [1][2]",
     "citations": [
       {"id": "chunk:abc", "doc": "sales_report_q1.pdf", "page": 5, "score": 0.92},
       {"id": "chunk:def", "doc": "order_policy.md", "page": 2, "score": 0.87}
     ],
     "tokens_used": 1450,
     "latency_ms": 820
   }
                                    │
6. Frontend renders:
   ├── Answer text with clickable citation badges
   ├── Citation side panel showing source chunks
   └── Token counter updated in header
```

## Data Flow: Write Action (Detailed)

```
1. User types "Update inventory for product SKU-123 to 500 units"
                                    │
2. Same auth flow as READ
                                    │
3. LangGraph State Machine:
   ├── ClassifyIntent Node: LLM → "write"
   ├── Coder Node:
   │   ├── Schema graph injected into prompt
   │   └── LLM generates: UPDATE inventory SET quantity = 500 WHERE sku = 'SKU-123'
   ├── Reviewer Node:
   │   ├── Ephemeral Docker container created (no network, tmpfs, 256MB)
   │   ├── Dry-run: parse SQL → validate syntax → check table/column exist in schema
   │   └── PASS: review_passed = True
   ├── MCP Executor:
   │   ├── Build JSON-RPC: {"method": "execute_query", "params": {"sql": "...", "params": {...}}}
   │   ├── POST to client's MCP Server endpoint
   │   └── Result: {"rows_affected": 1, "status": "success"}
   └── Response Builder: execution result
                                    │
4. If Reviewer FAILS:
   ├── Self-Healing Node:
   │   ├── Error: "column 'qty' does not exist" (LLM hallucinated)
   │   ├── LLM: "Fix: use 'quantity' instead of 'qty'"
   │   └── Route back to Coder Node (retry_count++)
   ├── Coder regenerates with fix
   ├── Reviewer re-validates → PASS
   └── MCP Executes
                                    │
5. Response to frontend + WebSocket status updates throughout
```

## Webhook → Agent Flow (Detailed)

```
1. Odoo fires webhook: POST /api/v1/webhooks/org_123/hook_456
   Payload: {"event": "inventory_low", "product": "SKU-123", "current": 10, "threshold": 50}
                                    │
2. Event Gateway:
   ├── Validate API Key (from X-API-Key header)
   ├── Load behavior rules for tenant org_123, hook hook_456
   ├── Match: rule "low_inventory_restock" → conditions met
   └── Publish to Redis: tenant:org_123:events
                                    │
3. ARQ Worker picks up event:
   ├── Subscribe: tenant:org_123:events
   ├── Deserialize event payload
   └── Start LangGraph agent loop with event context
                                    │
4. Agent executes (WRITE path, same as above):
   ├── Coder: "Generate purchase order for SKU-123 to restock to 500 units"
   ├── Reviewer validates
   └── MCP executes against Odoo API
                                    │
5. Throughout process, WebSocket pushes status:
   ├── {"event_id": "evt_789", "status": "processing", "step": "classifying_intent"}
   ├── {"event_id": "evt_789", "status": "processing", "step": "generating_code"}
   ├── {"event_id": "evt_789", "status": "processing", "step": "reviewing"}
   ├── {"event_id": "evt_789", "status": "processing", "step": "executing"}
   └── {"event_id": "evt_789", "status": "completed", "result": {...}}
                                    │
6. Frontend Events Monitor shows:
   ├── Live event feed with status badges
   ├── Expandable event details
   └── Success/failure metrics
```

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Monorepo (backend + frontend) | Single repo for MVP, easier CI, shared types possible |
| PostgreSQL + pgvector (single DB) | One DB to manage, pgvector is mature, avoids extra service |
| LangGraph over custom state machine | Battle-tested, visualization, checkpointing, MCP ecosystem |
| Docker sandbox (not WASM for MVP) | More mature, easier debugging, WASM can be added later |
| ARQ over Celery | Lighter, async-native, Redis-only (no extra broker) |
| Server Components first (Next.js) | Better perf, less JS shipped, good for dashboard |
| API key auth (not OAuth for MVP) | Simple, sufficient for B2B SaaS MVP |
| Geist font | Native Next.js/Vercel integration, great legibility |
