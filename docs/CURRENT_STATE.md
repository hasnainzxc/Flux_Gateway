# Current State

> **Date**: 2026-05-25
> **Phase**: Stage 2 Week 7 Complete — Stage 2 Week 8 Next

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
| Frontend dashboard | Not started (Week 8) |

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
├── main.py                          # FastAPI app, 6 routers
├── core/
│   ├── config.py                    # Pydantic Settings
│   ├── tenant.py                    # ContextVar tenant isolation
│   ├── security.py                  # Fernet encrypt/decrypt
│   ├── oidc.py                      # OIDC discovery + JWT
│   ├── redis_client.py              # Async Redis singleton
│   └── security_middleware.py       # Rate limiting + audit logging
├── db/
│   ├── models/
│   │   ├── __init__.py              # Tenant, User, ApiKey, Connection, SchemaCache, Credential
│   │   ├── document.py             # Document, Document→Chunks cascade
│   │   ├── chunk.py                # Chunk, pgvector Vector(1536)
│   │   └── citation.py             # Citation, FK→Chunk
│   ├── session.py                   # AsyncSession factory
│   ├── tenant_isolation.py          # ORM WHERE tenant_id injector
│   └── migrations/
│       ├── versions/0001_initial.py
│       └── versions/0002_rag.py
├── api/
│   ├── deps.py                      # Auth + tenant dependencies
│   └── v1/
│       ├── auth.py                  # OIDC login/callback
│       ├── api_keys.py              # API key CRUD
│       ├── connections.py           # Connection CRUD (encrypted)
│       ├── schema_endpoints.py      # Reflect/cache/get schema
│       ├── query.py                 # Schema-grounded NL query
│       ├── rag.py                   # RAG upload/search/ask/citations
│       └── agent.py                 # Agent query (LangGraph invocation)
├── agents/
│   ├── state.py                     # AgentState TypedDict
│   ├── graph.py                     # build_agent_graph() factory
│   └── nodes/
│       ├── classify_intent.py       # gpt-4o-mini read/write classifier
│       ├── researcher.py            # Hybrid RAG → LLM answer with citations
│       ├── coder.py                 # Schema-grounded SQL generation
│       ├── reviewer.py              # Rule-based validation (dangerous ops, params, columns)
│       ├── self_heal.py             # LLM fix with max 3 retries
│       ├── mcp_executor.py          # Placeholder (Stage 3 Week 11)
│       └── format_response.py       # Enrich response with citations/execution
└── services/
    ├── schema_reflection.py         # asyncpg information_schema → JSON
    ├── schema_cache.py              # Redis cache (TTL 3600s)
    ├── llm.py                       # OpenRouter client (real token tracking)
    ├── rag_ingestion.py             # PyMuPDF + tiktoken + pgvector pipeline
    └── rag_query.py                 # BM25 + vector + RRF hybrid search
```

## Test Status

- `ruff` — All checks passed
- `mypy --ignore-missing-imports` — Clean (3 pre-existing non-blocking issues)
- `pytest` — 1 passed (health check)

## Git Branches

```
main (1ad61e9)           ← Stage 1 + Stage 2 W5-6
  ← develop (09bdda9)    ← + Stage 2 W7 (LangGraph agent)
      ← feature/langgraph-agent (merged)
```

## Environment

```
Working directory: /home/hairzee/prods/Flux_gateway
OS: Linux · Shell: zsh
Docker: postgres (pgvector), redis
```

## Next Actions (Stage 2 Week 8 — Frontend Dashboard MVP)

1. Next.js 16 app with dark-first theme (Tailwind v4, shadcn/ui, Magic UI, Motion.dev, Geist)
2. Dashboard layout (sidebar + header + main)
3. Connections page (card grid, add dialog, test connection, schema explorer tree)
4. Agent Chat (message list, input, citation badges, citation panel, token counter)
5. Documents page (upload zone, grid, preview)
6. Settings page (API key management, general settings)
7. Playwright E2E tests

## Blockers

- None.
