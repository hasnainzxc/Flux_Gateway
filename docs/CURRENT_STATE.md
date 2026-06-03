# Current State

> Full reference: **[MASTER_GUIDE.md](MASTER_GUIDE.md)** — architecture, decision rationale, security model, agent topology, dev→prod evolution, API reference
>
> **Date**: 2026-06-03
> **Phase**: Stage 3 Complete (Weeks 9-12) — Production Ready
> **Last Commit**: pending — `feat(event-gateway): WebSocket, webhooks, ARQ workers, usage tracking`

---

## Recap: What was built (3 days)

### Stage 1 — Core Infrastructure (Weeks 1-4)

**Goal**: Connect any PostgreSQL DB → reflect schema → NL query about schema.

| Component | What it does |
|-----------|-------------|
| Monorepo scaffold | `backend/` + `frontend/` + `docs/` + `docker-compose.yml` |
| Multi-tenant DB | 6 tables (`tenants`, `users`, `api_keys`, `connections`, `schema_cache`, `credentials`) + Alembic migrations |
| Tenant isolation | Triple-layer: DB Row-Level Security → ORM listener → FastAPI dependency. Tenant A CANNOT see Tenant B data, ever |
| Auth (dual-mode) | API keys (`sk-` prefix, hashed storage) + OIDC/JWT for web login |
| Schema reflection | `asyncpg` queries `information_schema` (metadata only, no user rows). Builds JSON schema graph with tables/columns/keys/indexes/relationships. Cached in Redis (TTL 1hr) |
| LLM integration | OpenRouter client. Schema-grounded NL queries — asks `gpt-4o-mini` "what tables are in my database?" with system prompt containing only real column names. No hallucinated column names |
| Security | AES-256-GCM credential encryption, rate limiting (100req/60s per tenant), audit logging, security headers |

### Stage 2 — Productization (Weeks 5-8)

**Goal**: Full dashboard. Connect DB → explore schema → upload docs → get cited answers.

| Component | What it does |
|-----------|-------------|
| RAG ingestion | Upload PDF/MD/HTML/TXT → PyMuPDF parsing → tiktoken semantic chunking (1000t chunk, 200t overlap) → OpenAI embeddings (1536d) → pgvector storage. All tenant-scoped |
| Hybrid search | pgvector cosine distance + BM25 lexical (per-tenant in-memory index) → Reciprocal Rank Fusion (k=60, vector weight 0.7, BM25 0.3) — returns top chunks with scores |
| Citations | Inline `[1]` markers in answers → citation panel shows source doc, page, score, excerpt. Color-coded: green ≥0.9, yellow ≥0.7, red <0.7 |
| LangGraph agent | 7-node state machine: ClassifyIntent (gpt-4o-mini) → Researcher (reads) / Coder (writes) → Reviewer (validates) → Self-Heal (retry ≤3) → MCP Executor → FormatResponse. READ path: RAG search → LLM answer with citations. WRITE path: schema-grounded SQL → validation → MCP execution |
| Frontend dashboard | Next.js 16 App Router, Tailwind v4, shadcn/ui + Magic UI + Motion.dev + Geist font. Dark-first theme. 11 pages: Dashboard Home, Connections, Schema Explorer, Agent Chat (with citation badges, token counter, animations), Document Manager (drag-drop upload), Events, Settings (API keys, theme toggle, model selector) |
| WebSocket client | `frontend/src/lib/ws.ts` — auto-reconnect with exponential backoff, per-tenant connection pool |
| BFF proxy | Next.js API route forwards all requests to FastAPI backend with X-API-Key header |

### Stage 3 Week 9 — Docker Sandbox (Today)

**Goal**: Execute code in isolated Docker containers. Validate AI-generated SQL before it touches production databases.

**What the Reviewer + Sandbox does**:

```
Coder generates SQL
    ↓
Reviewer node receives generated_code + schema_graph
    ↓
Sandbox spins up ephemeral Docker container (python:3.12-slim)
    ↓
Container runs validation script with ONLY stdlib (re, json)
    - Checks for dangerous SQL ops (DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE, COPY FROM)
    - Checks for SQL injection patterns (tautologies, comment injection)
    - Checks write queries are parameterized ($1, $2 notation)
    - Checks column names actually exist in schema graph
    - Prints JSON result to stdout: {"passed": true/false, "errors": [...]}
    ↓
If passed → MCP Executor sends to client's actual DB
If failed → Self-Heal node fixes + retries (max 3)
```

**Docker container security**:
- `network_disabled: True` — no network access
- `mem_limit: 256m` — capped memory
- `cpu_quota: 50000` — 0.5 CPU core
- `read_only: True` — no writes to container filesystem
- `tmpfs: /tmp size=64m` — isolated temp space only
- `security_opt: no-new-privileges:true` — can't escalate
- `cap_drop: ALL` — all kernel capabilities removed
- `remove: True` — auto-destroyed after execution
- Timeout: 30 seconds

**Fallback**: If Docker daemon unavailable → runs same validation in-process (no isolation but same checks).

**API endpoint**: `POST /api/v1/sandbox/execute` — execute arbitrary Python or SQL validation in sandbox.

**Files created today**:
- `backend/src/services/sandbox.py` — `DockerSandboxService` class (146 lines)
- `backend/src/api/v1/sandbox.py` — Sandbox API router
- Updated: `backend/src/agents/nodes/reviewer.py` (delegates to sandbox)
- Updated: `backend/src/main.py` (register sandbox router)
- Updated: `backend/src/core/config.py` (sandbox settings)
- Updated: `backend/pyproject.toml` (docker dep, split ml extra)
- Updated: `docker-compose.yml` (mount docker.sock for sandbox)
- Updated: `Dockerfile` (remove uv, use pip directly)
- Updated: `.env.template` (sandbox config vars)
- Updated: `README.md` (quick start commands, API table, status)


### Stage 3 Weeks 10-12 — Event Gateway + Usage Tracking (Today)

**Goal**: Real-time event system, webhook ingestion, async worker pool, usage tracking for billing.

**What was built**:

| Component | What it does |
|-----------|-------------|
| WebSocket manager | Per-tenant connection pool, broadcast, dead connection cleanup, API key auth, ping/pong heartbeat |
| Redis Pub/Sub | Per-tenant channels (`tenant:{id}:events`), async publish/subscribe, event bus for worker dispatch |
| ARQ worker pool | Async job processing: load event → run LangGraph agent → update status → WS push → track usage. Max 10 concurrent, 3 retries, 300s timeout |
| Webhook ingestion | `POST /webhooks/ingest/{hook_id}` — HMAC SHA256 signature validation → match behavior rules → create EventLog → publish Redis → return immediately |
| Behavior rules engine | YAML-style rules per tenant. Operators: eq, ne, gt, lt, contains, in, starts_with. Nested JSON path resolution. Priority-sorted matching |
| Event log | Full audit trail: `event_log` table with status (queued/processing/completed/failed), matched rules, agent run ID, result JSONB, timestamps |
| Usage tracking | Monthly upsert per tenant: tokens_in, tokens_out, agent_runs, ws_events, storage_bytes. Summary + history APIs |
| Frontend events page | Real-time WebSocket feed, status filters, live updates, priority badges, error display |
| Webhook config UI | Create webhooks with secret display, copy URL, toggle active, delete |
| Usage dashboard | 7 stat cards, bar chart history, behavior rules CRUD with dialog |
| Live dashboard | Real-time stats: usage summary + connection/doc counts, 7 metric cards |

**DB migration 0003** (4 new tables):
- `webhook_configs` — tenant-scoped webhook endpoints with HMAC secrets
- `behavior_rules` — trigger conditions + agent actions, priority-sorted
- `event_log` — full event audit trail with status tracking
- `usage_records` — monthly usage aggregation for billing

**Files created**:
- Backend: 10 new files (models, services, workers, API routers)
- Frontend: 4 new pages (events, webhooks, billing/usage, dashboard stats)
- Updated: `main.py`, `graph.py`, `api.ts`, `ws.ts`, `sidebar.tsx`, `dialog.tsx`

| Component | Status |
|-----------|--------|
| Project concept & requirements | Done |
| Monorepo scaffold | Done (`backend/` + `frontend/` + `docs/`) |
| Docker dev environment | Done (PG16+pgvector, Redis 7, FastAPI) |
| Multi-tenant DB schema | Done (10 tables + 3 Alembic migrations) |
| FastAPI core + auth | Done (API keys + OIDC dual auth) |
| Schema reflection engine | Done (asyncpg `information_schema` → JSON → Redis) |
| LLM integration | Done (OpenRouter, schema-grounded queries) |
| RAG ingestion pipeline | Done (PyMuPDF, tiktoken chunker, pgvector store) |
| Hybrid search + citations | Done (pgvector + BM25 + RRF fusion) |
| LangGraph agent (7 nodes) | Done (classify → research/code → review → self-heal → exec → format) |
| Frontend dashboard | Done (Next.js 16, 15 pages, dark-first theme) |
| Docker sandbox execution | Done (Docker SDK, ephemeral container, reviewer integration) |
| Event Gateway (WS + Redis) | Done (WebSocket manager, Pub/Sub, heartbeat) |
| Webhooks + behavior rules | Done (HMAC validation, rule matching, async dispatch) |
| ARQ worker pool | Done (event processing, agent execution, usage tracking) |
| Usage tracking + billing prep | Done (monthly aggregation, summary/history APIs) |

## Confirmed Decisions

| Decision | Choice |
|----------|--------|
| LLM provider | OpenRouter (model-flexible) |
| Embedding model | OpenRouter / fallback all-MiniLM-L6-v2 |
| Repo structure | Monorepo |
| Auth | OAuth/OIDC from day 1 |
| DB scope | PostgreSQL-only |

## Built Files

```
backend/src/
├── main.py
├── core/ (config, tenant, security, oidc, redis_client, security_middleware)
├── db/ (models, session, tenant_isolation, migrations/[0001_initial, 0002_rag, 0003_event_gateway])
├── api/ (deps, v1/[auth, api_keys, connections, schema_endpoints, query, rag, agent, sandbox, events, webhooks, behavior_rules, ws, usage])
├── agents/ (state, graph, 7 nodes)
├── services/ (schema_reflection, schema_cache, llm, rag_ingestion, rag_query, sandbox, websocket_manager, event_bus, behavior_rules, webhook_service, usage_tracker)
└── workers/ (tasks.py — ARQ WorkerSettings, process_event, run_agent_task)

frontend/src/
├── app/
│   ├── globals.css                  # Dark-first CSS vars (shadcn/ui tokens)
│   ├── layout.tsx                    # RootLayout (Geist, ThemeProvider, Toaster)
│   ├── page.tsx                      # Redirect → /dashboard
│   ├── dashboard/
│   │   ├── layout.tsx               # DashboardLayout (Sidebar + Header)
│   │   ├── page.tsx                  # Dashboard Home (live stats, 7 metric cards)
│   │   ├── connections/
│   │   │   ├── page.tsx             # Connection list + add dialog
│   │   │   └── [id]/page.tsx        # Schema explorer per connection
│   │   ├── schema/page.tsx          # Global schema view
│   │   ├── chat/
│   │   │   ├── page.tsx             # Agent Chat (messages + citations + animations)
│   │   │   └── [conversationId]/page.tsx
│   │   ├── docs/
│   │   │   ├── page.tsx             # Document list + drag-drop upload
│   │   │   └── [docId]/page.tsx
│   │   ├── events/
│   │   │   ├── page.tsx             # Real-time event feed (WS, filters, live updates)
│   │   │   ├── [eventId]/page.tsx
│   │   │   └── webhooks/page.tsx    # Webhook config (create, secret, toggle, delete)
│   │   └── settings/
│   │       ├── page.tsx             # Theme toggle + model selector
│   │       ├── api/page.tsx         # API key management (CRUD)
│   │       └── billing/page.tsx     # Usage dashboard (stats, chart, behavior rules CRUD)
│   └── api/[...path]/route.ts       # BFF proxy → FastAPI backend
├── components/
│   ├── theme-provider.tsx            # Dark-first with system detection
│   ├── sidebar.tsx                   # Collapsible nav (8 items incl. Webhooks)
│   ├── header.tsx                    # Theme toggle + notifications
│   └── ui/                           # shadcn/ui primitives
│       ├── button.tsx
│       ├── card.tsx
│       ├── input.tsx
│       ├── badge.tsx
│       ├── dialog.tsx
│       └── skeleton.tsx
└── lib/
    ├── utils.ts                      # cn() helper
    ├── api.ts                        # ApiClient (connections, schema, query, rag, keys, events, webhooks, rules, usage)
    └── ws.ts                         # WebSocket client (auto-reconnect, tenant-scoped)

docs/
├── PROJECT_PLAN.md
├── CURRENT_STATE.md
├── architecture/ (system-overview, agent-topology, security-model, data-flow)
├── modules/ (schema-engine, rag-engine, sandbox-execution, event-gateway, sdk)
├── frontend/ (routes, ui-components)
└── roadmap/ (stage-1-core, stage-2-product, stage-3-scale, future-goals)
```

## Test Status

- `ruff check src/` (backend) — All checks passed
- `uvicorn` startup — Clean, no import errors, Redis connects
- `next build` (frontend) — All 17 routes compile successfully
- `eslint src/` (frontend) — 0 errors, 0 warnings
- DB migrations — All 3 applied (0001_initial, 0002_rag, 0003_event_gateway)

## Dependencies

```
frontend/package.json:
  next 16.2.6, react 19.2.4, react-dom 19.2.4
  react-hook-form, zod, @hookform/resolvers
  motion (Framer Motion), sonner
  lucide-react, react-dropzone
  class-variance-authority, clsx, tailwind-merge
  tailwindcss 4, @tailwindcss/postcss
```

## Git Branches

```
main (1ad61e9)           ← Stage 1 + Stage 2 W5-6
  ← develop (pending)    ← + Stage 2 W7-8 + Stage 3 W9-12 (Event Gateway + Usage)
```

## Environment

```
Working directory: /home/hairzee/prods/Flux_gateway
OS: Linux · Shell: zsh
Docker: postgres (pgvector), redis
Node: 22.22.0 · npm: 10.9.4
```

## Next Actions (Post-Stage 3)

1. Security audit — penetration testing, dependency scan, secrets check
2. Stripe integration — wire usage records to Stripe billing API
3. Admin dashboard — tenant management, system health monitoring
4. Documentation — API docs (OpenAPI/Swagger), user guides, deployment guide
5. Production deployment — Docker Compose prod, CI/CD pipeline, monitoring

## Blockers

- None. Stage 3 complete.
