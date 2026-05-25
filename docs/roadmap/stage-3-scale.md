# Stage 3: Scale & Integrations (Weeks 9-12)

> **Goal**: Ship sandbox execution, real-time event gateway, usage tracking, and billing prep.

---

## Week 9: Docker Sandbox Execution

### Day 1-3: Sandbox Service
- [ ] Docker SDK for Python integration
- [ ] Sandbox container configuration (no network, 256MB, tmpfs, 30s timeout)
- [ ] Create/destroy container lifecycle
- [ ] Code injection + execution in sandbox
- [ ] Capture stdout/stderr/output files
- [ ] Signed URL generation for output binary

### Day 4: Sandbox API
- [ ] `POST /api/v1/sandbox/execute` — run code in sandbox
- [ ] `GET /api/v1/sandbox/output/{execution_id}` — download output
- [ ] Container pool for warm starts (optional, perf optimization)

### Day 5: LangGraph Reviewer Integration
- [ ] Replace placeholder Reviewer with real Docker sandbox
- [ ] SQL validation: syntax check, table/column existence, no dangerous ops
- [ ] API payload validation: schema check, parameter types
- [ ] Self-healing loop integration (error from sandbox → fix → retry)
- [ ] End-to-end test: agent generates SQL → sandbox validates → passes/fails → heal → execute

### Week 9 Deliverables
- Ephemeral Docker sandbox fully operational
- Reviewer Node validates code before production execution
- Self-healing loop tested with real errors

---

## Week 10: Event Gateway (Part 1)

### Day 1-2: WebSocket Infrastructure
- [ ] FastAPI WebSocket endpoint setup
- [ ] WebSocket connection manager (per-tenant connection pool)
- [ ] Authentication on WebSocket connect (API key validation)
- [ ] Auto-reconnect with exponential backoff
- [ ] Heartbeat/keepalive

### Day 3-4: Redis Pub/Sub
- [ ] Redis Pub/Sub channel per tenant: `tenant:{id}:events`
- [ ] Event publish flow (webhook → validate → publish)
- [ ] ARQ/Celery worker setup (async task processing)
- [ ] Worker subscribes to tenant channel → picks up events → processes

### Day 5: WebSocket + Frontend
- [ ] Frontend WebSocket client (`lib/ws.ts`)
- [ ] Event feed component (real-time list with status badges)
- [ ] Progress bar during agent execution
- [ ] Event detail expander (payload, trace, result)

### Week 10 Deliverables
- WebSocket infrastructure working
- Real-time event streaming to dashboard
- Worker pool processing events

---

## Week 11: Event Gateway (Part 2) + MCP Client

### Day 1-2: Behavior Rules Engine
- [ ] Behavior rules CRUD API
- [ ] Rule evaluation engine (match event payload → trigger conditions)
- [ ] Rule configuration UI in dashboard (YAML/JSON editor)
- [ ] Priority-based execution ordering

### Day 3-4: Webhook Ingestion
- [ ] `POST /api/v1/webhooks/{tenant_id}/{hook_id}` endpoint
- [ ] Webhook registration API
- [ ] Webhook validation (API key + payload schema)
- [ ] Webhook in dashboard UI

### Day 5: MCP Client
- [ ] Implement MCP client (JSON-RPC 2.0 over HTTPS)
- [ ] Connection to client-side MCP Server
- [ ] Execute validated payloads on target systems
- [ ] End-to-end test: webhook → agent → sandbox → MCP → result → WebSocket

### Week 11 Deliverables
- Full event lifecycle: webhook → rules → worker → agent → sandbox → MCP → WebSocket stream
- Behavior rules configurable per tenant
- Webhook management in dashboard

---

## Week 12: Usage Tracking + Production Hardening

### Day 1-2: Telemetry & Usage
- [ ] Token usage tracking per tenant per model
- [ ] Compute time tracking (agent execution latency)
- [ ] Storage tracking (documents, chunks indexed)
- [ ] Usage API: `/api/v1/telemetry/usage`
- [ ] Usage charts in dashboard (token usage over time, cost estimation)

### Day 3-4: Billing Prep
- [ ] Stripe SDK integration
- [ ] Usage-based pricing tier definitions
- [ ] Invoice generation from telemetry data
- [ ] Internal admin dashboard

### Day 5: Stage 3 Review
- [ ] Stage 3 end-to-end integration test
- [ ] Performance + security audit
- [ ] Documentation finalization
- [ ] Production deployment checklist

### Stage 3 Milestone
**Working**: End-to-end platform. Webhook → autonomous agent loop → sandbox validation → MCP execution → live dashboard streaming. Usage tracking per tenant. Billing integration ready.

---

## Stage 3 File Checklist

```
backend/
├── src/
│   ├── services/
│   │   ├── sandbox.py             ✅
│   │   └── event_gateway.py       ✅
│   ├── workers/
│   │   ├── tasks.py               ✅
│   │   └── websocket_manager.py   ✅
│   ├── agents/
│   │   └── mcp_client.py          ✅
│   ├── api/v1/
│   │   ├── events.py              ✅
│   │   ├── telemetry.py           ✅
│   │   └── admin.py               ✅

frontend/
├── src/
│   ├── app/(dashboard)/
│   │   ├── events/page.tsx        ✅
│   │   └── settings/              ✅
│   ├── components/
│   │   └── events/                ✅
│   └── lib/
│       └── ws.ts                  ✅
```
