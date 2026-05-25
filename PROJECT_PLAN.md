# Flux Gateway — Implementation Plan

> **Status**: CONFIRMED — Stage 1 Week 1 active  
> **Last Updated**: 2026-05-25

---

## Requirements Restatement

Build B2B SaaS "Data-to-Agent Gateway" — think Zapier for Agentic Context.

**Core Value Proposition**: Companies paste DB connection string or API URL → platform auto-maps schema, indexes files safely, deploys secure NL agent that reads data + executes validated write-backs. No custom integration code needed.

### Three Core Modules (MVP)
1. **Schema Autodiscovery Engine**: Metadata-only DB reflection → JSON graph. LLM references this graph to prevent hallucinated column names and catastrophic queries.
2. **Isolated Hybrid RAG**: pgvector + BM25 semantic search with hardcoded `tenant_id` filters. Every response includes Citation Tracking Graph (verifiable audit trail).
3. **Action Sandbox**: LangGraph multi-agent circuit (Researcher → Coder → Reviewer → Self-Healing) with ephemeral Docker/WASM execution containers.

### Target Market
- Mid-market businesses running Odoo, HubSpot, SQL databases
- Companies losing thousands of hours to manual menu navigation ("the thousand clicks problem")
- Organizations spending $150K+ sourcing engineers for custom integrations

### UI Requirements
- Next.js 16, Tailwind v4, shadcn/ui, Magic UI, Motion.dev
- Geist font, dark-first design
- Playwright MCP for E2E testing

---

## Implementation Phases

### STAGE 1: CORE INFRASTRUCTURE (Weeks 1–4)

```
Week 1-2: Foundation
├── Project scaffold (monorepo: backend/ + frontend/ + docs/)
├── Docker Compose dev environment (PostgreSQL 16 + pgvector, Redis, FastAPI)
├── Multi-tenant DB schema design & Alembic migrations
├── FastAPI app skeleton with API key auth middleware
└── Tenant isolation layer (ORM event listener for WHERE tenant_id filter)

Week 3-4: Schema Engine MVP
├── Database connection manager (encrypted connection string storage)
├── Schema reflection service (information_schema → JSON metadata graph)
├── Schema cache layer (Redis, per-tenant, with invalidation)
├── Schema Graph API endpoints (CRUD for tenant connections)
└── Integration test: connect to test PG → reflect schema → return graph
```

**Milestone**: Can connect to any PostgreSQL DB, reflect schema safely, cache metadata graph.

**Resources to open now**:
- LangGraph docs: https://langchain-ai.github.io/langgraph/
- FastAPI docs: https://fastapi.tiangolo.com/
- pgvector: https://github.com/pgvector/pgvector
- SQLAlchemy 2.0 async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

---

### STAGE 2: PRODUCTIZATION & VISUAL ENGINE (Weeks 5–8)

```
Week 5-6: RAG Pipeline
├── Document ingestion service (PDF, MD, HTML parsing)
├── Semantic chunking + embedding pipeline
├── pgvector schema extension (tenant-scoped vector tables)
├── BM25 index builder (per-tenant, in-memory or Redis-backed)
├── Hybrid search API (vector + keyword → fused ranking)
├── Citation tracking system (chunk_id → source doc → page mapping)
└── Integration test: upload doc → query → get cited answer

Week 7: Agent Orchestration
├── LangGraph state machine definition (AgentState TypedDict)
├── Intent Classifier node (READ vs WRITE routing)
├── Researcher Node (pgvector context retrieval + LLM answer)
├── Coder Node (schema-grounded SQL/API generation)
├── Reviewer Node (sandboxed code validation)
├── Self-Healing Node (error → fix → retry loop, max 3)
└── Unit tests for each node

Week 8: Frontend Dashboard MVP
├── Next.js 16 project init with shadcn/ui, Tailwind v4, Magic UI, Motion.dev
├── Geist font configuration (Sans + Mono, variable)
├── Dark-first theme setup (CSS variables)
├── Dashboard layout (sidebar nav + main content)
├── Connections page (DB connection management UI)
├── Schema Explorer (tree view of reflected schema graph)
├── Agent Chat interface (NL query input + response display)
├── Token/cost tracking widget
└── Playwright MCP E2E test: connect → explore schema → ask question
```

**Milestone**: Full dashboard where user connects DB, sees schema graph, asks NL questions, gets cited answers.

**Resources to open now**:
- shadcn/ui: https://ui.shadcn.com/
- Magic UI: https://magicui.design/
- Motion.dev: https://motion.dev/
- Next.js 16: https://nextjs.org/docs
- Tailwind v4: https://tailwindcss.com/docs/v4-beta
- Geist font: https://vercel.com/font
- pgvector hybrid search patterns: https://github.com/pgvector/pgvector?tab=readme-ov-file#hybrid-search

---

### STAGE 3: SCALE & INTEGRATIONS (Weeks 9–12)

```
Week 9-10: Execution Sandbox
├── Docker SDK integration (ephemeral container management)
├── Sandbox execution service (code → container → stdout/stderr → destroy)
├── Signed URL generation for output files
├── WASM runtime evaluation (lighter alternative to Docker)
├── LangGraph Reviewer Node ↔ Sandbox integration
├── Self-healing retry loop (error capture → fix generation → re-execute)
└── Integration test: agent generates SQL → sandbox validates → passes → MCP executes

Week 10-11: Event Gateway
├── WebSocket endpoint setup (FastAPI WebSocket routes)
├── Redis Pub/Sub channel per tenant
├── Agentic Behavior Rules Matrix (YAML/JSON per-tenant config)
├── Background worker pool (ARQ or Celery)
├── Webhook ingestion endpoint (HTTP POST → validate → queue → execute)
├── Real-time status streaming to dashboard via WebSocket
└── Event log storage (tenant-isolated)

Week 12: Usage Tracking & Production Hardening
├── Token usage tracking per tenant per model
├── Compute time + storage tracking
├── Usage telemetry dashboard (charts, cost estimation)
├── Billing integration prep (Stripe)
├── Internal admin dashboard
├── Performance + security audit
└── Documentation finalization
```

**Milestone**: End-to-end platform: webhook → agent loop → sandbox execution → live dashboard streaming. Usage tracking per tenant. Billing-ready.

**Resources to open now**:
- Docker SDK Python: https://docker-py.readthedocs.io/
- Redis Pub/Sub: https://redis.io/docs/latest/develop/interact/pubsub/
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- ARQ (async task queue): https://arq-docs.helpmanual.io/
- Stripe SDK: https://stripe.com/docs/api

---

## Dependencies

### Internal (between modules)
```
Schema Engine ──► RAG Engine (schema graph informs RAG retrieval)
Schema Engine ──► Sandbox (Coder Node uses schema graph)
RAG Engine ──► Sandbox (Researcher Node uses RAG)
Sandbox ──► Event Gateway (agent loops triggered by events)
All modules ──► Frontend (dashboard surface for each feature)
```

### External
| Service | Purpose | Stage |
|---------|---------|-------|
| PostgreSQL 16 + pgvector | Primary DB, vector storage | Stage 1 |
| Redis 7 | Cache, Pub/Sub, queues | Stage 1 |
| Docker Engine | Sandbox containers | Stage 2-3 |
| LLM Provider (OpenAI/Anthropic/local) | Agent intelligence | Stage 1 |
| Embedding Model | Vector embeddings | Stage 2 |
| Stripe | Billing | Stage 3 |

### Tool Install Checklist (sequential)
1. **Before Stage 1**: Python 3.12+, Node 22+, Docker, PostgreSQL 16, Redis
2. **Stage 1 start**: `uv` (Python pkg manager), Alembic, LangGraph, FastAPI, SQLAlchemy
3. **Stage 2 start**: pgvector extension, SentenceTransformers, PyMuPDF, Next.js, shadcn/ui
4. **Stage 3 start**: Docker SDK, Playwright, ARQ, Stripe SDK

---

## Risks

### HIGH
| Risk | Mitigation |
|------|------------|
| **Data leakage across tenants** | RLS at DB level + ORM event listener + API middleware. Triple-layer enforcement. Never trust client-side tenant_id. |
| **Malicious code execution in sandbox** | No network access, CPU/memory limits, tmpfs only, 30s timeout, container destroyed after use. WASM for lower-risk tasks. |
| **LLM hallucination on production DB** | Schema Graph grounding (exact column names), Reviewer Node validation, no raw row data in LLM context, read-only metadata reflection. |

### MEDIUM
| Risk | Mitigation |
|------|------------|
| **Schema drift (DB structure changes)** | Cache invalidation hooks, periodic re-reflection, versioned schema snapshots. |
| **pgvector performance at scale** | HNSW indexes, tenant-level partitioning, query result caching. |
| **Docker sandbox cold start latency** | Container pool (pre-warmed), WASM fallback for simple tasks, async execution. |
| **LLM cost unpredictability** | Token tracking dashboard, per-tenant budgets, model tiering (cheap model for classification, expensive for generation). |

### LOW
| Risk | Mitigation |
|------|------------|
| **BM25 index rebuild time** | Incremental updates, background worker, acceptable at MVP scale. |
| **WebSocket connection drops** | Auto-reconnect with exponential backoff, event log replay on reconnect. |

---

## Estimated Complexity

| Module | Complexity | Rationale |
|--------|-----------|-----------|
| Schema Engine | **Medium** | SQL reflection is well-understood; complexity in connection security + caching |
| RAG Engine | **High** | Hybrid search fusion, chunking strategy, citation tracking = many moving parts |
| Agent Sandbox | **High** | LangGraph orchestration + Docker sandbox + self-healing = 3 sub-systems |
| Event Gateway | **Medium** | WebSockets + Redis Pub/Sub is standard; complexity in behavior rules engine |
| Frontend Dashboard | **Medium-High** | Many pages, real-time streaming, dark-first design system |
| Multi-tenant Isolation | **High** | Cross-cutting concern touching every layer; catastrophic if wrong |

**Total**: ~16-20 weeks for full MVP with 1-2 senior engineers.

---

## Project Structure (Planned)

```
Flux_gateway/
├── backend/
│   ├── src/
│   │   ├── api/              # FastAPI routes
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── connections.py
│   │   │   │   ├── schema.py
│   │   │   │   ├── rag.py
│   │   │   │   ├── agent.py
│   │   │   │   ├── events.py
│   │   │   │   └── telemetry.py
│   │   │   └── deps.py       # FastAPI dependencies (tenant_id, auth)
│   │   ├── core/
│   │   │   ├── config.py     # Settings from env
│   │   │   ├── security.py   # Encryption, API keys
│   │   │   └── tenant.py     # Tenant isolation middleware
│   │   ├── db/
│   │   │   ├── session.py    # Async SQLAlchemy session
│   │   │   ├── models/       # SQLAlchemy ORM models
│   │   │   └── migrations/   # Alembic
│   │   ├── services/
│   │   │   ├── schema_reflection.py
│   │   │   ├── rag_ingestion.py
│   │   │   ├── rag_query.py
│   │   │   ├── sandbox.py
│   │   │   └── event_gateway.py
│   │   ├── agents/
│   │   │   ├── graph.py          # LangGraph state machine
│   │   │   ├── nodes/
│   │   │   │   ├── classifier.py
│   │   │   │   ├── researcher.py
│   │   │   │   ├── coder.py
│   │   │   │   ├── reviewer.py
│   │   │   │   └── self_healing.py
│   │   │   └── mcp_client.py
│   │   └── workers/
│   │       ├── tasks.py      # ARQ/Celery tasks
│   │       └── websocket_manager.py
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx      # Dashboard home
│   │   │   ├── connections/
│   │   │   ├── schema/
│   │   │   ├── chat/
│   │   │   ├── docs/
│   │   │   ├── events/
│   │   │   └── settings/
│   │   ├── components/
│   │   │   ├── ui/           # shadcn/ui components
│   │   │   ├── layout/       # Sidebar, header
│   │   │   ├── chat/         # Agent chat interface
│   │   │   ├── schema/       # Schema explorer tree
│   │   │   ├── citations/    # Citation badges
│   │   │   └── telemetry/    # Charts, token tracker
│   │   ├── lib/
│   │   │   ├── api.ts        # Backend API client
│   │   │   └── ws.ts         # WebSocket client
│   │   └── hooks/            # Custom React hooks
│   ├── tests/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── docs/                     # All documentation (see below)
└── scripts/                  # Dev/CI scripts
```

### Documentation Map

```
docs/
├── CURRENT_STATE.md              # What exists now (empty project)
├── modules/
│   ├── schema-engine.md          # DB reflection, graph caching, security
│   ├── rag-engine.md             # Ingestion, hybrid search, citations
│   ├── sandbox-execution.md      # LangGraph agents, Docker/WASM sandbox
│   ├── event-gateway.md          # WebSockets, Pub/Sub, behavior rules
│   └── sdk.md                    # Client JS SDK spec
├── architecture/
│   ├── system-overview.md        # Full system diagram + data flow
│   ├── agent-topology.md         # LangGraph nodes, state, transitions
│   ├── security-model.md         # Tenant isolation, encryption, sandbox
│   └── data-flow.md              # Read vs Write lifecycle traces
├── frontend/
│   ├── ui-components.md          # Component tree + shadcn/ui usage
│   └── routes.md                 # Page routes + data fetching strategy
└── roadmap/
    ├── stage-1-core.md           # Weeks 1-4 detailed tasks
    ├── stage-2-product.md        # Weeks 5-8 detailed tasks
    ├── stage-3-scale.md          # Weeks 9-12 detailed tasks
    └── future-goals.md           # Post-MVP vision
```

---

## Key Design Principles

1. **Tenant Isolation First**: Every query, every vector search, every agent execution gated by hardcoded `tenant_id`. Triple-layer: DB RLS → ORM → API middleware.
2. **Schema Grounding**: LLM never sees raw production data. Only metadata graph + vector chunks with citations.
3. **Sandbox Everything**: All generated code validated in ephemeral container before touching production.
4. **Citation Everything**: Every RAG response traceable to exact source chunk. Kills hallucination dead.
5. **Stateless Agents**: LangGraph state is request-scoped. No cross-request state leakage.
6. **Dark-First Design**: All UI components designed in dark mode. Light mode via CSS variable overrides.

---

## End Goal

A production B2B SaaS platform where:
- Mid-market company signs up → pastes DB string → in 5 minutes has a secure NL agent
- Agent reads their data, answers questions with citations, executes validated write-backs
- Background webhooks trigger autonomous agent workflows
- Platform tracks token/cost usage per tenant for billing

---

## ✅ Confirmed Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | LLM provider | **OpenRouter** — model flexible, pick best fit per task (gpt-4o, claude, etc.) |
| 2 | Embedding model | OpenRouter if available, fallback **local all-MiniLM-L6-v2** for dev/testing |
| 3 | Repo structure | **Monorepo** (`backend/` + `frontend/` + `docs/`) |
| 4 | Auth strategy | **OAuth/OIDC from day 1** — skip API-key-only phase |
| 5 | DB scope | **PostgreSQL-only** for MVP |

> **Status**: CONFIRMED — Stage 1 coding begins.
