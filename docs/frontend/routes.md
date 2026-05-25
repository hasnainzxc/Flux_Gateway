# Frontend — Routes & Data Fetching

> Next.js 16 App Router route structure + data fetching strategy.

## Route Map

```
app/
├── layout.tsx                    RootLayout (fonts, theme, providers)
├── page.tsx                      Landing page (post-MVP: marketing site)
│
├── (auth)/                       Auth group (post-MVP: login/signup)
│   ├── login/page.tsx
│   └── signup/page.tsx
│
├── (dashboard)/                  Dashboard group (authenticated)
│   ├── layout.tsx                DashboardLayout (sidebar + header)
│   ├── page.tsx                  Dashboard Home
│   │
│   ├── connections/
│   │   ├── page.tsx              Connection list
│   │   └── [id]/
│   │       └── page.tsx          Single connection detail + schema explorer
│   │
│   ├── schema/
│   │   └── page.tsx              Schema Explorer (global view)
│   │
│   ├── chat/
│   │   ├── page.tsx              Agent Chat (new conversation)
│   │   └── [conversationId]/
│   │       └── page.tsx          Existing conversation
│   │
│   ├── docs/
│   │   ├── page.tsx              Document list
│   │   └── [docId]/
│   │       └── page.tsx          Document detail + chunk viewer
│   │
│   ├── events/
│   │   ├── page.tsx              Event feed + webhook manager
│   │   └── [eventId]/
│   │       └── page.tsx          Single event detail
│   │
│   └── settings/
│       ├── page.tsx              General settings
│       ├── api/page.tsx          API key management
│       └── billing/page.tsx      Usage & billing (post-MVP)
│
└── api/                          Next.js API routes (proxy to FastAPI)
    └── [...path]/route.ts        BFF: forwards requests to backend
```

## Data Fetching Strategy

### Server Components (default)
- Dashboard home stats: `fetch()` from FastAPI, revalidate every 60s
- Connection list: server fetch at request time
- Schema explorer: server fetch, cache in Redis
- Document list: server fetch

### Client Components (for interactivity)
- Agent Chat: `useState` + `useEffect` for messages, WebSocket for streaming
- Event feed: WebSocket connection via `useWebSocket` hook
- Forms: React Hook Form + Zod validation
- Token counter: polling or WebSocket

### Data Flow
```
Next.js Server Component
  → fetch("http://backend:8000/api/v1/...", { headers: { "X-API-Key": ... } })
  → FastAPI Backend
  → PostgreSQL / Redis
  → Response
  → Rendered HTML (RSC)

Next.js Client Component
  → tRPC or custom fetch hook
  → Next.js API Route (BFF)
  → FastAPI Backend
  → Response
  → React state update + re-render
```

### WebSocket Flow
```
Client Component mounts
  → new WebSocket("ws://backend:8000/ws/{tenantId}")
  → Backend WebSocketManager registers connection
  → Events pushed from Redis Pub/Sub → WebSocket → Client
  → Component re-renders with new event data
```

## API Client

```typescript
// frontend/src/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private apiKey: string;
  
  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }
  
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
        ...options?.headers,
      },
    });
    
    if (!res.ok) {
      throw new ApiError(res.status, await res.json());
    }
    
    return res.json();
  }
  
  // Connections
  getConnections() { return this.request("/api/v1/connections"); }
  createConnection(data) { return this.request("/api/v1/connections", { method: "POST", body: JSON.stringify(data) }); }
  
  // Schema
  getSchema(connectionId) { return this.request(`/api/v1/connections/${connectionId}/schema`); }
  reflectSchema(connectionId) { return this.request(`/api/v1/connections/${connectionId}/reflect`, { method: "POST" }); }
  
  // Agent
  query(prompt, options?) { return this.request("/api/v1/agent/query", { method: "POST", body: JSON.stringify({ prompt, ...options }) }); }
  
  // RAG
  uploadDocument(file: File) { /* FormData upload */ }
  searchDocuments(query) { return this.request("/api/v1/rag/search", { method: "POST", body: JSON.stringify({ query }) }); }
  
  // Events
  getEvents() { return this.request("/api/v1/events"); }
  createWebhook(data) { return this.request("/api/v1/webhooks", { method: "POST", body: JSON.stringify(data) }); }
}
```

## Loading & Error States

- Every page: `loading.tsx` (skeleton)
- Every page: `error.tsx` (error boundary with retry)
- Every page: `not-found.tsx` (404)
- Data fetching: React Suspense boundaries
- Mutations: optimistic updates with rollback (React Query)
