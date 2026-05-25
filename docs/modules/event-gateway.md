# Real-time Event Gateway

> **Module**: `backend/src/services/event_gateway.py`, `backend/src/workers/`  
> **API**: `backend/src/api/v1/events.py`, WebSocket routes

## Purpose

Background automation gateway. Client systems pipe webhooks (new signup, inventory alert, support ticket) into automated LangGraph agent loops. Real-time status streams to dashboard via WebSocket.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    External Client Systems                        │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Odoo ERP │  │ HubSpot  │  │ Custom   │  │ Stripe   │        │
│  │ Webhook  │  │ Webhook  │  │ App Hook │  │ Webhook  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │              │              │              │              │
│       └──────────────┴──────────────┴──────────────┘              │
│                              │                                    │
│              POST /api/v1/webhooks/{tenant_id}/{hook_id}          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI Event Gateway                          │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  1. Validate API Key + tenant_id                        │     │
│  │  2. Parse event payload                                 │     │
│  │  3. Lookup Agentic Behavior Rules Matrix                │     │
│  │  4. Publish to Redis Pub/Sub channel                    │     │
│  │     channel: tenant:{tenant_id}:events                  │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  WebSocket Manager                                       │     │
│  │  /ws/{tenant_id} — Dashboard connects here               │     │
│  │  - Real-time status push per event                       │     │
│  │  - Connection pool by tenant                             │     │
│  │  - Auto-reconnect with event log replay                  │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Redis Pub/Sub                                   │
│                                                                   │
│  channel: tenant:{id}:events                                      │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  Message: {                                              │     │
│  │    "event_id": "evt_123",                                │     │
│  │    "hook_id": "hook_456",                                │     │
│  │    "payload": {...},                                     │     │
│  │    "matched_rules": ["low_inventory_alert"],             │     │
│  │    "priority": "high"                                    │     │
│  │  }                                                       │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Async Worker Pool (ARQ)                         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  Worker subscribes to tenant channel                     │     │
│  │  Picks up event → evaluates rules → dispatches agent     │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  Agent Loop:                                             │     │
│  │  1. Parse event context                                 │     │
│  │  2. Fetch relevant RAG docs (tenant-filtered)           │     │
│  │  3. Execute LangGraph agent circuit                      │     │
│  │  4. Stream status to WebSocket                           │     │
│  │  5. Store result in event_log table                      │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  WebSocket Status Push:                                  │     │
│  │  {                                                       │     │
│  │    "event_id": "evt_123",                                │     │
│  │    "status": "processing" | "completed" | "failed",      │     │
│  │    "step": "classifying_intent",                         │     │
│  │    "progress": 0.6,                                      │     │
│  │    "result": null | {...}                                │     │
│  │  }                                                       │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

## Agentic Behavior Rules Matrix

```yaml
# Per-tenant configuration
# Stored in DB: behavior_rules table
# tenant_id: "org_acme_corp"

rules:
  - name: "low_inventory_restock"
    description: "When inventory drops below threshold, trigger restock agent"
    trigger:
      event_type: "inventory_alert"
      conditions:
        - field: "payload.current_stock"
          operator: "lt"
          value: "payload.reorder_point"
    action:
      agent_type: "inventory_restock"
      agent_config:
        model: "gpt-4o"
        max_retries: 2
    priority: "high"
    
  - name: "new_support_ticket_triage"
    description: "Auto-triage incoming Zendesk tickets"
    trigger:
      event_type: "support_ticket.created"
    action:
      agent_type: "support_triage"
      agent_config:
        model: "gpt-4o-mini"  # cheap model for triage
        max_retries: 1
    priority: "medium"
    
  - name: "daily_report_generation"
    description: "Generate end-of-day sales report"
    trigger:
      event_type: "scheduled"
      schedule: "0 18 * * 1-5"  # 6 PM weekdays
    action:
      agent_type: "report_generator"
      agent_config:
        model: "gpt-4o"
        output_format: "pdf"
    priority: "low"
    
  - name: "fraud_detection_alert"
    description: "Flag suspicious transactions"
    trigger:
      event_type: "transaction.created"
      conditions:
        - field: "payload.amount"
          operator: "gt"
          value: 10000
    action:
      agent_type: "fraud_review"
      agent_config:
        model: "gpt-4o"
        require_human_approval: true  # high-risk: needs approval
    priority: "critical"
```

## WebSocket Manager

```python
from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

class WebSocketManager:
    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = {}  # tenant_id → websockets
    
    async def connect(self, tenant_id: str, websocket: WebSocket):
        await websocket.accept()
        if tenant_id not in self.connections:
            self.connections[tenant_id] = set()
        self.connections[tenant_id].add(websocket)
    
    async def disconnect(self, tenant_id: str, websocket: WebSocket):
        self.connections[tenant_id].discard(websocket)
    
    async def broadcast(self, tenant_id: str, message: dict):
        """Push to all connected dashboards for this tenant."""
        if tenant_id in self.connections:
            dead = set()
            for ws in self.connections[tenant_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.add(ws)
            self.connections[tenant_id] -= dead
    
    async def send_event_update(
        self, 
        tenant_id: str, 
        event_id: str, 
        status: str, 
        step: str = None,
        progress: float = None,
    ):
        await self.broadcast(tenant_id, {
            "type": "event_update",
            "event_id": event_id,
            "status": status,
            "step": step,
            "progress": progress,
            "timestamp": datetime.utcnow().isoformat(),
        })
```

## Webhook Ingestion Flow

```python
@router.post("/webhooks/{tenant_id}/{hook_id}")
async def ingest_webhook(
    tenant_id: str,
    hook_id: str,
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    # 1. Validate API key (from header)
    api_key = request.headers.get("X-API-Key")
    if not await validate_api_key(api_key, tenant_id):
        raise HTTPException(status_code=401)
    
    # 2. Load behavior rules
    rules = await get_behavior_rules(tenant_id, hook_id, db)
    
    # 3. Evaluate rules against payload
    matched = evaluate_rules(rules, payload)
    
    if not matched:
        return {"status": "no_rules_matched"}
    
    # 4. Create event record
    event = Event(
        tenant_id=tenant_id,
        hook_id=hook_id,
        payload=payload,
        matched_rules=[r.name for r in matched],
        status="queued",
    )
    db.add(event)
    await db.commit()
    
    # 5. Publish to Redis
    await redis.publish(
        f"tenant:{tenant_id}:events",
        json.dumps({
            "event_id": event.id,
            "hook_id": hook_id,
            "payload": payload,
            "matched_rules": [r.name for r in matched],
            "priority": max(r.priority for r in matched),
        }),
    )
    
    # 6. Respond immediately (async processing)
    return {
        "event_id": event.id,
        "status": "queued",
        "matched_rules": len(matched),
    }
```

## Event Log Schema

```sql
CREATE TABLE event_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    hook_id UUID NOT NULL REFERENCES webhooks(id),
    event_type VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    matched_rules TEXT[] DEFAULT '{}',
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    -- status: queued → processing → completed | failed
    agent_run_id UUID REFERENCES agent_runs(id),
    result JSONB,
    error TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Hard tenant filter index
    CONSTRAINT fk_event_log_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE INDEX idx_event_log_tenant_status ON event_log(tenant_id, status);
CREATE INDEX idx_event_log_created ON event_log(tenant_id, created_at DESC);
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/webhooks` | Register new webhook endpoint |
| GET | `/api/v1/webhooks` | List tenant's webhooks |
| DELETE | `/api/v1/webhooks/{id}` | Remove webhook |
| POST | `/api/v1/webhooks/{tenant_id}/{hook_id}` | External systems POST events here |
| GET | `/api/v1/events` | List tenant's event history |
| GET | `/api/v1/events/{id}` | Get event details + result |
| WS | `/ws/{tenant_id}` | Live event stream for dashboard |
| POST | `/api/v1/rules` | Create behavior rule |
| PUT | `/api/v1/rules/{id}` | Update behavior rule |
| DELETE | `/api/v1/rules/{id}` | Delete behavior rule |

## Future Enhancements

- Event replay (re-process historical events)
- Dead letter queue for failed events
- Event schema validation (JSON Schema per hook)
- Rate limiting per webhook (prevent abuse)
- Webhook signing (HMAC validation)
- Scheduled events (cron-based triggers)
- Event-driven agent chaining (output of one agent → input to another)
