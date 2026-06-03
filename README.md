<div align="center">

# Flux Gateway

### Data-to-Agent Gateway for B2B SaaS

**Paste a DB connection string. Get a secure AI agent that reads, writes, and automates your data.**

[Quick Start](#quick-start) · [Architecture](#architecture) · [API Reference](#api-reference) · [Documentation](#documentation)

---

![Status](https://img.shields.io/badge/status-Stage%203%20Complete-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![Next.js](https://img.shields.io/badge/next.js-16.2.6-black)
![PostgreSQL](https://img.shields.io/badge/postgres-16+pgvector-blue)
![Redis](https://img.shields.io/badge/redis-7-red)
![License](https://img.shields.io/badge/license-Proprietary-gray)

</div>

---

## What is Flux Gateway?

Flux Gateway turns any PostgreSQL database into an AI-powered automation platform in minutes — not months.

**Connect** → paste a connection string, platform auto-maps your schema  
**Query** → ask questions in natural language, get answers with SQL citations  
**Automate** → webhooks trigger autonomous agent workflows via behavior rules  
**Monitor** → real-time WebSocket event feed with full audit trail  

No custom integration code. No ETL pipelines. No vendor lock-in.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Systems                          │
│         Odoo · HubSpot · Stripe · Custom Webhooks               │
└───────────────────────────────┬─────────────────────────────────┘
                                │ Webhooks (HMAC-SHA256)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Flux Gateway Platform                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              FastAPI Gateway (Port 8000)                   │   │
│  │  Auth MW · Rate Limit · Tenant Isolation · Audit Log      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────┐  ┌──────────┐  ┌────────────┐  ┌────────────┐  │
│  │   Schema   │  │   RAG    │  │   Agent    │  │   Event    │  │
│  │   Engine   │  │  Engine  │  │  Sandbox   │  │  Gateway   │  │
│  │            │  │          │  │            │  │            │  │
│  │ Reflection │  │ Ingest   │  │ LangGraph  │  │ WebSockets │  │
│  │ Cache      │  │ Hybrid   │  │ 7-Node     │  │ Webhooks   │  │
│  │ Graph      │  │ Search   │  │ Pipeline   │  │ ARQ Workers│  │
│  └────────────┘  └──────────┘  └────────────┘  └────────────┘  │
│                                                                  │
│  ┌─────────────────────────┐    ┌────────────────────────────┐  │
│  │  PostgreSQL 16 + pgvector│    │         Redis 7            │  │
│  │                          │    │                            │  │
│  │  10 Tables · 3 Migrations│    │  Schema Cache (1hr TTL)    │  │
│  │  Tenant Isolation (RLS)  │    │  Pub/Sub (per-tenant)      │  │
│  │  Encrypted Credentials   │    │  Rate Limit (100/60s)      │  │
│  │  Vector Embeddings       │    │  ARQ Job Queue             │  │
│  └─────────────────────────┘    └────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Docker Sandbox Engine                         │   │
│  │  Ephemeral containers · No network · tmpfs · 30s timeout  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Next.js 16 Dashboard (Port 3000)               │
│                                                                  │
│  Dashboard · Connections · Schema · Chat · Documents · Events    │
│  Webhooks · Settings · Usage/Billing                             │
│                                                                  │
│  Tailwind v4 · shadcn/ui (29 components) · Motion · React Query │
└─────────────────────────────────────────────────────────────────┘
```

---

## LangGraph Agent Pipeline

```
__start__
    │
    ▼
classify_intent ──── GPT-4o-mini classifies: read / write / unknown
    │
    ├── intent=read ──→ researcher_node ──→ format_response ──→ __end__
    │                     │
    │                     ├── Hybrid search (pgvector cosine + BM25 + RRF)
    │                     ├── Schema-grounded context injection
    │                     └── Citation tracking
    │
    ├── intent=write ─→ coder_node ──→ reviewer_node
    │                     │                │
    │                     │                ├── pass ──→ mcp_exec_node ──→ format_response
    │                     │                │
    │                     │                └── fail ──→ self_heal_node (max 3 retries)
    │                     │                              │
    │                     │                              └── retry ──→ coder_node
    │                     │
    │                     └── Docker sandbox validation
    │                         (no network, tmpfs, 30s timeout)
    │
    └── intent=unknown ──→ format_response ──→ __end__
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy async, Alembic |
| **AI/ML** | OpenRouter (GPT-4o / GPT-4o-mini), SentenceTransformers (fallback) |
| **Orchestration** | LangGraph (7-node state machine with self-healing) |
| **Database** | PostgreSQL 16 + pgvector (cosine similarity search) |
| **Cache/Queue** | Redis 7 (schema cache, pub/sub, rate limiting, ARQ job queue) |
| **Workers** | ARQ (async Redis queue, 10 concurrent jobs, 3 retries) |
| **Search** | pgvector cosine + BM25 lexical + Reciprocal Rank Fusion |
| **Auth** | Dual-mode: API keys (SHA-256 hashed) + OIDC/JWT |
| **Frontend** | Next.js 16, React 19, Tailwind v4, shadcn/ui, Motion, React Query |
| **Sandbox** | Docker ephemeral containers (no network, tmpfs, 256MB, 30s) |
| **Infra** | Docker Compose (PG, Redis, FastAPI, ARQ workers) |

---

## Security Model

| Layer | Mechanism |
|-------|-----------|
| **Tenant Isolation** | Triple-layer: DB Row-Level Security → SQLAlchemy ORM listener → FastAPI dependency injection |
| **Credentials** | Fernet symmetric encryption (AES-128-CBC) at rest |
| **Sandbox** | Docker containers: no network access, tmpfs-only filesystem, 30s timeout, `no-new-privileges` |
| **Rate Limiting** | Redis token bucket: 100 requests/60s per tenant |
| **API Keys** | SHA-256 hashed, `sk-` prefix, expiry enforcement |
| **Webhooks** | HMAC-SHA256 signature verification |
| **Audit** | Every action logged with tenant_id, IP, user-agent, timestamp |

---

## Quick Start

### Prerequisites

```bash
Python 3.12+      # python --version
Node.js 22+       # node --version
Docker v24+       # docker --version (with Compose v2)
```

### 1. Clone and Configure

```bash
git clone <repo-url> && cd Flux_gateway
cp .env.template .env
```

Edit `.env`:

```bash
# Required
DATABASE_URL=postgresql+asyncpg://flux:flux_dev@localhost:5432/flux_gateway
REDIS_URL=redis://:flux_redis_dev@localhost:6379/0
OPENROUTER_API_KEY=sk-or-v1-...
SECRET_KEY=changeme-in-production
ENVIRONMENT=development

# Optional (OIDC auth)
OIDC_ISSUER=https://accounts.google.com
OIDC_CLIENT_ID=...
OIDC_CLIENT_SECRET=...

# Optional (Stripe billing)
STRIPE_SECRET_KEY=sk_test_...
```

### 2. Start Everything with Docker

```bash
# Full stack: PostgreSQL + Redis + Backend (containerized)
docker compose up -d

# Or just infrastructure for local dev:
docker compose up -d postgres redis
```

**Services:**

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | `5432` | Database with pgvector extension |
| Redis | `6379` | Cache, pub/sub, job queue |
| Backend API | `8000` | FastAPI server + Swagger docs |

```bash
# Verify all containers healthy
docker compose ps

# View logs
docker compose logs -f backend

# Run migrations (first time only)
docker compose exec backend alembic upgrade head
```

### 3. Local Development (Recommended)

Run backend and frontend locally for hot-reload:

```bash
# Terminal 1: Start DB + Redis only
docker compose up -d postgres redis

# Terminal 2: Backend (hot-reload)
cd backend
pip install -e ".[dev,ml]"
alembic upgrade head
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: Frontend (hot-reload)
cd frontend
npm install
npm run dev

# Terminal 4: ARQ workers (optional, for async jobs)
cd backend
arq src.workers.tasks.WorkerSettings
```

### 4. Verify

```bash
# Backend health
curl http://localhost:8000/health
# {"status":"ok","environment":"development"}

# Create API key
curl -X POST http://localhost:8000/api/v1/api-keys \
  -H "Content-Type: application/json" \
  -d '{"name":"test-key"}'
# {"id":"...","key":"sk-...","name":"test-key"}

# Swagger docs
open http://localhost:8000/docs

# Dashboard
open http://localhost:3000/dashboard
```

### One-Liner (Full Stack)

```bash
docker compose up -d && sleep 5 && docker compose exec backend alembic upgrade head && curl http://localhost:8000/health
```

---

## Development Commands

### Backend

```bash
cd backend

# Linting
ruff check src/                    # Check
ruff check src/ --fix              # Auto-fix

# Type checking
mypy --ignore-missing-imports src/

# Testing
pytest                             # Run all tests
pytest -v                          # Verbose output
pytest --cov=src                   # With coverage

# Database
alembic upgrade head               # Apply migrations
alembic downgrade -1               # Rollback one migration
alembic revision --autogenerate -m "description"  # Create migration

# Development server
uvicorn src.main:app --reload --port 8000

# Worker
arq src.workers.tasks.WorkerSettings
```

### Frontend

```bash
cd frontend

# Development
npm run dev                        # Start dev server (port 3000)
npm run build                      # Production build
npm run start                      # Start production server

# Linting & Type checking
npm run lint                       # ESLint
npx tsc --noEmit                   # TypeScript check

# Testing (coming soon)
# npm run test                     # Vitest
# npm run test:e2e                 # Playwright
```

### Docker

```bash
# Start all services
docker compose up -d

# Start specific services
docker compose up -d postgres redis
docker compose up -d backend

# View logs
docker compose logs -f backend
docker compose logs -f postgres

# Stop services
docker compose down                # Stop (preserve data)
docker compose down -v             # Stop + wipe volumes

# Database shell
docker compose exec postgres psql -U flux -d flux_gateway

# Redis CLI
docker compose exec redis redis-cli
```

---

## Project Structure

```
Flux_gateway/
├── docker-compose.yml              # PostgreSQL, Redis, backend services
├── .env.template                   # Environment variables template
│
├── backend/
│   ├── pyproject.toml              # Python dependencies (FastAPI, LangGraph, ARQ, Stripe)
│   ├── alembic.ini                 # Database migration config
│   └── src/
│       ├── main.py                 # FastAPI app entry, router registration
│       ├── core/                   # Config, security, OIDC, tenant context, middleware
│       ├── db/
│       │   ├── models/             # SQLAlchemy models (10 tables)
│       │   ├── migrations/         # Alembic migrations (3 versions)
│       │   ├── session.py          # Async engine + session factory
│       │   └── tenant_isolation.py # Auto tenant filtering on queries
│       ├── api/v1/                 # REST API routers (13 endpoints groups)
│       │   ├── auth.py             # OIDC login/callback
│       │   ├── api_keys.py         # API key CRUD
│       │   ├── connections.py      # DB connection CRUD
│       │   ├── schema_endpoints.py # Schema reflection/cache
│       │   ├── query.py            # Simple NL query
│       │   ├── rag.py              # Document upload, search, RAG Q&A
│       │   ├── agent.py            # Full LangGraph agent pipeline
│       │   ├── sandbox.py          # Docker code execution
│       │   ├── events.py           # Event log CRUD
│       │   ├── webhooks.py         # Webhook config + ingestion
│       │   ├── behavior_rules.py   # Automation rules CRUD
│       │   ├── ws.py               # WebSocket endpoint
│       │   └── usage.py            # Usage tracking/billing
│       ├── agents/                 # LangGraph 7-node pipeline
│       │   ├── graph.py            # Workflow definition + run_agent()
│       │   ├── state.py            # AgentState TypedDict
│       │   └── nodes/              # classify, research, code, review, heal, execute, format
│       ├── services/               # Business logic
│       │   ├── llm.py              # OpenRouter + local fallback
│       │   ├── rag_ingestion.py    # PDF/MD/TXT parsing, chunking, embedding
│       │   ├── rag_query.py        # Hybrid search (vector + BM25 + RRF)
│       │   ├── sandbox.py          # Docker SQL validation
│       │   ├── schema_cache.py     # Redis schema cache
│       │   ├── schema_reflection.py # PostgreSQL introspection
│       │   ├── websocket_manager.py # Per-tenant WS connection pool
│       │   ├── event_bus.py        # Redis Pub/Sub
│       │   ├── behavior_rules.py   # Rule evaluation engine
│       │   ├── webhook_service.py  # HMAC verification + ingestion
│       │   └── usage_tracker.py    # Token/compute/storage tracking
│       └── workers/                # ARQ async workers
│           └── tasks.py            # process_event, run_agent_task
│
├── frontend/
│   ├── package.json                # Next.js 16, React 19, Tailwind v4, shadcn/ui
│   └── src/
│       ├── app/                    # Next.js App Router pages
│       │   ├── dashboard/          # 8 dashboard sections
│       │   └── api/                # Next.js API proxy
│       ├── components/
│       │   ├── ui/                 # 29 shadcn/ui primitives (Radix-based)
│       │   ├── providers.tsx       # QueryClient, Toaster, ErrorBoundary
│       │   ├── error-boundary.tsx  # React error boundary
│       │   ├── sidebar.tsx         # Collapsible navigation
│       │   └── header.tsx          # Top bar
│       └── lib/
│           ├── api.ts              # Typed API client
│           ├── ws.ts               # WebSocket client (auto-reconnect)
│           ├── toast.ts            # Sonner toast wrapper
│           └── utils.ts            # cn() helper
│
└── docs/
    ├── CURRENT_STATE.md            # What's built, what's next
    ├── MASTER_GUIDE.md             # Full architecture deep-dive
    ├── architecture/               # System overview, data flows
    ├── modules/                    # Feature specs (event-gateway, etc.)
    └── roadmap/                    # Stage 1-3 task breakdowns
```

---

## API Reference

### Authentication

All endpoints require `X-API-Key: sk-...` header (except `/health` and `/api/v1/auth/*`).

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/auth/login` | OIDC login redirect |
| `GET` | `/api/v1/auth/callback` | OIDC callback |

### API Keys

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/api-keys` | Create API key |
| `GET` | `/api/v1/api-keys` | List API keys |
| `DELETE` | `/api/v1/api-keys/{id}` | Revoke API key |

### Connections

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/connections` | Create DB connection |
| `GET` | `/api/v1/connections` | List connections |
| `DELETE` | `/api/v1/connections/{id}` | Delete connection |
| `POST` | `/api/v1/connections/{id}/test` | Test connection |

### Schema

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/connections/{id}/reflect` | Reflect DB schema |
| `GET` | `/api/v1/connections/{id}/schema` | Get cached schema |
| `POST` | `/api/v1/schema/refresh` | Refresh all schemas |
| `GET` | `/api/v1/schema/test` | Test schema endpoint |

### Query & Agent

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/query` | Simple NL query |
| `POST` | `/api/v1/agent/query` | Full LangGraph agent pipeline |
| `POST` | `/api/v1/sandbox/execute` | Execute SQL in Docker sandbox |

### RAG (Retrieval-Augmented Generation)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/rag/documents` | Upload document (PDF/MD/TXT) |
| `GET` | `/api/v1/rag/documents` | List documents |
| `DELETE` | `/api/v1/rag/documents/{id}` | Delete document |
| `POST` | `/api/v1/rag/search` | Hybrid search (vector + BM25) |
| `POST` | `/api/v1/rag/ask` | RAG Q&A with citations |

### Event Gateway

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/events` | List events (paginated, filterable) |
| `GET` | `/api/v1/events/{id}` | Get event details |
| `POST` | `/api/v1/events/{id}/retry` | Retry failed event |
| `WS` | `/ws/{tenant_id}` | WebSocket event stream |

### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/webhooks` | Create webhook config |
| `GET` | `/api/v1/webhooks` | List webhook configs |
| `PATCH` | `/api/v1/webhooks/{id}` | Update webhook config |
| `DELETE` | `/api/v1/webhooks/{id}` | Delete webhook config |
| `POST` | `/api/v1/webhooks/ingest/{hook_id}` | Ingest webhook (HMAC verified) |

### Behavior Rules

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/behavior-rules` | Create automation rule |
| `GET` | `/api/v1/behavior-rules` | List rules |
| `PATCH` | `/api/v1/behavior-rules/{id}` | Update rule |
| `DELETE` | `/api/v1/behavior-rules/{id}` | Delete rule |

### Usage & Billing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/usage/summary` | Current month usage |
| `GET` | `/api/v1/usage/history` | Usage history (monthly) |

---

## Database Schema

**10 tables across 3 migrations:**

| Table | Purpose |
|-------|---------|
| `tenants` | Multi-tenant root |
| `users` | OIDC users linked to tenants |
| `api_keys` | SHA-256 hashed API keys |
| `connections` | Encrypted DB connection strings |
| `schema_cache` | JSON schema snapshots |
| `credentials` | Fernet-encrypted service credentials |
| `documents` | RAG uploaded documents |
| `chunks` | Text chunks + pgvector(1536) embeddings |
| `citations` | Query-to-chunk references |
| `webhook_configs` | Webhook endpoint configurations |
| `behavior_rules` | Automation trigger rules (JSONB conditions) |
| `event_log` | Webhook event audit trail |
| `usage_records` | Monthly token/compute/storage tracking |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL async connection string |
| `REDIS_URL` | Yes | — | Redis connection string |
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key for GPT-4o |
| `FERNET_KEY` | No | auto-generated | Encryption key for credentials |
| `OIDC_ISSUER` | No | — | OIDC provider URL |
| `OIDC_CLIENT_ID` | No | — | OIDC client ID |
| `OIDC_CLIENT_SECRET` | No | — | OIDC client secret |
| `STRIPE_SECRET_KEY` | No | — | Stripe secret key for billing |
| `SANDBOX_ENABLED` | No | `true` | Enable Docker sandbox |
| `SANDBOX_TIMEOUT` | No | `30` | Sandbox execution timeout (seconds) |

---

## Documentation

- **[CURRENT_STATE.md](docs/CURRENT_STATE.md)** — What's built now, what's next
- **[MASTER_GUIDE.md](docs/MASTER_GUIDE.md)** — Full architecture deep-dive
- **[docs/architecture/](docs/architecture/)** — System overview, data flows, security model
- **[docs/modules/](docs/modules/)** — Feature specs (event-gateway, schema-engine, etc.)
- **[docs/roadmap/](docs/roadmap/)** — Stage 1-3 task breakdowns, future goals

---

## License

Proprietary. All rights reserved.

---

<div align="center">

**Built with FastAPI · LangGraph · PostgreSQL · Redis · Next.js**

</div>
