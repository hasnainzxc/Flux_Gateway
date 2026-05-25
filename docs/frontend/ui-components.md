# Frontend — UI Components

> Next.js 16 + Tailwind v4 + shadcn/ui + Magic UI + Motion.dev + Geist font + dark-first design

## Design Tokens

```
Colors (dark-first CSS variables):
  --background: 0 0% 3.9%         (near-black)
  --foreground: 0 0% 98%          (near-white)
  --card: 0 0% 6%
  --primary: 217 91% 60%          (blue accent)
  --muted: 0 0% 15%
  --border: 0 0% 14.9%

Font: Geist Sans (body) + Geist Mono (code) via next/font
Radius: 0.5rem (shadcn default)
Animation: Motion.dev (page transitions), Magic UI (components)
```

## Component Tree

```
RootLayout
  GeistFontLoader
  ThemeProvider (dark-first)
  Toaster (sonner)
  WebSocketProvider

DashboardLayout
  Sidebar
    SidebarHeader (logo + tenant name)
    SidebarNav
      NavItem: Dashboard, Connections, Schema, Chat, Docs, Events, Settings
    SidebarFooter (tenant selector)
  Header
    Breadcrumbs, SearchBar (Cmd+K), TokenBadge, Notifications
  Main Content (page-specific)
  RightPanel (contextual: citations, logs)
```

## Pages

### Dashboard Home
- WelcomeBanner (getting started checklist)
- QuickStats: Total Queries, Documents, Connections, Token Usage
- RecentActivity timeline
- AgentHealthWidget

### Connections
- ConnectionList grid of cards (type icon, name, status, last reflected)
- AddConnectionDialog modal (host, port, db, user, password, test button)
- SchemaExplorer expandable tree per connection (tables, columns, FKs)

### Agent Chat
- ChatSidebar (conversation history list)
- ChatMain: messages (user bubble + agent bubble with citation badges)
- CitationPanel slide-out (source doc, page, score, excerpt)
- ExecutionResult (status banner, code preview, result data table)
- AgentTrace expander (show node path)
- ChatInput (textarea, model selector, connection selector, send button)
- TokenCounter floating widget

### Documents
- UploadZone drag-and-drop with file list + progress
- DocumentList grid of cards (icon, name, size, chunks count)
- DocumentPreview slide-out (rendered content, chunk highlights)

### Events
- EventFeed real-time list (WebSocket)
  - EventItem: type icon, summary, status badge, progress bar, timestamp
  - EventDetail expander: full payload JSON, agent trace, execution log
- WebhookManager: list of webhook URLs, create dialog
- RulesManager: behavior rules list, YAML editor

### Settings
- General: tenant name, logo, default model
- API: API key manager (create, revoke, copy)
- Billing: usage chart, plan, payment (post-MVP)
- Team: members, roles (post-MVP)

## Key UI Patterns

### Citation Badges
- Inline colored badges [1], [2] in answer text
- Click opens source chunk in side panel
- Color code: green (score >= 0.9), yellow (>= 0.7), red (< 0.7)

### Real-time Status
- WebSocket for live event feed
- Agent execution progress bar with step labels
- Token counter updates live

### Dark-First Approach
- All components designed in dark mode
- Light mode via CSS variable overrides only
- System preference detection with manual toggle

### Responsive
- Sidebar collapses to icon-only on tablet
- Chat + citation panel stack on mobile
- Schema explorer tree adapts to narrow screens

## Magic UI Components To Use

- AnimatedList for event feed
- SparklesText for AI-generated content indicator
- ShimmerButton for CTA actions
- BorderBeam for connection status cards
- Particles for background effects
