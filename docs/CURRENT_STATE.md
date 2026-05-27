# Current State

> **Date**: 2026-05-27
> **Phase**: Stage 3 Week 9 Complete — Week 10 Next

## Project Status

| Component | Status |
|-----------|--------|
| Project concept & requirements | Done |
| Monorepo scaffold | Done (`backend/` + `frontend/` + `docs/`) |
| Docker dev environment | Done (PG16+pgvector, Redis 7, FastAPI) |
| Multi-tenant DB schema | Done (6 tables + Alembic migration 0001) |
| FastAPI core + auth | Done (API keys + OIDC dual auth) |
| Schema reflection engine | Done (asyncpg `information_schema` → JSON → Redis) |
| LLM integration | Done (OpenRouter, schema-grounded queries) |
| RAG ingestion pipeline | Done (PyMuPDF, tiktoken chunker, pgvector store) |
| Hybrid search + citations | Done (pgvector + BM25 + RRF fusion) |
| LangGraph agent (7 nodes) | Done (classify → research/code → review → self-heal → exec → format) |
| Frontend dashboard | Done (Next.js 16, 11 pages, dark-first theme) |
| Docker sandbox execution | Done (Docker SDK, ephemeral container, reviewer integration) |

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
├── db/ (models, session, tenant_isolation, migrations)
├── api/ (deps, v1/[auth, api_keys, connections, schema_endpoints, query, rag, agent, sandbox])
├── agents/ (state, graph, 7 nodes)
└── services/ (schema_reflection, schema_cache, llm, rag_ingestion, rag_query, sandbox)

frontend/src/
├── app/
│   ├── globals.css                  # Dark-first CSS vars (shadcn/ui tokens)
│   ├── layout.tsx                    # RootLayout (Geist, ThemeProvider, Toaster)
│   ├── page.tsx                      # Redirect → /dashboard
│   ├── (dashboard)/
│   │   ├── layout.tsx               # DashboardLayout (Sidebar + Header)
│   │   ├── page.tsx                  # Dashboard Home (stats + getting started)
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
│   │   │   ├── page.tsx             # Event feed stub
│   │   │   └── [eventId]/page.tsx
│   │   └── settings/
│   │       ├── page.tsx             # Theme toggle + model selector
│   │       ├── api/page.tsx         # API key management (CRUD)
│   │       └── billing/page.tsx     # Billing stub (post-MVP)
│   └── api/[...path]/route.ts       # BFF proxy → FastAPI backend
├── components/
│   ├── theme-provider.tsx            # Dark-first with system detection
│   ├── sidebar.tsx                   # Collapsible nav (7 items)
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
    ├── api.ts                        # ApiClient (connections, schema, query, rag, keys)
    └── ws.ts                         # WebSocket client (auto-reconnect)

docs/
├── PROJECT_PLAN.md
├── CURRENT_STATE.md
├── architecture/ (system-overview, agent-topology, security-model, data-flow)
├── modules/ (schema-engine, rag-engine, sandbox-execution, event-gateway, sdk)
├── frontend/ (routes, ui-components)
└── roadmap/ (stage-1-core, stage-2-product, stage-3-scale, future-goals)
```

## Test Status

- `ruff` (backend) — All checks passed
- `mypy --ignore-missing-imports` (backend) — Clean (3 pre-existing non-blocking issues)
- `pytest` (backend) — 1 passed (health check)
- `tsc --noEmit` (frontend) — 0 errors
- `eslint` (frontend) — 0 errors, 0 warnings

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
  ← develop (09bdda9)    ← + Stage 2 W7 (LangGraph agent)
```

## Environment

```
Working directory: /home/hairzee/prods/Flux_gateway
OS: Linux · Shell: zsh
Docker: postgres (pgvector), redis
Node: 22.22.0 · npm: 10.9.4
```

## Next Actions (Stage 3 Week 10 — Event Gateway)

1. WebSocket endpoint (`/ws/{tenant_id}`) with FastAPI WebSocket manager
2. Redis Pub/Sub per-tenant channel (`tenant:{id}:events`)
3. ARQ worker pool for async agent dispatch
4. Frontend WebSocket client: real-time event feed, progress bars

## Blockers

- None.
