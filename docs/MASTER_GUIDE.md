# Flux Gateway — Master Guide

> **Data-to-Agent Gateway** | B2B SaaS | Zapier for Agentic Context  
> Last built: Stage 3 Week 9 (Docker Sandbox) | Next: Week 10 (Event Gateway)

---

## Table of Contents

1. [What Is Flux Gateway](#1-what-is-flux-gateway)
2. [Architecture Overview](#2-architecture-overview)
3. [Stage 1: Core Infrastructure (Weeks 1-4)](#3-stage-1-core-infrastructure)
4. [Stage 2: Productization (Weeks 5-8)](#4-stage-2-productization)
5. [Stage 3: Scale (Weeks 9-12)](#5-stage-3-scale)
6. [Security Model](#6-security-model)
7. [Agent Topology](#7-agent-topology)
8. [Decision Rationale](#8-decision-rationale)
9. [Dev → Production Evolution](#9-dev--production-evolution)
10. [Full File Tree](#10-full-file-tree)
11. [API Reference](#11-api-reference)

---

## 1. What Is Flux Gateway

Companies paste a DB connection string or API URL → platform auto-maps schema, indexes documents, deploys a secure NL agent that reads data and executes validated write-backs. No custom integration code needed.

**Problem it solves**: Mid-market businesses spend $150K+ sourcing engineers for custom integrations (Odoo, HubSpot, SQL databases). Thousands of hours lost to manual menu navigation — "the thousand clicks problem."

**Core value**: 5 minutes from connection string to production NL agent with zero-hallucination safety guarantees.

### The Three Pillars

```
┌──────────────────────────────────────────────────────────────────┐
│                        FLUX GATEWAY                              │
│                                                                  │
│  1. SCHEMA AUTO-DISCOVERY                                        │
│     Metadata-only DB reflection → JSON schema graph              │
│     LLM uses exact column names, never hallucinates              │
│                                                                  │
│  2. ISOLATED HYBRID RAG                                          │
│     pgvector dense + BM25 lexical → fused ranking                │
│     Every answer has Citation Tracking Graph (audit trail)       │
│                                                                  │
│  3. ACTION SANDBOX                                                │
│     LangGraph 7-node agent → Docker sandbox → validated exec     │
│     Self-healing retry loop (max 3) for generated code           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Overview

```
                            ┌──────────────────────────┐
                            │     CLIENT INFRASTRUCTURE  │
                            │                            │
                            │  Production DBs (PG/MySQL) │
                            │  Internal Docs (S3,Files)  │
                            │  Business Apps (Odoo,etc)  │
                            └──────────┬─────────────────┘
                                       │
                          ┌────────────┼────────────┐
                          │ HTTPS       │ Webhooks   │ MCP
                          ▼             ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLUX GATEWAY PLATFORM                         │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              FASTAPI API GATEWAY                            │  │
│  │  Auth MW │ Tenant MW │ Rate Limit │ CORS │ Audit Log       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│     ┌────────────────────────┼────────────────────────┐         │
│     ▼                        ▼                        ▼         │
│  ┌──────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │ SCHEMA   │  │      RAG ENGINE      │  │  AGENT SANDBOX   │  │
│  │ ENGINE   │  │                      │  │                  │  │
│  │          │  │  Ingest → Chunk →    │  │  LangGraph       │  │
│  │ Reflect  │  │  Embed → pgvector    │  │  7-Node State    │  │
│  │ information│  │                      │  │  Machine         │  │
│  │ _schema  │  │  Hybrid Search       │  │                  │  │
│  │ → JSON   │  │  Vector + BM25 + RRF │  │  Docker Sandbox  │  │
│  │ → Redis  │  │  Citation Tracking   │  │  MCP Client      │  │
│  └──────────┘  └──────────────────────┘  └──────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  EVENT GATEWAY                              │  │
│  │  Webhooks → Redis Pub/Sub → ARQ Workers → WebSocket Stream │  │
│  │  Behavior Rules Matrix → Autonomous Agent Loops            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────┐    ┌──────────────────────────────┐   │
│  │ PostgreSQL 16        │    │ Redis 7                       │   │
│  │ + pgvector           │    │                               │   │
│  │                      │    │ Schema Cache (TTL 1hr)        │   │
│  │ Tenant Data          │    │ Rate Limiting (Token Bucket)  │   │
│  │ Vector Store (1536d) │    │ Pub/Sub (Per-Tenant Channel)  │   │
│  │ Event Log            │    │ Worker Queue (ARQ)            │   │
│  │ Credential Store     │    │ BM25 Index (In-Memory)        │   │
│  │ (AES-256-GCM)        │    │                               │   │
│  └─────────────────────┘    └──────────────────────────────┘   │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                DOCKER ENGINE                                │  │
│  │  Ephemeral Containers (no network, tmpfs, 30s timeout)     │  │
│  │  Validate code BEFORE touching production databases        │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                       │
                          ┌────────────┼────────────┐
                          ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FRONTEND DASHBOARD                               │
│                  Next.js 16 App Router                            │
│                                                                  │
│  shadcn/ui │ Magic UI │ Motion.dev │ Geist Font │ Dark-First    │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │Dashboard │ │Connection│ │ Schema   │ │Agent Chat│          │
│  │ Home     │ │ Manager  │ │ Explorer │ │Interface │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │Document  │ │ Events   │ │ Settings │ │BFF Proxy │          │
│  │ Manager  │ │ Monitor  │ │ +API Keys│ │(→FastAPI)│          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow: Three Lifecycle Traces

```
READ QUERY TRACE
─────────────────
User: "Show me all orders from last week"
  │
  ├─► Frontend SDK captures {prompt, user_role, session_id}
  ├─► POST /api/v1/agent/query (HTTPS + X-API-Key)
  ├─► Auth MW: API key → resolve tenant_id
  ├─► Tenant MW: inject tenant_id into context var
  ├─► Rate Limiter: check token bucket (100/60s)
  ├─► LangGraph Agent:
  │     ├─ classify_intent → "read"
  │     ├─ researcher_node:
  │     │    ├─ Embed query → pgvector cosine search
  │     │    ├─ BM25 lexical search (tenant-scoped)
  │     │    ├─ RRF fusion (k=60, vector=0.7, bm25=0.3)
  │     │    ├─ Top-10 chunks → context assembly
  │     │    └─ LLM generates answer with [1]...[10] citations
  │     └─ format_response
  └─► Response: {answer, citations[], tokens_used: 1450, latency_ms: 820}

WRITE ACTION TRACE
──────────────────
User: "Set inventory SKU-123 to 500 units"
  │
  ├─► Same auth + tenant injection
  ├─► LangGraph Agent:
  │     ├─ classify_intent → "write"
  │     ├─ coder_node:
  │     │    └─ Schema-grounded SQL: UPDATE inventory SET quantity = $1
  │     │       WHERE sku = $2 AND tenant_id = $3
  │     │       (parameterized, exact column names from graph)
  │     ├─ reviewer_node:
  │     │    ├─ Docker sandbox (no network, 256MB, tmpfs, 30s)
  │     │    ├─ Validate: syntax, columns exist, parameterized, no DROP/TRUNCATE
  │     │    └─ Result: {passed: true, errors: []}
  │     ├─ mcp_exec_node:
  │     │    └─ JSON-RPC 2.0 → client's MCP Server → execute
  │     └─ format_response
  └─► Response: {answer: "Inventory updated...", execution_result: {rows_affected: 1}}

WRITE FAILURE + SELF-HEALING TRACE
───────────────────────────────────
Coder generates: UPDATE inventory SET qty = 500 WHERE sku = 'SKU-123'
  │
  ├─► Reviewer Docker sandbox: ✗ Column 'qty' does not exist.
  │     Available: sku, quantity, warehouse_id
  │
  ├─► self_heal_node (retry_count: 1 of 3):
  │     └─ LLM: Fix column name qty→quantity, parameterize SKU-123
  │
  ├─► Back to coder_node → regenerates fixed SQL
  ├─► Reviewer re-validates → PASS
  └─► MCP executes successfully
```

---

## 3. Stage 1: Core Infrastructure

### What Was Built (Weeks 1-4)

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: CORE INFRASTRUCTURE                                     │
│                                                                  │
│ Week 1: Monorepo scaffold + Docker env                           │
│   docker-compose.yml (PG16+pgvector, Redis 7, FastAPI)          │
│   backend/pyproject.toml (uv), frontend/ (Next.js 16 placeholder)│
│                                                                  │
│ Week 1: Multi-tenant DB schema                                   │
│   6 tables: tenants, users, api_keys, connections,               │
│             schema_cache, credentials                            │
│   Alembic migration 0001_initial.py                              │
│   Triple-layer tenant isolation from day 1                       │
│                                                                  │
│ Week 2: FastAPI core + Auth                                      │
│   Dual-mode: API keys (sk- prefix, hashed) + OIDC/JWT           │
│   Redis token bucket rate limiter (100 req/60s)                  │
│   Connection CRUD (encrypted connection strings)                 │
│                                                                  │
│ Week 3: Schema reflection engine                                 │
│   asyncpg → information_schema queries                           │
│   JSON metadata graph (tables/columns/keys/indexes/relationships)│
│   Redis cache (TTL 1hr, per-tenant, per-connection)             │
│                                                                  │
│ Week 4: LLM integration + security hardening                     │
│   OpenRouter client (gpt-4o-mini for queries)                    │
│   Schema-grounded NL queries (system prompt = real column names) │
│   Security headers, audit logging, penetration test              │
│                                                                  │
│ MILESTONE: Connect any PG DB → reflect schema → NL query about   │
│            schema structure. All tenant-isolated.                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why These Decisions

| Decision | Rationale |
|----------|-----------|
| **Monorepo** | Single repo for MVP — shared types, easier CI, no cross-repo version hell. Split later if needed. |
| **PostgreSQL + pgvector only** | One DB to manage. pgvector is mature, native, no extra service. HNSW indexes for scale. No MongoDB/MySQL until post-MVP. |
| **Triple-layer tenant isolation from day 1** | Cross-tenant data leak is a CATACLYSMIC failure mode. Fixing it retroactively is near-impossible. DB RLS + ORM listener + FastAPI dep = defense in depth. |
| **API keys + OIDC both** | API keys for programmatic SDK access (every B2B customer needs this). OIDC for web dashboard login. Both from day 1 avoids painful migration. |
| **OpenRouter over direct OpenAI** | Model flexibility — swap gpt-4o-mini for Claude, Llama, etc. without code changes. Avoids vendor lock-in. |
| **AES-256-GCM for credentials** | Connection strings contain passwords. Must be encrypted at rest. Fernet (AES-128-CBC) was initial choice, upgraded to AES-256-GCM for stronger encryption. |
| **Read-only information_schema reflection** | Never touch user tables. Metadata only. Even if reflection code is exploited, it has SELECT-only on system catalogs. |
| **Redis token bucket** | Tried in-memory first — fails with multiple workers. Redis is shared state, works across processes, handles restarts. 100 req/60s is generous for early-stage B2B. |

### Dev → Production Changes

```
┌────────────────────────────┬─────────────────────────────────────┐
│ DEV                         │ PRODUCTION                          │
├─────────────────────────────┼─────────────────────────────────────┤
│ Single PostgreSQL instance  │ Read replicas, connection pooling   │
│ Env vars in .env            │ HashiCorp Vault / AWS Secrets Manager│
│ Single FastAPI process      │ K8s Deployment (3+ replicas, HPA)  │
│ No auth on Redis            │ Redis ACL + TLS                     │
│ structlog → console         │ structlog → OTEL → Grafana          │
│ No backup strategy          │ WAL-G continuous backups            │
└─────────────────────────────┴─────────────────────────────────────┘
```

---

## 4. Stage 2: Productization

### What Was Built (Weeks 5-8)

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: PRODUCTIZATION & VISUAL ENGINE                          │
│                                                                  │
│ Week 5: RAG Ingestion Pipeline                                   │
│   Upload PDF/MD/HTML/TXT                                         │
│   PyMuPDF parsing (PDFs)                                         │
│   tiktoken semantic chunking (1000t, 200t overlap, min 100t)    │
│   OpenAI text-embedding-3-small → 1536d vectors                  │
│   pgvector storage (per-tenant, HNSW index)                      │
│   Fallback: local SentenceTransformer all-MiniLM-L6-v2 (384d)   │
│                                                                  │
│ Week 6: Hybrid Search + Citation Tracking                        │
│   pgvector cosine distance search (top_k * 2 oversample)         │
│   BM25 lexical index (per-tenant, in-memory, lazy-built)         │
│   Reciprocal Rank Fusion: score = Σ 1/(k + rank_i), k=60        │
│   Weights: vector 0.7, BM25 0.3                                  │
│   Citations: [1] markers → {id, doc, page, score, excerpt}      │
│   Color-coded: green ≥0.9, yellow ≥0.7, red <0.7                │
│                                                                  │
│ Week 7: LangGraph Agent Orchestration                            │
│   7-node state machine (full details in §7)                       │
│   classify_intent → researcher/coder → reviewer → self_heal     │
│   → mcp_exec → format_response                                   │
│   Real token tracking (response.usage.total_tokens)              │
│   Session DI pattern (RunnableConfig, not SessionLocal leak)     │
│                                                                  │
│ Week 8: Next.js 16 Dashboard MVP                                 │
│   App Router layout groups: (auth) / (dashboard)                 │
│   11 pages: Home, Connections, Schema, Chat, Docs, Events,       │
│             Settings (+ API Keys, Billing stubs)                  │
│   Dark-first theme (oklch CSS vars, shadcn/ui tokens)            │
│   Magic UI animated components + Motion.dev                      │
│   Geist Sans (body) + Geist Mono (code)                          │
│   BFF proxy: app/api/[...path]/route.ts → FastAPI                │
│   WebSocket client: auto-reconnect, exponential backoff          │
│                                                                  │
│ MILESTONE: Full dashboard. Connect DB → explore schema →         │
│            upload docs → ask questions → get cited answers.       │
│            Agent generates + validates write operations.          │
└─────────────────────────────────────────────────────────────────┘
```

### Why These Decisions

| Decision | Rationale |
|----------|-----------|
| **OpenAI embeddings over local-only** | text-embedding-3-small is cheap ($0.02/1M tokens), high quality (1536d), zero setup. Local fallback exists for dev/offline. |
| **BM25 in-memory per-tenant** | Simplicity for MVP. Redis-backed BM25 planned for production (survives restarts, scales). Per-tenant isolation = no cross-tenant lexical bleed. |
| **RRF fusion over linear combination** | Scores from pgvector (cosine 0-1) and BM25 (unbounded) are incomparable. RRF normalizes via rank, works with any scoring function. k=60 is standard IR practice. |
| **Semantic chunking over fixed-size** | Fixed-size chunks split mid-paragraph, destroying meaning. Splitting on `\n\n` paragraphs + merging to token limit preserves semantic coherence. Overlap prevents boundary misses. |
| **LangGraph over custom state machine** | Battle-tested, visualization, checkpointing, conditional edges built-in. Why reinvent a state machine when LangGraph already solved it? |
| **Session via RunnableConfig** | Original code used `SessionLocal()` directly in nodes — leaks connections, bypasses DI, breaks tests. Fixed: session injected through LangGraph's config mechanism. |
| **Real token tracking from day 1** | Original code had hardcoded `+50 tokens`. Fixed to use `response.usage.total_tokens` from OpenRouter. Critical for billing accuracy. |
| **Server Components default (Next.js)** | Better perf — less JS shipped to client. Only interactive parts (Chat, Events) use 'use client'. |
| **Dark-first design** | Target users are engineers working late. Dark mode is table stakes. Light mode via CSS variable overrides. |
| **BFF proxy pattern** | Next.js API routes proxy to FastAPI. Avoids CORS issues, hides backend URL, allows server-side auth injection. |

### Dev → Production Changes

```
┌────────────────────────────┬─────────────────────────────────────┐
│ DEV                         │ PRODUCTION                          │
├─────────────────────────────┼─────────────────────────────────────┤
│ OpenAI embed (API)          │ BGE-large-en-v1.5 (local, 1024d)   │
│ BM25 in-memory              │ BM25 in Redis (persistent, scaled)  │
│ Single chunk per doc        │ Recursive parent-child chunks       │
│ Text-only RAG               │ Multi-modal (PDF images, tables)    │
│ No query rewriting          │ HyDE / multi-query expansion        │
│ No re-ranker                │ Cross-encoder re-ranking (Cohere)   │
│ npm run dev                 │ CDN (Vercel/Cloudflare)             │
│ Single region               │ Multi-region (edge rendering)       │
│ No model caching            │ Redis cache for frequent LLM answers│
└─────────────────────────────┴─────────────────────────────────────┘
```

---

## 5. Stage 3: Scale

### What Has Been Built (Week 9)

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 3: SCALE & INTEGRATIONS                                    │
│                                                                  │
│ Week 9 ✅: Docker Sandbox Execution                              │
│   Ephemeral Python 3.12-slim containers                          │
│   network_disabled: true, mem_limit: 256m, cpu_quota: 50000     │
│   read_only rootfs, tmpfs /tmp 64m, cap_drop: ALL               │
│   security_opt: no-new-privileges:true, timeout: 30s            │
│   auto_remove: true (destroyed after execution)                  │
│   Validation script (stdlib only): checks dangerous SQL,         │
│     injection patterns, parameterization, column existence       │
│   Prints JSON result to stdout → parsed by Reviewer              │
│   Fallback: in-process validation if Docker unavailable          │
│                                                                  │
│ Week 10 🔜: Event Gateway                                        │
│   WebSocket endpoint /ws/{tenant_id}                             │
│   Redis Pub/Sub per-tenant channel: tenant:{id}:events          │
│   ARQ worker pool for async agent dispatch                       │
│   Frontend: real-time event feed, progress bars                  │
│                                                                  │
│ Week 11 🔜: Behavior Rules + MCP Client                          │
│   Agentic Behavior Rules Matrix (YAML per-tenant)                │
│   Webhook ingestion: POST /webhooks/{tenant}/{hook}              │
│   MCP Client: JSON-RPC 2.0 over HTTPS to client MCP Server      │
│                                                                  │
│ Week 12 🔜: Usage Tracking + Hardening                           │
│   Token usage per tenant per model                               │
│   Usage telemetry dashboard (charts, cost estimation)            │
│   Billing integration prep (Stripe)                              │
│   Performance + security audit                                   │
│                                                                  │
│ MILESTONE (target): End-to-end platform. Webhook → agent loop    │
│   → sandbox execution → live dashboard streaming.                │
│   Usage tracking per tenant. Billing-ready.                      │
└─────────────────────────────────────────────────────────────────┘
```

### Why These Decisions

| Decision | Rationale |
|----------|-----------|
| **Docker over WASM for sandbox** | Docker is mature, debuggable, widely available. WASM is lighter but less battle-tested and harder to debug. Planned as fallback option. |
| **Validation in stdlib only** | Sandbox container has ONLY Python stdlib. No pip installs. No network. Attack surface: zero. |
| **Ephemeral, always-destroyed** | No container reuse. Every validation gets a fresh container. Prevents state leakage, timing attacks, resource buildup. |
| **ARQ over Celery** | ARQ is lighter, async-native, Redis-only. Celery adds RabbitMQ/Redis complexity. For MVP-scale async workers, ARQ is sufficient. |
| **Behavior Rules as YAML** | Human-readable, version-controllable, per-tenant. JSON alternative exists but YAML is more ergonomic for non-engineers configuring rules. |
| **MCP (Model Context Protocol)** | JSON-RPC 2.0 standard. Client runs MCP Server on their infrastructure — we never hold production credentials in hot memory. |

### Dev → Production Changes

```
┌────────────────────────────┬─────────────────────────────────────┐
│ DEV                         │ PRODUCTION                          │
├─────────────────────────────┼─────────────────────────────────────┤
│ Ephemeral single container  │ Container pool (pre-warmed), 10-    │
│                             │   container warm pool per tenant    │
│ WASM in evaluation          │ WASM for low-risk tasks (<10ms)     │
│ ARQ single worker           │ ARQ worker pool (4+ per tenant)     │
│ In-memory event queue       │ Redis Streams (persistent, DLQ)     │
│ Single WebSocket process    │ Redis Pub/Sub → multi-process fanout│
│ No event replay             │ Event sourcing, full replay         │
│ No dead letter queue        │ DLQ + retry with exponential backoff│
│ No HMAC webhook signing     │ HMAC-SHA256 signature verification  │
│ Basic usage tracking        │ Per-minute granularity, cost API    │
│ Stripe prep only            │ Full Stripe integration, usage-based│
└─────────────────────────────┴─────────────────────────────────────┘
```

---

## 6. Security Model

### Threat Surface & Mitigations

```
┌──────────────────────────────────────────────────────────────────┐
│                    THREAT MODEL (8 VECTORS)                       │
│                                                                   │
│  THREAT                            │ MITIGATION                   │
│  ──────────────────────────────────┼───────────────────────────── │
│  Cross-tenant data leak            │ Triple-layer: DB RLS →       │
│                                    │ ORM listener → FastAPI dep   │
│                                    │                               │
│  LLM hallucinates, corrupts DB     │ Schema grounding + Reviewer  │
│                                    │ sandbox validation            │
│                                    │                               │
│  Malicious code escapes sandbox    │ No network, tmpfs, CPU/mem   │
│                                    │ caps, no-new-privileges,     │
│                                    │ cap_drop ALL, ephemeral      │
│                                    │                               │
│  Connection string leak            │ AES-256-GCM encrypted at     │
│                                    │ rest, key in env var          │
│                                    │                               │
│  API key theft                     │ Hashed storage (bcrypt-like),│
│                                    │ rate limiting, audit log      │
│                                    │                               │
│  Webhook spoofing                  │ API key validation + optional│
│                                    │ HMAC signing                  │
│                                    │                               │
│  SQL injection via LLM output      │ Parameterized queries only,  │
│                                    │ Reviewer checks, read-only    │
│                                    │ reflection connection         │
│                                    │                               │
│  Cross-tenant vector search        │ Hardcoded WHERE tenant_id,   │
│                                    │ enforced at ORM level         │
└──────────────────────────────────────────────────────────────────┘
```

### Triple-Layer Tenant Isolation

```
LAYER 1: DATABASE (Row-Level Security)
──────────────────────────────────────
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON chunks FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
  ↑
  PostgreSQL enforces this at the C level. No bypass possible.

LAYER 2: ORM (SQLAlchemy Event Listener)
─────────────────────────────────────────
@event.listens_for(Session, "do_orm_execute")
def inject_tenant_filter(orm_execute_state):
    """Every SELECT/INSERT/UPDATE/DELETE gets WHERE tenant_id injected."""
    ↑
    Second line of defense. Catches queries that bypass RLS config.

LAYER 3: APPLICATION (FastAPI Dependency)
──────────────────────────────────────────
async def get_current_tenant(
    x_api_key: str = Header(alias="X-API-Key")
) -> UUID:
    """Extract tenant_id from API key. NEVER from client payload."""
    ↑
    Tenant B cannot impersonate Tenant A by sending a different tenant_id.
    Tenant ID comes from the API key, which is verified against the DB.
```

### Sandbox Container Security Profile

```
┌──────────────────────────────────────────────────────────────────┐
│                DOCKER SANDBOX SECURITY PROFILE                     │
│                                                                   │
│  network_mode: none          ◄── No network. No internet.         │
│  mem_limit: 256m             ◄── Can't exhaust host memory.       │
│  cpu_quota: 50000 (0.5 CPU)  ◄── Can't CPU-starve other tenants.  │
│  read_only: true             ◄── Can't write to container FS.     │
│  tmpfs: /tmp size=64m        ◄── Isolated scratch space only.     │
│  security_opt:               ◄── Can't gain root via setuid.      │
│    no-new-privileges:true                                         │
│  cap_drop: ALL               ◄── Zero kernel capabilities.        │
│  auto_remove: true           ◄── Destroyed after 30s. No reuse.   │
│  timeout: 30                 ◄── Kill if hangs.                   │
│                                                                   │
│  RUNTIME: python:3.12-slim, ONLY stdlib (no pip, no network).    │
│                                                                   │
│  BLOCKED SQL PATTERNS (Reviewer regex):                           │
│    DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE, COPY FROM       │
│    Tautologies: OR 1=1, OR '1'='1'                               │
│    Comment injection: ; --                                        │
│    Multi-statement: ; followed by SQL                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. Agent Topology

### 7-Node LangGraph State Machine

```
                              ┌──────────┐
                              │ __start__│
                              └────┬─────┘
                                   │
                                   ▼
                         ┌─────────────────────┐
                         │  classify_intent     │
                         │  Model: gpt-4o-mini  │
                         │  Output: read | write│
                         └─────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │ intent=read  │              │ intent=write
                    ▼              │              ▼
         ┌──────────────────┐     │    ┌──────────────────┐
         │ researcher_node  │     │    │   coder_node      │
         │ Model: gpt-4o    │     │    │ Model: gpt-4o     │
         │                  │     │    │                  │
         │ Hybrid RAG search│     │    │ Schema-grounded   │
         │ ↓                │     │    │ SQL generation    │
         │ Context assembly │     │    │ ↓                │
         │ ↓                │     │    │ Parameterized    │
         │ LLM answer +     │     │    │ queries only     │
         │ citations        │     │    └────────┬─────────┘
         └────────┬─────────┘     │             │
                  │               │             ▼
                  │               │    ┌──────────────────┐
                  │               │    │  reviewer_node    │
                  │               │    │ Rule-based        │
                  │               │    │                  │
                  │               │    │ Docker sandbox    │
                  │               │    │ ↓                │
                  │               │    │ Validate: syntax, │
                  │               │    │ columns, params,  │
                  │               │    │ no dangerous ops  │
                  │               │    └────────┬─────────┘
                  │               │             │
                  │               │    ┌────────┼────────┐
                  │               │    │ pass   │ fail    │
                  │               │    ▼        │        ▼
                  │               │ ┌────────┐ │ ┌──────────────┐
                  │               │ │mcp_exec│ │ │ self_heal    │
                  │               │ │        │ │ │ Model: gpt-4o│
                  │               │ │JSON-RPC│ │ │              │
                  │               │ │2.0 →   │ │ │ Parse error  │
                  │               │ │Client  │ │ │ → LLM fix    │
                  │               │ │MCP Svr │ │ │ → retry++    │
                  │               │ └───┬────┘ │ └──────┬───────┘
                  │               │     │      │        │
                  │               │     │      │  ┌─────┴──────┐
                  │               │     │      │  │retry < 3   │
                  │               │     │      │  ▼            │
                  │               │     │      │ coder_node   │
                  │               │     │      │              │
                  │               │     │      │  │retry >= 3 │
                  │               │     │      │  ▼            │
                  │               │     │      │ error → user │
                  │               │     │      │              │
                  ▼               ▼     ▼      ▼              ▼
         ┌──────────────────────────────────────────────────────┐
         │               format_response_node                    │
         │  Enrich with: citations, execution result,            │
         │  tokens_used, latency_ms, node_traces                │
         └──────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
                              ┌──────────┐
                              │ __end__  │
                              └──────────┘
```

### AgentState (Python TypedDict)

```python
class AgentState(TypedDict):
    # Request context
    tenant_id: str
    user_query: str
    user_role: str

    # Routing
    intent: str                    # "read" | "write" | "unknown"

    # Schema grounding
    schema_graph: Optional[dict]
    connection_id: Optional[str]

    # READ path
    retrieved_chunks: list[dict]   # [{id, content, doc_name, page, score}]
    citations: list[dict]          # [{id, doc, page, score, excerpt}]

    # WRITE path
    generated_code: Optional[str]
    target_system: Optional[str]

    # Review
    review_passed: Optional[bool]
    review_errors: list[str]
    retry_count: int
    max_retries: int               # default 3

    # Output
    final_response: Optional[str]
    execution_result: Optional[dict]

    # Telemetry
    tokens_used: int
    latency_ms: float
    node_traces: list[dict]        # [{node, latency_ms, tokens}]
    error: Optional[str]
```

### Node Execution Details

```
┌──────────────────┬───────────────┬──────────────────────────────────┐
│ NODE             │ MODEL         │ BEHAVIOR                          │
├──────────────────┼───────────────┼──────────────────────────────────┤
│ classify_intent  │ gpt-4o-mini   │ Binary classification:            │
│                  │               │ Is this a READ query or WRITE     │
│                  │               │ action? Fallback to "read" for    │
│                  │               │ safety. Returns real token count. │
├──────────────────┼───────────────┼──────────────────────────────────┤
│ researcher_node  │ gpt-4o        │ 1. Embed user query               │
│                  │               │ 2. pgvector cosine search (top_k*2)│
│                  │               │ 3. BM25 lexical search (top_k*2)  │
│                  │               │ 4. RRF fusion (k=60, v=0.7,b=0.3)│
│                  │               │ 5. Assemble context with [1]..[N] │
│                  │               │ 6. LLM generates cited answer     │
├──────────────────┼───────────────┼──────────────────────────────────┤
│ coder_node       │ gpt-4o        │ Schema graph as system prompt.    │
│                  │               │ Generates SQL using ONLY column    │
│                  │               │ names from graph. Parameterized   │
│                  │               │ queries ($1, $2) — never string   │
│                  │               │ concatenation.                    │
├──────────────────┼───────────────┼──────────────────────────────────┤
│ reviewer_node    │ Rule-based    │ Docker sandbox validation:        │
│                  │               │ 1. Dangerous SQL check (regex)    │
│                  │               │ 2. Injection pattern check        │
│                  │               │ 3. Parameterization check         │
│                  │               │ 4. Column existence check         │
│                  │               │ 5. Returns {passed, errors[]}     │
├──────────────────┼───────────────┼──────────────────────────────────┤
│ self_heal_node   │ gpt-4o        │ Receives: code + review_errors.   │
│                  │               │ LLM generates fixed version.      │
│                  │               │ Max 3 retries. After 3: error.    │
├──────────────────┼───────────────┼──────────────────────────────────┤
│ mcp_exec_node    │ N/A           │ Placeholder (Stage 3 Week 11).    │
│                  │               │ Will: JSON-RPC 2.0 → client MCP   │
│                  │               │ Server over HTTPS. Executes       │
│                  │               │ validated code against real DB.   │
├──────────────────┼───────────────┼──────────────────────────────────┤
│ format_response  │ N/A           │ Enriches response with citations, │
│                  │               │ execution result, tokens, latency.│
│                  │               │ Formats for frontend display.     │
└──────────────────┴───────────────┴──────────────────────────────────┘
```

---

## 8. Decision Rationale

### 8.1 Why PostgreSQL + pgvector (Single DB)

```
OPTIONS EVALUATED:
  A) PostgreSQL + pgvector + separate vector DB (Pinecone/Weaviate)
  B) PostgreSQL + pgvector only
  C) MySQL + separate vector DB

CHOSEN: B — Single DB

WHY:
  - One DB to manage, backup, monitor
  - pgvector is mature (ivfflat + HNSW indexes)
  - No network latency between relational + vector queries
  - Hybrid search (SQL JOIN + vector distance) in one query
  - Tenant isolation via RLS works on vector data too
  - At MVP scale (<100M vectors), pgvector performance is sufficient

WHEN TO SPLIT:
  - >100M vectors per tenant
  - Need for specialized vector DB features (filtered search, quantization)
  - Then: migrate vectors to pgvector replica or Qdrant
```

### 8.2 Why OpenRouter (Not Direct OpenAI)

```
OPTIONS EVALUATED:
  A) Direct OpenAI API (gpt-4o, gpt-4o-mini)
  B) Direct Anthropic API (Claude 3.5 Sonnet)
  C) OpenRouter (unified API for all providers)
  D) Local models only (Ollama, Llama)

CHOSEN: C — OpenRouter

WHY:
  - Model flexibility: swap gpt-4o-mini for Claude Haiku without code change
  - Cost optimization: route cheap queries to cheap models
  - Fallback: if OpenAI is down, route to Anthropic automatically
  - No vendor lock-in: can migrate to any provider
  - Same OpenAI-compatible API surface: drop-in replacement
  - For MVP: use best model per task. Classify → cheap. Generate → quality.
  - Local fallback (Ollama) can be added via OpenRouter-compatible endpoint

WHEN TO CHANGE:
  - If OpenRouter latency becomes an issue (adds ~50-100ms hop)
  - If direct provider contracts offer better pricing at scale
  - Then: keep OpenRouter as fallback, add direct provider as primary
```

### 8.3 Why Dual Auth (API Keys + OIDC)

```
OPTIONS EVALUATED:
  A) API keys only (simpler MVP)
  B) OIDC only (better security)
  C) Both from day 1

CHOSEN: C — Both

WHY:
  - API keys: required for SDK/programmatic access. Every B2B customer
    needs this. Hashed storage, sk- prefix for secret scanning.
  - OIDC/JWT: required for web dashboard login. Google/GitHub OAuth.
    Auto-creates tenant on first login.
  - Migrating from A→C later is painful: token format changes,
    middleware rewrites, customer communication overhead.
  - Both coexist: API key for SDK, JWT for dashboard. Same tenant
    resolution in FastAPI dependency.

HOW IT WORKS:
  FastAPI Dependency chain:
    1. Check X-API-Key header → hash → lookup api_keys table → tenant_id
    2. OR Check Authorization: Bearer <JWT> → decode → tenant_id
    3. If neither present → 401 Unauthorized
    4. Set context var: current_tenant_id = resolved_tenant_id
```

### 8.4 Why LangGraph (Not Custom State Machine)

```
OPTIONS EVALUATED:
  A) Custom Python state machine (if/elif/else chain)
  B) LangGraph (LangChain's graph framework)
  C) Prefect/Temporal (workflow engines)

CHOSEN: B — LangGraph

WHY:
  - Purpose-built for LLM agent orchestration
  - Conditional edges: route based on LLM output (read vs write)
  - Visualization: generate graph diagrams automatically
  - Checkpointing: save/resume agent state (future: human-in-loop)
  - MCP ecosystem integration
  - Graph is declarative: add/remove nodes without restructuring
  - Battle-tested: used by LangChain, Replit, many startups

WHY NOT CUSTOM:
  - Custom state machine → you end up building LangGraph badly
  - Edge cases multiply: retries, timeouts, conditional routing
  - Visualization, debugging, checkpointing — you'd build all of it
  - LangGraph is just 2KB of import. Low cost, high value.

WHY NOT PREFECT/TEMPORAL:
  - Overkill for request-scoped agent state
  - Adds external service dependency
  - Better suited for long-running multi-day workflows (data pipelines)
```

### 8.5 Why Docker Sandbox (Not WASM)

```
OPTIONS EVALUATED:
  A) Docker containers
  B) WASM (WebAssembly) runtime
  C) gVisor/Firecracker microVMs
  D) In-process subprocess with seccomp

CHOSEN: A — Docker (for MVP)

WHY:
  - Docker is ubiquitous: every dev has it, every cloud runs it
  - Mature security features: no-network, tmpfs, cap_drop, seccomp profiles
  - Easy debugging: docker logs, docker exec for inspection
  - Python 3.12-slim image is 50MB, starts in <2s (acceptable for MVP)
  - WASM is faster but less mature, harder to debug, fewer Python libraries

WHEN TO ADD WASM:
  - When cold start latency matters (<100ms target)
  - For high-frequency, low-complexity validations
  - WASM as fast path, Docker as full validation path

WHY NOT gVISOR/FIRECRACKER:
  - Adds operational complexity (separate runtime to manage)
  - Overkill for MVP code validation
  - Consider at enterprise deployment stage (SOC 2)
```

### 8.6 Why Next.js App Router (Not Pages Router or SPA)

```
OPTIONS EVALUATED:
  A) Next.js Pages Router (stable, proven)
  B) Next.js App Router (newer, RSC)
  C) Vite + React SPA
  D) Remix

CHOSEN: B — Next.js App Router

WHY:
  - Server Components by default: less JS shipped to client
  - Layout groups ((dashboard)): shared sidebar/header without prop drilling
  - Streaming: suspense boundaries for data fetching
  - BFF pattern: api/[...path]/route.ts proxying to FastAPI
  - shadcn/ui is built for App Router (server components compatible)
  - Geist font integration: next/font, zero layout shift
  - Vercel deployment (optional, works on any Node host)

WHY NOT PAGES ROUTER:
  - Legacy direction. All new Next.js features target App Router.
  - Server Components are the future of React.

WHY NOT SPA:
  - SEO not critical for dashboard, but RSC performance gain IS critical
  - BFF proxy eliminates CORS issues
  - Server-side data fetching hides backend URL
```

---

## 9. Dev → Production Evolution

### Full Evolution Table

```
┌──────────────────────────┬─────────────────────────────────────────────┐
│ DEVELOPMENT (CURRENT)     │ PRODUCTION (TARGET)                         │
├──────────────────────────┼─────────────────────────────────────────────┤
│                          │                                              │
│ INFRASTRUCTURE            │                                              │
│ ─────────────             │                                              │
│ Docker Compose (3 svc)   │ Kubernetes (Deployment, HPA, Service, Ingress)│
│ Single PG instance       │ PG with read replicas (pgBouncer pooling)    │
│ Single Redis instance    │ Redis Cluster / Sentinel for HA              │
│ Env vars in .env         │ HashiCorp Vault / AWS Secrets Manager        │
│ Local Docker Engine      │ Kubernetes Pod Security Policies + Runtime   │
│                          │                                              │
│ AUTH                      │                                              │
│ ────                      │                                              │
│ Fernet (AES-128-CBC)     │ AES-256-GCM with key rotation (Vault)        │
│ API key in header        │ mTLS + API key for service-to-service        │
│ OIDC with mock provider  │ OIDC with Google/GitHub/SAML (Okta/Auth0)   │
│                          │                                              │
│ AI/ML                     │                                              │
│ ─────                     │                                              │
│ OpenRouter API            │ Direct provider contracts + OpenRouter       │
│                           │   fallback for resilience                    │
│ OpenAI embed (API)        │ BGE-large-en-v1.5 (local, 1024d, GPU)       │
│ Single model per task     │ Model tiering: Haiku for classify,           │
│                           │   Sonnet for generate, local for embed       │
│                          │                                              │
│ RAG                       │                                              │
│ ───                       │                                              │
│ BM25 in-memory            │ BM25 in Redis (persistent, tenant-isolated)  │
│ Single chunk flat         │ Recursive parent-child chunks                │
│ Text only                 │ Multi-modal: PDF images, tables, charts      │
│ No query rewriting        │ HyDE + multi-query + cross-encoder rerank   │
│                          │                                              │
│ AGENT                     │                                              │
│ ─────                     │                                              │
│ Ephemeral Docker per req  │ Container pool (10+ pre-warmed per tenant)   │
│                         │ + WASM fast path for simple validations        │
│ Self-heal 3 retries       │ Escalation: retry → human approval → rollback│
│ Single-step actions       │ Multi-step DAG tool calls with checkpoints   │
│ No memory                 │ Agent memory: conversation history,           │
│                           │   learned patterns per tenant                │
│                          │                                              │
│ OBSERVABILITY             │                                              │
│ ─────────────             │                                              │
│ structlog → console       │ structlog → OpenTelemetry → Grafana/Tempo    │
│ No metrics                │ Prometheus: request latency, error rate,      │
│                           │   token usage, sandbox health                │
│ No tracing                │ Distributed tracing: every agent node traced  │
│ Basic audit log (Redis)   │ Structured audit log → PostgreSQL/Elastic    │
│                          │                                              │
│ FRONTEND                  │                                              │
│ ────────                  │                                              │
│ npm run dev               │ CDN (Vercel / Cloudflare Pages)              │
│ Single region             │ Multi-region edge rendering                  │
│ No PWA                    │ PWA for offline agent chat                    │
│ Mock data for stubs       │ Real data with optimistic UI + React Query   │
│                          │                                              │
│ BILLING                   │                                              │
│ ───────                   │                                              │
│ No billing                │ Stripe: usage-based (tokens + compute +      │
│                           │   storage), per-tenant plans, annual billing  │
│ No cost tracking          │ Per-minute token cost, budget alerts per     │
│                           │   tenant, hard caps with graceful degradation │
│                          │                                              │
│ SCALING                   │                                              │
│ ───────                   │                                              │
│ Single process uvicorn    │ K8s HPA: CPU/memory auto-scaling (3-10 pods) │
│ No load testing           │ k6/JMeter: regular load tests at scale       │
│ No rate limit tiers       │ Per-plan rate limits: free (10/min),          │
│                           │   pro (100/min), enterprise (1000/min)        │
│ No data residency         │ EU/US/APAC region selection for data          │
│                           │   sovereignty compliance                      │
└──────────────────────────┴─────────────────────────────────────────────┘
```

---

## 10. Full File Tree

```
Flux_gateway/
├── docker-compose.yml              # PG16+pgvector, Redis 7, FastAPI
├── Dockerfile                      # Backend container
├── .env.template                   # All config vars
├── .gitignore
├── README.md                       # Project overview + quick start
├── PROJECT_PLAN.md                 # Master implementation plan
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml              # Python deps (uv)
│   ├── alembic.ini                 # DB migration config
│   └── src/
│       ├── main.py                 # FastAPI app entry (CORS, routers, security headers)
│       ├── core/
│       │   ├── config.py           # Pydantic Settings (DB, Redis, OpenRouter, OIDC, sandbox)
│       │   ├── tenant.py           # ContextVar-based tenant isolation
│       │   ├── security.py         # Fernet encrypt/decrypt (AES-256-GCM)
│       │   ├── oidc.py             # OIDC discovery, token exchange, JWT create/decode
│       │   ├── redis_client.py     # Async Redis singleton
│       │   └── security_middleware.py  # Rate limiting (100/60s token bucket) + audit log
│       ├── db/
│       │   ├── models/
│       │   │   ├── __init__.py     # Re-exports: Tenant, User, ApiKey, Connection,
│       │   │   │                   #   SchemaCache, Credential, Document, Chunk, Citation
│       │   │   ├── document.py     # Document ORM model
│       │   │   ├── chunk.py        # Chunk ORM model (pgvector Vector(1536))
│       │   │   └── citation.py     # Citation ORM model
│       │   ├── session.py          # AsyncSession factory
│       │   ├── tenant_isolation.py # ORM listener: inject WHERE tenant_id on all queries
│       │   └── migrations/
│       │       ├── env.py          # Async Alembic runner
│       │       └── versions/
│       │           ├── 0001_initial.py  # tenants, users, api_keys, connections,
│       │           │                    #   schema_cache, credentials
│       │           └── 0002_rag.py      # documents, chunks (pgvector), citations
│       ├── api/
│       │   ├── deps.py             # authenticate (API key + JWT), require_tenant
│       │   └── v1/
│       │       ├── auth.py         # OIDC login/callback, auto-creates tenant
│       │       ├── api_keys.py     # CRUD for API keys (hashed, sk- prefix)
│       │       ├── connections.py  # CRUD for DB connections (encrypted strings)
│       │       ├── schema_endpoints.py  # Reflect/cache/get/test schema
│       │       ├── query.py        # Schema-grounded NL query with OpenRouter LLM
│       │       ├── rag.py          # Document upload, hybrid search, RAG ask, citations
│       │       ├── agent.py        # LangGraph agent: POST /agent/query, get/list
│       │       └── sandbox.py      # POST /sandbox/execute (Docker sandbox)
│       ├── agents/
│       │   ├── state.py            # AgentState TypedDict (all fields)
│       │   ├── graph.py            # StateGraph builder (7 nodes, 3 conditional edges)
│       │   └── nodes/
│       │       ├── classify_intent.py   # gpt-4o-mini: read | write | unknown
│       │       ├── researcher.py        # Hybrid RAG → LLM answer with citations
│       │       ├── coder.py             # Schema-grounded SQL generation
│       │       ├── reviewer.py          # Docker sandbox validation (rule-based)
│       │       ├── self_heal.py         # LLM fix → retry (max 3)
│       │       ├── mcp_executor.py      # Placeholder → JSON-RPC 2.0 to MCP Server
│       │       └── format_response.py   # Enrich response with metadata
│       └── services/
│           ├── schema_reflection.py    # asyncpg information_schema → JSON graph
│           ├── schema_cache.py         # Redis cache (TTL 3600s)
│           ├── llm.py                  # OpenRouter client + embedding functions
│           ├── rag_ingestion.py        # Parse → chunk → embed → store pipeline
│           ├── rag_query.py            # BM25Index, hybrid search, RRF fusion
│           └── sandbox.py              # DockerSandboxService (container lifecycle)
│
├── frontend/
│   ├── package.json               # Next.js 16, React 19, Tailwind v4, etc.
│   ├── next.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── app/
│       │   ├── globals.css        # Dark-first CSS vars (oklch), shadcn/ui tokens
│       │   ├── layout.tsx          # RootLayout (Geist font, ThemeProvider, Toaster)
│       │   ├── page.tsx            # Redirect → /dashboard
│       │   ├── (dashboard)/
│       │   │   ├── layout.tsx      # DashboardLayout (Sidebar + Header + main)
│       │   │   ├── page.tsx        # Dashboard Home (stats + getting started checklist)
│       │   │   ├── connections/
│       │   │   │   ├── page.tsx    # Connection list (cards + add dialog)
│       │   │   │   └── [id]/page.tsx  # Schema explorer per connection
│       │   │   ├── schema/page.tsx     # Global schema view stub
│       │   │   ├── chat/
│       │   │   │   ├── page.tsx        # Agent Chat (messages + citations + animations)
│       │   │   │   └── [conversationId]/page.tsx  # Stub
│       │   │   ├── docs/
│       │   │   │   ├── page.tsx        # Document list + drag-drop upload
│       │   │   │   └── [docId]/page.tsx  # Stub
│       │   │   ├── events/
│       │   │   │   ├── page.tsx        # Event feed stub
│       │   │   │   └── [eventId]/page.tsx  # Stub
│       │   │   └── settings/
│       │   │       ├── page.tsx        # Theme toggle + model selector
│       │   │       ├── api/page.tsx    # API key CRUD
│       │   │       └── billing/page.tsx  # Billing stub (post-MVP)
│       │   └── api/[...path]/route.ts  # BFF proxy → FastAPI
│       ├── components/
│       │   ├── theme-provider.tsx  # Dark-first + localStorage + system preference
│       │   ├── sidebar.tsx         # Collapsible nav (7 items)
│       │   ├── header.tsx          # Theme toggle + notifications
│       │   └── ui/
│       │       ├── button.tsx      # 6 variants, 4 sizes (cva)
│       │       ├── card.tsx        # Card, Header, Title, Description, Content, Footer
│       │       ├── input.tsx       # Styled input
│       │       ├── badge.tsx       # 6 variants (default, secondary, destructive, etc.)
│       │       ├── dialog.tsx      # Modal with backdrop
│       │       └── skeleton.tsx    # Pulse loading
│       └── lib/
│           ├── utils.ts            # cn() helper
│           ├── api.ts              # ApiClient (connections, schema, query, rag, keys)
│           └── ws.ts               # WebSocket client (auto-reconnect)
│
└── docs/
    ├── CURRENT_STATE.md            # Living project tracker (what's built, what's next)
    ├── MASTER_GUIDE.md             # THIS FILE — comprehensive reference
    ├── PROJECT_PLAN.md             # Original implementation plan (12 weeks)
    ├── architecture/
    │   ├── system-overview.md      # Full system diagram + data flow traces
    │   ├── agent-topology.md       # LangGraph nodes, AgentState, transitions
    │   ├── security-model.md       # Triple-layer isolation, credential management
    │   └── data-flow.md            # READ vs WRITE lifecycle traces with error paths
    ├── modules/
    │   ├── schema-engine.md        # DB reflection, graph caching, security constraints
    │   ├── rag-engine.md           # Ingestion, hybrid search, citations, chunking config
    │   ├── sandbox-execution.md    # LangGraph agents, Docker/WASM sandbox, MCP client
    │   ├── event-gateway.md        # WebSockets, Pub/Sub, behavior rules, ARQ workers
    │   └── sdk.md                  # Client JS SDK spec (FluxGateway class)
    ├── frontend/
    │   ├── routes.md               # Next.js App Router routes + data fetching strategy
    │   └── ui-components.md        # Component tree + design tokens + UI patterns
    └── roadmap/
        ├── stage-1-core.md         # Weeks 1-4 detailed task list
        ├── stage-2-product.md      # Weeks 5-8 detailed task list
        ├── stage-3-scale.md        # Weeks 9-12 detailed task list
        └── future-goals.md         # Q2 2026 → 2027+ vision
```

---

## 11. API Reference

### Backend Endpoints

```
┌────────┬──────────────────────────────────────────┬──────────────────────┐
│ METHOD │ PATH                                      │ DESCRIPTION           │
├────────┼──────────────────────────────────────────┼──────────────────────┤
│ GET    │ /health                                   │ Health check          │
│ GET    │ /docs                                     │ Swagger UI            │
│ GET    │ /redoc                                    │ ReDoc                 │
├────────┼──────────────────────────────────────────┼──────────────────────┤
│ POST   │ /api/v1/auth/login                        │ OIDC login            │
│ GET    │ /api/v1/auth/callback                     │ OIDC callback         │
├────────┼──────────────────────────────────────────┼──────────────────────┤
│ POST   │ /api/v1/api-keys                          │ Create API key        │
│ GET    │ /api/v1/api-keys                          │ List API keys         │
│ DELETE │ /api/v1/api-keys/{key_id}                 │ Revoke API key        │
├────────┼──────────────────────────────────────────┼──────────────────────┤
│ POST   │ /api/v1/connections                       │ Create DB connection  │
│ GET    │ /api/v1/connections                       │ List connections      │
│ GET    │ /api/v1/connections/{id}                  │ Get connection        │
│ DELETE │ /api/v1/connections/{id}                  │ Delete connection     │
│ POST   │ /api/v1/connections/{id}/test             │ Test connection       │
├────────┼──────────────────────────────────────────┼──────────────────────┤
│ POST   │ /api/v1/schema/{connection_id}/reflect    │ Trigger reflection    │
│ GET    │ /api/v1/schema/{connection_id}            │ Get cached schema     │
├────────┼──────────────────────────────────────────┼──────────────────────┤
│ POST   │ /api/v1/query                             │ Schema-grounded query │
├────────┼──────────────────────────────────────────┼──────────────────────┤
│ POST   │ /api/v1/rag/documents                     │ Upload document       │
│ GET    │ /api/v1/rag/documents                     │ List documents        │
│ DELETE │ /api/v1/rag/documents/{id}                │ Delete document       │
│ POST   │ /api/v1/rag/search                        │ Hybrid search         │
│ POST   │ /api/v1/rag/ask                           │ RAG + LLM answer      │
│ GET    │ /api/v1/rag/citations/{chunk_id}          │ Get chunk detail      │
├────────┼──────────────────────────────────────────┼──────────────────────┤
│ POST   │ /api/v1/agent/query                       │ Full agent pipeline   │
│ GET    │ /api/v1/agent/queries/{id}                │ Get query result      │
│ GET    │ /api/v1/agent/queries                     │ List queries          │
├────────┼──────────────────────────────────────────┼──────────────────────┤
│ POST   │ /api/v1/sandbox/execute                   │ Run code in sandbox   │
└────────┴──────────────────────────────────────────┴──────────────────────┘

AUTH: All /api/* endpoints require X-API-Key header (API key auth)
      OR Authorization: Bearer <JWT> (OIDC auth)
```

### Frontend Routes

```
┌─────────────────────────────┬──────────────────────────────────────────┐
│ ROUTE                        │ COMPONENT                                │
├──────────────────────────────┼──────────────────────────────────────────┤
│ /                             │ Redirect → /dashboard                   │
│ /dashboard                    │ Dashboard Home (stats + checklist)       │
│ /dashboard/connections        │ Connection list + add dialog             │
│ /dashboard/connections/[id]   │ Schema explorer per connection           │
│ /dashboard/schema             │ Global schema view                       │
│ /dashboard/chat               │ Agent Chat interface                     │
│ /dashboard/chat/[id]          │ Existing conversation (stub)             │
│ /dashboard/docs               │ Document list + drag-drop upload         │
│ /dashboard/docs/[id]          │ Document detail (stub)                   │
│ /dashboard/events             │ Event feed (stub)                        │
│ /dashboard/events/[id]        │ Event detail (stub)                      │
│ /dashboard/settings           │ Theme toggle + default model             │
│ /dashboard/settings/api       │ API key management (create/copy/revoke)  │
│ /dashboard/settings/billing   │ Billing (post-MVP stub)                  │
│ /api/[...path]                │ BFF proxy → FastAPI backend              │
└──────────────────────────────┴──────────────────────────────────────────┘
```

---

## Appendix A: Key Design Principles

1. **Tenant Isolation First**: Every query, every vector search, every agent execution gated by hardcoded `tenant_id`. Triple-layer: DB RLS → ORM → API middleware. Never trust client-side tenant_id.

2. **Schema Grounding**: LLM never sees raw production data. Only metadata graph (information_schema) + vector chunks with citations. Coder node uses exact column names from graph — hallucinated column names are physically impossible.

3. **Sandbox Everything**: All generated code validated in ephemeral Docker container before touching production. Network disabled, memory capped, rootfs read-only, container destroyed after 30s. Attack surface: zero.

4. **Citation Everything**: Every RAG response has inline `[1]` markers traceable to exact source chunk (doc + page + score + excerpt). Kills hallucination dead. Frontend color-codes by confidence.

5. **Stateless Agents**: LangGraph state is request-scoped. No cross-request state leakage. No conversation history leaking between tenants. Agent memory is per-tenant, encrypted, isolated.

6. **Dark-First Design**: All UI components designed in dark mode (oklch color space). Light mode via CSS variable overrides. System preference detection + manual toggle. Target users are engineers working late.

7. **Defense in Depth**: Security at every layer. DB RLS → ORM listener → API middleware → Sandbox isolation → Audit logging. No single point of security failure.

---

## Appendix B: Test Status

```
┌─────────────┬────────────────────────────────────┐
│ TOOL        │ RESULT                              │
├─────────────┼────────────────────────────────────┤
│ ruff        │ All checks passed                   │
│ mypy        │ Clean (3 pre-existing non-blocking) │
│ pytest      │ 1 passed (health check)             │
│ tsc --noEmit│ 0 errors                            │
│ eslint      │ 0 errors, 0 warnings                │
└─────────────┴────────────────────────────────────┘
```

---

## Appendix C: Git Branches

```
main (1ad61e9)
  ↕
develop (856a4b2) ← Current: Stage 1-3 Week 9 complete
  ├── feature/langgraph-agent (merged, Week 7)
  └── (future feature branches)
```
