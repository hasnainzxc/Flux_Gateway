# Current State

> Full reference: **[MASTER_GUIDE.md](MASTER_GUIDE.md)** — architecture, decision rationale, security model, agent topology, dev→prod evolution, API reference
>
> **Date**: 2026-06-05
> **Honest Phase**: **Stage 2.5 — read-path MVP, write-path stubbed, pre-hardening**
> **NOT** "Stage 3 Complete" (prior label was aspirational; this doc was rewritten against verified code reality on 2026-06-05)

---

## TL;DR (Verified Reality)

- **Backend is ~75% real.** Read flow works end-to-end. Auth, tenant isolation, schema reflection, RAG, LLM, Docker sandbox, LangGraph agent (6 of 7 nodes) are genuinely implemented.
- **Write flow is FAKE at the last step.** The MCP Executor node is a stub — it returns a hardcoded `{"status":"simulated"}`. `mcp_client.py` does not exist. The core "agent writes back to your data" feature does not actually execute.
- **Frontend has real data wiring but NO auth/onboarding.** 10 pages call real APIs. There is no login page, no auth guard on `/dashboard`, no frontend OIDC flow, and a bootstrap paradox (you need an API key to mint an API key).
- **Quality infra is near-absent.** ~0% business-logic test coverage (only a health-check test), zero CI/CD, lint/type configured but unenforced. Stripe is a declared dependency that is never imported.

This document supersedes the previous self-reported "everything Done" status table.

---

## What is actually built vs claimed

### Backend — REAL (verified in code)

| Component | Status | Evidence |
|-----------|--------|----------|
| FastAPI gateway + middleware | ✅ Real | `main.py` registers routers + auth/tenant/rate-limit/CORS/logging MW |
| Triple-layer tenant isolation | ✅ Real | DB RLS → SQLAlchemy ORM listener → FastAPI dependency |
| Dual auth (API key + OIDC) | ✅ Real | API keys hashed; `core/oidc.py` full discovery → code-exchange → JWT (python-jose, httpx) |
| Schema reflection + Redis cache | ✅ Real | `asyncpg` `information_schema` → JSON graph → Redis TTL 1hr |
| LLM service | ✅ Real | `services/llm.py` AsyncOpenAI → OpenRouter; `llm_complete`/`llm_complete_json`/`generate_embeddings`; local `all-MiniLM-L6-v2` fallback (384d → 1536 zero-pad) |
| RAG ingestion + hybrid search | ✅ Real | PyMuPDF + tiktoken chunking; pgvector cosine + BM25 + RRF (k=60, vec 0.7 / bm25 0.3); citations |
| Docker sandbox | ✅ Real | `services/sandbox.py` `docker.from_env()`, network_disabled, mem 256m, cpu_quota 50000, read_only, tmpfs, no-new-privileges, cap_drop ALL; regex fallback if no Docker |
| LangGraph agent — 6 of 7 nodes | ✅ Real | `classify_intent`, `researcher`, `coder`, `reviewer`, `self_heal`, `format_response` all make real LLM/sandbox calls; `graph.py` real `StateGraph` with conditional edges + retry loop |

### Backend — STUBBED / MISSING (the gaps that matter)

| Component | Status | Evidence |
|-----------|--------|----------|
| **MCP Executor (write-back)** | ❌ **STUB** | `agents/nodes/mcp_executor.py` docstring says "placeholder for real Model Context Protocol execution (Stage 3)"; returns hardcoded `{"status":"simulated","message":"MCP execution placeholder — real execution will be wired in Stage 3 Week 11"}` |
| **`mcp_client.py`** | ❌ **MISSING** | No such file exists. The write-path has no transport. |
| **Stripe billing** | ❌ **NOT IMPLEMENTED** | `stripe` is in `pyproject.toml` deps but never imported anywhere. `usage_tracker.py` + `usage.py` are pure DB aggregation. `UsageRecord` has no `stripe_customer_id`/`plan`/`subscription_id`. `config.py` has no `STRIPE_SECRET_KEY`. |
| Low-severity TODOs | ⚠️ Minor | `main.py:115` CORS tighten; `auth.py:76` slug collision; `ws.py:67` pass; `behavior_rules.py:40` returns None |

> **Consequence:** "WRITE path: schema-grounded SQL → validation → MCP execution" is true up to validation. The final execution is simulated. An agent told to write data will report success without writing anything.

### Frontend — REAL DATA, BROKEN AUTH

| Area | Status | Evidence |
|------|--------|----------|
| API client | ✅ Real | `lib/api.ts` sends `X-API-Key` from `localStorage('flux_api_key')` (client) / `globalApiKey` (server). No hardcoded key; no header if missing. |
| BFF proxy | ✅ Real | `app/api/[...path]/route.ts` injects `process.env.BACKEND_API_KEY` (single shared key) |
| WebSocket | ✅ Real | `lib/ws.ts` `ws://NEXT_PUBLIC_WS_URL/ws/{tenantId}?token={apiKey}`, auto-reconnect 3s |
| 10 real-data pages | ✅ Real | dashboard, connections (hardcoded `db_type:postgresql` only), connections/[id], chat, docs, events (live WS), events/webhooks, settings/api, settings/billing (+behavior-rules CRUD). **Zero mock arrays anywhere.** |
| schema/page.tsx | ⚠️ Placeholder | static "select a connection" text; TODO aggregate schemas |
| settings/page.tsx | ⚠️ Partial | model selector disabled ("future update") |
| events/[eventId], docs/[docId], chat/[conversationId] | ⚠️ Stubs | each just `redirect()` |
| **Login / signup page** | ❌ **MISSING** | none exists |
| **Auth guard on `/dashboard`** | ❌ **MISSING** | dashboard is wide open |
| **Frontend OIDC flow** | ❌ **MISSING** | backend OIDC ready; frontend never calls it |
| **Onboarding (mint first key)** | ❌ **MISSING** | bootstrap paradox: need API key to mint API key; `tenant_id` hand-set in localStorage with no UI |

### Quality / Infra — NEAR ABSENT

| Area | Status | Evidence |
|------|--------|----------|
| Backend tests | ❌ ~0% biz logic | only `backend/tests/test_health.py` (1 fn, `GET /health`) + empty `__init__.py`; no `conftest`/`pytest.ini`; `pytest-cov` not installed (README's `pytest --cov=src` would fail) |
| Frontend tests | ❌ None | zero files/config/deps; `@playwright/test` is only a transitive lock entry, not in `package.json`; no vitest |
| CI/CD | ❌ None | no `.github/` directory; no pipeline |
| Pre-commit | ❌ None | — |
| Lint/type | ⚠️ Configured, unenforced | backend ruff (line 100, py312, E/F/I/N/W/UP/B/C4/SIM) + mypy strict; frontend eslint (next core-web-vitals+ts) + tsconfig strict — none run in CI |
| Docker | ⚠️ Dev-only | backend `Dockerfile` single-stage `python:3.12-slim`, installs `[dev]`, runs as **root**, no healthcheck; `docker-compose.yml` has PG+Redis healthchecks but backend has `--reload` + volume mount + no healthcheck; **no frontend service, no frontend Dockerfile, no prod override** |
| "Vitest + Playwright 80% coverage" | ❌ Fiction | it is a TODO item, not a built feature |

---

## Honest Status Table

| Component | Real? |
|-----------|-------|
| Monorepo scaffold | ✅ |
| Multi-tenant DB schema (10 tables, 3 migrations) | ✅ |
| Tenant isolation (triple-layer) | ✅ |
| Auth backend (API key + OIDC) | ✅ |
| Schema reflection + Redis cache | ✅ |
| LLM integration (OpenRouter + local fallback) | ✅ |
| RAG ingestion + hybrid search + citations | ✅ |
| Docker sandbox (validation) | ✅ |
| LangGraph agent — read path | ✅ |
| LangGraph agent — write path | ❌ **stops at simulated MCP node** |
| Frontend data pages (10) | ✅ |
| Frontend auth / onboarding | ❌ |
| MCP write-back execution | ❌ stub |
| Stripe billing | ❌ dep only, never wired |
| Backend tests | ❌ ~0% |
| Frontend tests | ❌ none |
| CI/CD | ❌ none |
| Prod Docker | ❌ dev-only |

---

## Three Blocking Gaps (must close to be a truthful product)

1. **MCP write-back is fake.** Implement a real `mcp_client.py` (JSON-RPC) and wire `mcp_executor` to actually execute validated writes. Until then the headline feature ("agent writes back to your data") is non-functional.
2. **No frontend auth / onboarding.** Add login page, dashboard auth guard, mint-first-key onboarding flow, and a tenant selector. Resolve the bootstrap paradox.
3. **~0% tests + 0 CI.** Stand up pytest-cov backend tests (auth/tenant/agent/sandbox), vitest + playwright smoke tests, and a `.github/workflows/ci.yml` (lint → type → test → build).

---

## Confirmed Decisions (unchanged)

| Decision | Choice |
|----------|--------|
| LLM provider | OpenRouter (model-flexible) |
| Embedding model | OpenRouter / fallback all-MiniLM-L6-v2 |
| Repo structure | Monorepo |
| Auth | OAuth/OIDC from day 1 (backend only so far) |
| DB scope | PostgreSQL-only (MVP) |

---

## Corrected Roadmap (sequenced by truth, not by hype)

The previous "Next Actions" jumped to marketplace / multi-modal / SSO. That is premature while the core write-path is stubbed and there are no tests. Correct order:

### P0 — Make it TRUE (in progress)
- **P0.1** Real MCP client + wire `mcp_executor` to real execution
- **P0.2** Frontend auth: login page + dashboard guard + onboarding (mint first key) + tenant selector
- **P0.3** Test foundation: pytest-cov backend (≥60% on auth/tenant/agent/sandbox) + vitest/playwright smoke + `.github/workflows/ci.yml`

### P1 — Make it SHIPPABLE
- Prod Docker (multi-stage, non-root, healthchecks, frontend Dockerfile, compose prod override)
- Real Stripe (subscription + webhook + plan-gating on existing usage meter)
- Finish the 3 stub pages + schema aggregation + model selector

### P2 — SCALE
- Connectors beyond Postgres (MySQL / Mongo / REST / GraphQL)
- K8s, read replicas, Redis cluster, RBAC

### P3 — PLATFORM
- Marketplace, multi-modal RAG, SSO/SAML/SOC2, SDKs/CLI, zero-code agent builder

---

## Test Status (verified)

- `ruff check src/` — configured (not run in CI)
- `pytest` — only `test_health.py` exists; `pytest --cov` fails (pytest-cov not installed)
- `next build` — compiles
- frontend tests — none exist
- DB migrations — 3 present (0001_initial, 0002_rag, 0003_event_gateway)

---

## Blockers

- **MCP write-back stub** blocks the core product promise.
- **No frontend auth** blocks any real user onboarding.
- **No tests / CI** blocks safe iteration on the above.
