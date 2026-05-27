# Flux Gateway

> Data-to-Agent Gateway — B2B SaaS. Zapier for Agentic Context.

Companies paste a DB connection string or API URL → platform auto-maps schema, indexes documents, deploys a secure NL agent that reads data and executes validated write-backs. No custom integration code needed.

---

## Architecture

```
Client Infra (DBs, Docs, Apps)
        │
        ▼
┌─────────────────────────────────────────────┐
│              Flux Gateway Platform           │
│                                              │
│  FastAPI Gateway (Auth, Rate Limit, Tenancy) │
│  ┌──────────┐ ┌──────┐ ┌──────────────────┐ │
│  │ Schema   │ │ RAG  │ │ Agent Sandbox    │ │
│  │ Engine   │ │Engine│ │ (LangGraph 7-node)│ │
│  └──────────┘ └──────┘ └──────────────────┘ │
│  ┌──────────────────────────────────────────┐│
│  │        Event Gateway (WebSockets)        ││
│  └──────────────────────────────────────────┘│
│                                              │
│  PostgreSQL 16 + pgvector   │   Redis 7      │
│  (Tenant Data, Vectors,     │   (Cache,      │
│   Event Log, Credentials)   │    Pub/Sub)    │
└─────────────────────────────────────────────┘
        │
        ▼
Next.js 16 Dashboard (shadcn/ui, Magic UI, Motion.dev, Geist)
```

## LangGraph Agent Topology

```
__start__ → classify_intent (gpt-4o-mini)
  ├─ intent=read  → researcher_node (hybrid RAG + LLM) → format_response → __end__
  └─ intent=write → coder_node (schema-grounded SQL)
                     → reviewer_node (rule-based validation)
                       ├─ pass → mcp_exec_node (JSON-RPC 2.0) → format_response → __end__
                       └─ fail → self_heal_node (LLM fix, max 3 retries)
                                   ├─ retry → coder_node
                                   └─ exhausted → format_response (error) → __end__
```

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, Alembic |
| AI/ML | OpenRouter (GPT-4o / GPT-4o-mini), SentenceTransformers |
| Orchestration | LangGraph (7-node state machine) |
| Database | PostgreSQL 16 + pgvector (pgvector) |
| Cache/PubSub | Redis 7 (token bucket rate limiter, schema cache, BM25 index) |
| Search | pgvector cosine + BM25 lexical + Reciprocal Rank Fusion |
| Auth | Dual-mode: API keys (hashed, `sk-` prefix) + OIDC/JWT |
| Frontend | Next.js 16, Tailwind v4, shadcn/ui, Magic UI, Motion.dev, Geist font |
| Testing | pytest-asyncio, Playwright MCP (E2E) |
| Infra | Docker Compose (PG, Redis, FastAPI) |

## Security

- **Tenant isolation**: Triple-layer — DB Row-Level Security → ORM listener → FastAPI dependency
- **Credentials**: AES-256-GCM encryption at rest (Fernet)
- **Sandbox**: Docker ephemeral containers (no network, tmpfs, 30s timeout, `no-new-privileges`)
- **Rate limiting**: Redis token bucket (100 req/60s per tenant)
- **Audit**: Every action logged with tenant_id, IP, user-agent

## Project Structure

```
.
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── src/
│       ├── main.py                  # FastAPI app entry
│       ├── core/                    # config, security, tenant, oidc, middleware
│       ├── db/                      # models, session, migrations, tenant isolation
│       ├── api/v1/                  # auth, api_keys, connections, schema, query, rag, agent
│       ├── agents/                  # state, graph, nodes (classify, research, code, review, etc.)
│       └── services/               # schema_reflection, schema_cache, llm, rag_ingestion, rag_query
├── docs/
│   ├── architecture/               # system-overview, agent-topology, security-model, data-flow
│   ├── modules/                    # schema-engine, rag-engine, sandbox-execution, event-gateway, sdk
│   ├── frontend/                   # routes, ui-components
│   └── roadmap/                    # stage-1-core, stage-2-product, stage-3-scale, future-goals
└── frontend/                       # (Week 8 — Next.js 16 dashboard)
```

## Getting Started

### Prerequisites
- Python 3.12+, Node 22+, Docker (Docker Compose v2+)

### Quick Start (Backend)

```bash
# Clone & enter
cd Flux_gateway

# Copy env template
cp .env.template .env

# Start PostgreSQL 16 + pgvector + Redis
docker compose up -d postgres redis

# Wait for health checks
docker compose ps

# Install Python deps
cd backend
pip install -e ".[dev]"

# Run DB migrations
alembic upgrade head

# Start FastAPI server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Running Everything with Docker

```bash
# Start all services (PG, Redis, FastAPI)
docker compose up -d

# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Frontend (Stage 2 Week 8)

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

### Commands Quick Reference

```bash
# Backend lint & typecheck
cd backend
ruff check src/           # Lint
mypy --ignore-missing-imports src/   # Type check
pytest                    # Run tests
alembic upgrade head      # Apply migrations
alembic revision --autogenerate -m "desc"  # Create migration

# Frontend lint & typecheck
cd frontend
npx eslint src/
npx tsc --noEmit
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/auth/login` | OIDC login |
| `GET` | `/api/v1/auth/callback` | OIDC callback |
| `POST` | `/api/v1/api-keys` | Create API key |
| `GET` | `/api/v1/api-keys` | List API keys |
| `POST` | `/api/v1/connections` | Create DB connection |
| `GET` | `/api/v1/connections` | List connections |
| `POST` | `/api/v1/schema/{connection_id}/reflect` | Reflect schema |
| `GET` | `/api/v1/schema/{connection_id}` | Get cached schema |
| `POST` | `/api/v1/query` | Schema-grounded NL query |
| `POST` | `/api/v1/rag/documents` | Upload document |
| `GET` | `/api/v1/rag/documents` | List documents |
| `POST` | `/api/v1/rag/search` | Hybrid search |
| `POST` | `/api/v1/rag/ask` | RAG + LLM answer with citations |
| `POST` | `/api/v1/agent/query` | LangGraph agent query (full pipeline) |
| `POST` | `/api/v1/sandbox/execute` | Execute code in Docker sandbox |

## Status

| Stage | Week | Status |
|-------|------|--------|
| Stage 1: Core | W1-4 | Complete |
| Stage 2: Product | W5-6 | Complete (RAG + Hybrid Search) |
| Stage 2: Product | W7 | Complete (LangGraph Agent) |
| Stage 2: Product | W8 | Complete (Frontend Dashboard) |
| Stage 3: Scale | W9 | Complete (Docker Sandbox) |
| Stage 3: Scale | W10-12 | Pending |

## License

Proprietary. All rights reserved.
