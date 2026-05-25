# Current State

> **Date**: 2026-05-25  
> **Phase**: Stage 1 Complete — Stage 2 Week 5 Active

## Project Status

| Component | Status |
|-----------|--------|
| Project concept & requirements | Done (PDF walkthrough) |
| Serena project config | Done (`.serena/`) |
| Monorepo scaffold | Done (`backend/` + `frontend/` + `docs/`) |
| Docker dev environment | Done (PG16+pgvector, Redis 7, FastAPI) |
| Multi-tenant DB schema | Done (6 tables + Alembic migration 0001) |
| FastAPI core + auth | Done (API keys + OIDC dual auth) |
| Schema reflection engine | Done (asyncpg information_schema → JSON → Redis cache) |
| LLM integration | Done (OpenRouter, schema-grounded queries) |
| RAG models | In progress (Document, Chunk, Citation) |
| RAG ingestion pipeline | In progress (Week 5) |
| Frontend dashboard | Not started (Week 8) |

## Confirmed Decisions

| Decision | Choice |
|----------|--------|
| LLM provider | OpenRouter (model-flexible) |
| Embedding model | OpenRouter / fallback all-MiniLM-L6-v2 |
| Repo structure | Monorepo |
| Auth | OAuth/OIDC from day 1 |
| DB scope | PostgreSQL-only |

## Built Files (Stage 1)

```
backend/
├── src/
│   ├── main.py                          # FastAPI app, security headers, 5 routers
│   ├── core/
│   │   ├── config.py                    # Pydantic Settings
│   │   ├── tenant.py                    # ContextVar tenant isolation
│   │   ├── security.py                  # Fernet encrypt/decrypt
│   │   ├── oidc.py                      # OIDC discovery + JWT
│   │   ├── redis_client.py             # Async Redis singleton
│   │   └── security_middleware.py       # Rate limiting + audit logging
│   ├── db/
│   │   ├── models/__init__.py           # Tenant, User, ApiKey, Connection, SchemaCache, Credential
│   │   ├── session.py                  # AsyncSession factory
│   │   ├── tenant_isolation.py         # ORM WHERE tenant_id injector
│   │   └── migrations/
│   │       ├── env.py                  # Async Alembic runner
│   │       └── versions/0001_initial.py
│   ├── api/
│   │   ├── deps.py                     # Auth + tenant dependencies
│   │   └── v1/
│   │       ├── auth.py                 # OIDC login/callback
│   │       ├── api_keys.py             # API key CRUD
│   │       ├── connections.py          # Connection CRUD (encrypted)
│   │       ├── schema_endpoints.py     # Reflect/cache/get schema
│   │       └── query.py               # Schema-grounded NL query
│   └── services/
│       ├── schema_reflection.py        # asyncpg information_schema → JSON
│       ├── schema_cache.py             # Redis cache (TTL 3600s)
│       └── llm.py                      # OpenRouter client
└── tests/
    └── test_health.py                  # Health check test
```

## Test Status

- `ruff` — All checks passed
- `mypy --ignore-missing-imports` — Clean (27 source files)
- `pytest` — 1 passed (health check)

## Environment

```
Working directory: /home/hairzee/prods/Flux_gateway
OS: Linux
Shell: zsh
Docker: postgres (pgvector), redis
```

## Next Actions (Stage 2 Week 5 — RAG Ingestion)

1. Create Document, Chunk, Citation models
2. Migration 0002 for RAG tables
3. RAG ingestion service (PyMuPDF, semantic chunking, embeddings)
4. RAG API endpoints (upload, list, delete)

## Blockers

- None.
