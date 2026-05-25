# Stage 1: Core Infrastructure (Weeks 1-4)

> **Goal**: Build secure, un-breachable core pipeline where databases connect and schemas are read safely.

---

## Week 1: Project Foundation

### Day 1-2: Environment Setup
- [ ] Initialize monorepo structure (backend/ + frontend/ + docs/)
- [ ] Create `docker-compose.yml` with PostgreSQL 16 + pgvector + Redis
- [ ] Initialize Python project with `pyproject.toml` (uv or poetry)
- [ ] Configure ruff, mypy, pytest
- [ ] Initialize Next.js 16 project with `create-next-app`
- [ ] Configure Tailwind v4, shadcn/ui, Geist font
- [ ] Set up `.env` template with all required vars
- [ ] Create `.gitignore`

### Day 3-4: Database Schema Design
- [ ] Design multi-tenant PostgreSQL schema:
  - `tenants` table
  - `api_keys` table (hashed)
  - `connections` table
  - `schema_cache` table
  - `credentials` table (encrypted values)
- [ ] Write Alembic initial migration
- [ ] Create SQLAlchemy async models
- [ ] Set up session factory with tenant context

### Day 5: Tenant Isolation Layer
- [ ] Implement ORM event listener for `WHERE tenant_id` injection
- [ ] Implement context variable for current tenant
- [ ] Create FastAPI dependency for tenant extraction from API key
- [ ] Write tests: verify Tenant A cannot see Tenant B data

### Week 1 Deliverables
- Docker dev environment running
- Database with multi-tenant schema
- Tenant isolation enforced at DB + ORM + API layers
- Basic test suite passing

---

## Week 2: FastAPI Core + Auth

### Day 1-2: FastAPI App Skeleton
- [ ] Create FastAPI app with health check endpoint
- [ ] Set up CORS middleware
- [ ] Set up logging (structlog)
- [ ] Create error handling (custom exceptions + handlers)
- [ ] Set up OpenAPI docs

### Day 3-4: Authentication
- [ ] API key generation (UUID-based, hashed storage)
- [ ] API key validation middleware
- [ ] Rate limiting (Redis token bucket)
- [ ] API endpoints: create key, list keys, revoke key
- [ ] Test auth flow end-to-end

### Day 5: Connection Manager (Basic)
- [ ] Connection model + CRUD endpoints
- [ ] Encrypt connection string before storage
- [ ] Connection test endpoint (ping DB)
- [ ] List/delete connections (tenant-scoped)

### Week 2 Deliverables
- FastAPI running with auth
- API key management working
- Connection CRUD endpoints
- All endpoints tenant-scoped

---

## Week 3: Schema Reflection Engine

### Day 1-3: Schema Reflection Service
- [ ] Implement PostgreSQL `information_schema` queries
- [ ] Build JSON metadata graph from reflection results
- [ ] Cache graph in Redis (per tenant, per connection)
- [ ] Implement cache invalidation (manual refresh, TTL)
- [ ] Add version tracking to schema snapshots

### Day 4: Reflection API
- [ ] `POST /api/v1/connections/{id}/reflect` endpoint
- [ ] `GET /api/v1/connections/{id}/schema` endpoint
- [ ] Asynchronous reflection (background task for large schemas)
- [ ] Progress tracking during reflection

### Day 5: Testing & Polish
- [ ] Test with sample databases (various schemas)
- [ ] Edge cases: empty DB, many tables, complex FKs
- [ ] Performance: reflection time for 100+ table DB
- [ ] Error handling: invalid connection, timeout, permission denied

### Week 3 Deliverables
- Schema reflection fully functional
- JSON metadata graph generated correctly
- Cached in Redis with invalidation
- API endpoints tested

---

## Week 4: Schema Engine Integration + Stage 1 Review

### Day 1-2: LLM Integration Prep
- [ ] Set up LLM provider client (OpenAI SDK)
- [ ] Create prompt templates for schema-grounded queries
- [ ] Implement basic "ask about schema" endpoint (read-only, no RAG yet)
- [ ] Test: "What tables are in my database?" → agent answers from schema graph

### Day 3-4: Security Hardening
- [ ] Audit all endpoints for tenant isolation
- [ ] Add security headers
- [ ] Set up audit logging for security events
- [ ] Penetration test: attempt cross-tenant access
- [ ] Document security model

### Day 5: Stage 1 Review
- [ ] End-to-end integration test: connect DB → reflect schema → ask question
- [ ] Performance benchmarks
- [ ] Code review + refactor
- [ ] Update documentation

### Stage 1 Milestone
**Working**: Can connect to any PostgreSQL DB, reflect schema safely, cache metadata graph, ask natural language questions about schema structure — all with tenant isolation.

---

## Stage 1 File Checklist

```
backend/
├── src/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── health.py          ✅
│   │   │   ├── auth.py            ✅
│   │   │   ├── connections.py     ✅
│   │   │   └── schema.py          ✅
│   │   └── deps.py                ✅
│   ├── core/
│   │   ├── config.py              ✅
│   │   ├── security.py            ✅
│   │   └── tenant.py              ✅
│   ├── db/
│   │   ├── session.py             ✅
│   │   ├── models/                ✅
│   │   └── migrations/            ✅
│   └── services/
│       ├── schema_reflection.py   ✅
│       └── connection_manager.py  ✅
├── tests/
│   ├── test_auth.py               ✅
│   ├── test_tenant_isolation.py   ✅
│   └── test_schema_reflection.py  ✅
├── pyproject.toml                 ✅
└── Dockerfile                     ✅

frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx             ✅
│   │   └── (dashboard)/
│   │       ├── layout.tsx         ✅
│   │       └── page.tsx           ✅  (basic dashboard shell)
│   └── lib/
│       └── api.ts                 ✅
├── package.json                   ✅
└── Dockerfile                     ✅

docker-compose.yml                 ✅
```
