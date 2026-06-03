<div align="center">

# Flux Gateway — Frontend

### Next.js 16 Dashboard for the Data-to-Agent Platform

[Getting Started](#getting-started) · [Architecture](#architecture) · [Pages](#pages) · [Components](#components)

---

![Next.js](https://img.shields.io/badge/next.js-16.2.6-black)
![React](https://img.shields.io/badge/react-19.2.4-blue)
![Tailwind](https://img.shields.io/badge/tailwind-v4-38bdf8)
![TypeScript](https://img.shields.io/badge/typescript-5.x-3178c6)

</div>

---

## Getting Started

```bash
# Install dependencies
npm install

# Start dev server
npm run dev          # http://localhost:3000

# Production build
npm run build
npm run start

# Linting & type checking
npm run lint         # ESLint
npx tsc --noEmit     # TypeScript check
```

### Environment Variables

Create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## Architecture

```
frontend/src/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout (Providers, fonts, theme)
│   ├── page.tsx                  # Landing page → redirect to /dashboard
│   ├── api/[...path]/route.ts    # API proxy to backend
│   └── dashboard/
│       ├── layout.tsx            # Dashboard shell (Sidebar + Header)
│       ├── page.tsx              # Home — live stats, usage metrics
│       ├── connections/          # DB connection manager
│       ├── schema/               # Schema explorer
│       ├── chat/                 # Agent chat interface
│       ├── docs/                 # RAG document manager
│       ├── events/               # Real-time event feed + webhooks
│       └── settings/             # API keys, billing, usage
│
├── components/
│   ├── ui/                       # 29 shadcn/ui primitives (Radix-based)
│   ├── providers.tsx             # QueryClient + Toaster + ErrorBoundary + Tooltip
│   ├── error-boundary.tsx        # React error boundary
│   ├── sidebar.tsx               # Collapsible navigation (8 items)
│   └── header.tsx                # Top bar
│
└── lib/
    ├── api.ts                    # Typed API client (all endpoints)
    ├── ws.ts                     # WebSocket client (auto-reconnect, pub/sub)
    ├── toast.ts                  # Sonner toast wrapper
    └── utils.ts                  # cn() class merge helper
```

---

## Tech Stack

| Category | Technology |
|----------|-----------|
| **Framework** | Next.js 16.2.6 (App Router) |
| **UI Library** | React 19.2.4 |
| **Styling** | Tailwind CSS v4, CSS variables for theming |
| **Components** | shadcn/ui (29 Radix-based primitives) |
| **Animations** | Motion (Framer Motion successor) |
| **Data Fetching** | @tanstack/react-query v5 |
| **Forms** | react-hook-form v7 + zod v4 validation |
| **Icons** | lucide-react |
| **Toasts** | sonner v2 |
| **Theme** | next-themes (dark/light) |
| **Command Palette** | cmdk |
| **File Upload** | react-dropzone |
| **Type Safety** | TypeScript 5.x (strict) |

---

## Pages

| Route | Description |
|-------|-------------|
| `/dashboard` | Home — live stats (connections, docs, events, tokens), usage summary |
| `/dashboard/connections` | DB connection CRUD with test connectivity |
| `/dashboard/connections/[id]` | Connection detail view |
| `/dashboard/schema` | Schema explorer — tables, columns, relationships |
| `/dashboard/chat` | Agent chat — NL queries with SQL citations |
| `/dashboard/chat/[conversationId]` | Chat conversation thread |
| `/dashboard/docs` | RAG document manager — upload PDF/MD/TXT |
| `/dashboard/docs/[docId]` | Document detail + chunk viewer |
| `/dashboard/events` | Real-time event feed via WebSocket |
| `/dashboard/events/[eventId]` | Event detail + retry |
| `/dashboard/events/webhooks` | Webhook config CRUD + secret management |
| `/dashboard/settings` | General settings |
| `/dashboard/settings/api` | API key management |
| `/dashboard/settings/billing` | Usage dashboard + behavior rules CRUD |

---

## Components

### UI Primitives (`components/ui/`)

29 shadcn/ui components built on Radix UI:

`accordion` · `alert-dialog` · `avatar` · `badge` · `button` · `card` · `checkbox` · `command` · `dialog` · `dropdown-menu` · `hover-card` · `input` · `label` · `navigation-menu` · `popover` · `progress` · `radio-group` · `scroll-area` · `select` · `separator` · `sheet` · `skeleton` · `slider` · `switch` · `table` · `tabs` · `textarea` · `toggle` · `tooltip`

### Layout

| Component | File | Description |
|-----------|------|-------------|
| `Providers` | `components/providers.tsx` | QueryClient, Toaster, ErrorBoundary, TooltipProvider |
| `ErrorBoundary` | `components/error-boundary.tsx` | Catches render crashes with fallback UI |
| `Sidebar` | `components/sidebar.tsx` | Collapsible nav, 8 items, active state, version badge |
| `Header` | `components/header.tsx` | Top bar with theme toggle |
| `ThemeProvider` | `components/theme-provider.tsx` | next-themes wrapper (dark/light/system) |

---

## API Client

`lib/api.ts` — typed client covering all backend endpoints:

```typescript
import { api } from "@/lib/api"

// Connections
api.getConnections()
api.createConnection({ name, host, port, database, username, password })
api.testConnection(id)

// Agent
api.query(prompt, { connection_id })

// RAG
api.uploadDocument(file)
api.searchDocuments(query, topK)
api.askRag(query, topK)

// Events
api.getEvents({ status, limit, offset })
api.retryEvent(id)

// Webhooks
api.createWebhook({ name, event_types, secret })

// Usage
api.getUsageSummary()
api.getUsageHistory(months)
```

## WebSocket Client

`lib/ws.ts` — auto-reconnecting WebSocket with event pub/sub:

```typescript
import { wsClient } from "@/lib/ws"

wsClient.connect(tenantId)

const unsub = wsClient.on("event.created", (data) => {
  console.log("New event:", data)
})

wsClient.disconnect()
```

---

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server with HMR |
| `npm run build` | Production build |
| `npm run start` | Start production server |
| `npm run lint` | ESLint check |
| `npx tsc --noEmit` | TypeScript type check |

---

## License

Proprietary. Part of the Flux Gateway platform.
