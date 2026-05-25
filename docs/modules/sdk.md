# SDK — Client JavaScript SDK Spec

> Lightweight SDK businesses install in their application frontend to enable Flux Gateway.  
> **Package**: `@flux-gateway/sdk`  
> **Module**: `frontend/src/lib/sdk/` (built separately) or standalone npm package

## Purpose

Minimal JS snippet that captures user context and proxies agent requests to Flux Gateway backend. Zero-config for basic use, extensible for advanced.

## Installation

```bash
npm install @flux-gateway/sdk
```

```html
<!-- Or via CDN for quick setup -->
<script src="https://cdn.fluxgateway.io/sdk/v1/flux-gateway.min.js"></script>
```

## Basic Usage

```javascript
import { FluxGateway } from "@flux-gateway/sdk";

const flux = new FluxGateway({
  apiKey: "fg_live_abc123...",       // Your tenant API key
  endpoint: "https://api.fluxgateway.io",  // SaaS endpoint
  tenantId: "org_retail_zone_4",     // Your org identifier
});

// Natural language query
const result = await flux.ask("Show me all unpaid invoices from Q2");
// → { answer: "...", citations: [...], tokens_used: 1450 }

// Execute action
const result = await flux.execute("Update inventory SKU-123 to 500 units");
// → { answer: "...", execution_result: {...} }

// Upload document for RAG
await flux.uploadDocument(fileInput.files[0]);
// → { document_id: "doc_xyz", chunks_created: 42 }

// Search documents
const docs = await flux.search("return policy for damaged items");
// → { results: [...], citations: [...] }
```

## Advanced: With Session Context

```javascript
const flux = new FluxGateway({
  apiKey: "fg_live_abc123...",
  endpoint: "https://api.fluxgateway.io",
  tenantId: "org_retail_zone_4",
});

// Set session context (user role, current page, etc.)
flux.setContext({
  userRole: "finance_manager",
  currentPage: "/reports/payables",
  activeFilters: { status: "unpaid", quarter: "Q2" },
});

// Context automatically attached to every request
const result = await flux.ask("Which vendors have the most overdue invoices?");
// Context helps agent understand the user's perspective
```

## Real-time Events

```javascript
// Listen for webhook-triggered event updates
flux.onEvent("inventory_alert", (event) => {
  console.log("Inventory alert:", event.payload);
  // Update UI
});

// Subscribe to specific event types
flux.subscribe(["inventory_alert", "order_shipped"], (event) => {
  showNotification(event);
});

// Get live status for a specific event
flux.onEventUpdate("evt_789", (status) => {
  console.log(`Event ${status.event_id}: ${status.step} (${status.progress * 100}%)`);
});
```

## WebSocket Connection

```javascript
// Auto-connects WebSocket for real-time updates
const flux = new FluxGateway({
  apiKey: "...",
  endpoint: "https://api.fluxgateway.io",
  tenantId: "org_retail_zone_4",
  websocket: true,  // Enable WebSocket
});

// Connection state
flux.onConnectionChange((state) => {
  // "connected", "disconnected", "reconnecting"
});
```

## React Hook

```typescript
import { createFluxHook } from "@flux-gateway/sdk/react";

const useFlux = createFluxHook({
  apiKey: process.env.NEXT_PUBLIC_FLUX_API_KEY!,
  endpoint: process.env.NEXT_PUBLIC_FLUX_ENDPOINT!,
  tenantId: "org_retail_zone_4",
});

function MyComponent() {
  const { ask, execute, loading, error } = useFlux();
  
  const handleQuery = async () => {
    const result = await ask("Show Q2 revenue by product category");
    // Handle result
  };
  
  return (
    <div>
      <button onClick={handleQuery} disabled={loading}>
        {loading ? "Thinking..." : "Ask Agent"}
      </button>
      {error && <div className="error">{error.message}</div>}
    </div>
  );
}
```

## SDK Architecture

```
┌──────────────────────────────────────────────────────┐
│                  @flux-gateway/sdk                     │
│                                                       │
│  ┌────────────────────────────────────────────────┐  │
│  │ FluxGateway (main class)                       │  │
│  │  ├── ask(prompt, options?) → QueryResult       │  │
│  │  ├── execute(prompt, options?) → ExecuteResult │  │
│  │  ├── uploadDocument(file) → Document           │  │
│  │  ├── search(query) → SearchResult             │  │
│  │  ├── setContext(ctx) → void                    │  │
│  │  ├── onEvent(type, handler) → unsubscribe     │  │
│  │  └── subscribe(types, handler) → unsubscribe  │  │
│  └────────────────────────────────────────────────┘  │
│                                                       │
│  ┌────────────────────────────────────────────────┐  │
│  │ HttpTransport                                  │  │
│  │  ├── fetch() with API key + tenant headers     │  │
│  │  ├── Retry logic (3 retries, exponential)      │  │
│  │  └── Error handling + typed errors             │  │
│  └────────────────────────────────────────────────┘  │
│                                                       │
│  ┌────────────────────────────────────────────────┐  │
│  │ WebSocketTransport                             │  │
│  │  ├── Auto-connect with reconnection            │  │
│  │  ├── Event subscription management             │  │
│  │  └── Heartbeat / keepalive                     │  │
│  └────────────────────────────────────────────────┘  │
│                                                       │
│  ┌────────────────────────────────────────────────┐  │
│  │ ContextManager                                 │  │
│  │  ├── Session context (user role, page, etc.)   │  │
│  │  ├── Auto-attached to every request header     │  │
│  │  └── Persistent across page navigations        │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## API Payload Format

```typescript
// Every request to FastAPI backend
interface FluxRequest {
  prompt: string;
  context?: {
    userRole?: string;
    sessionId?: string;
    currentPage?: string;
    activeFilters?: Record<string, any>;
  };
  options?: {
    model?: "gpt-4o" | "gpt-4o-mini";
    maxRetries?: number;
    timeout?: number;
  };
}

// Query response
interface QueryResult {
  answer: string;
  citations: Citation[];
  tokensUsed: number;
  latencyMs: number;
  intent: "read" | "write";
  queryId: string;
}

interface Citation {
  id: string;
  documentName: string;
  page: number;
  score: number;
  excerpt: string;
}

// Execute response
interface ExecuteResult {
  answer: string;
  executionResult: {
    rowsAffected?: number;
    status: "success" | "failed";
    data?: any;
  };
  reviewPassed: boolean;
  retryCount: number;
  tokensUsed: number;
  latencyMs: number;
}
```

## Future SDK Features (Post-MVP)

- File upload with progress tracking
- Offline queue (queue actions when offline, replay on reconnect)
- Audit log streaming (all agent interactions)
- Multi-tenant SDK (switch between orgs in same app)
- Custom tool registration (define tools the agent can call)
- Webhook management API (register/unregister webhooks from SDK)
