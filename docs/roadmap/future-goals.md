# Future Goals (Post-MVP)

> Features planned after Stage 3 launch. Prioritized by impact + feasibility.

---

## Q2 2026 (Weeks 13-16): Production Hardening

### Authentication & Multi-User
- [ ] OAuth/OIDC integration (Google, GitHub, SAML for enterprise)
- [ ] Role-based access control (admin, developer, viewer)
- [ ] Multi-user per tenant
- [ ] Audit log for all user actions

### Database Support Expansion
- [ ] MySQL/MariaDB schema reflection
- [ ] MongoDB schema inference (sampling-based)
- [ ] REST API schema discovery (OpenAPI/Swagger parsing)
- [ ] GraphQL schema introspection

### Scalability
- [ ] Horizontal scaling (multiple FastAPI instances behind load balancer)
- [ ] Read replicas for PostgreSQL
- [ ] Redis cluster for Pub/Sub
- [ ] Kubernetes deployment manifests
- [ ] CDN for frontend assets

---

## Q3 2026 (Weeks 17-24): Advanced Features

### Multi-Modal RAG
- [ ] Image extraction from PDFs (tables, charts)
- [ ] Audio transcription + indexing
- [ ] Code repository indexing (GitHub/GitLab integration)
- [ ] Real-time document sync (watch folders for changes)

### Advanced Agent Capabilities
- [ ] Multi-step agent workflows (DAG of tool calls)
- [ ] Human-in-the-loop approval for high-risk writes
- [ ] Agent memory across sessions (conversation history)
- [ ] Custom tool definitions (tenant can define own tools)
- [ ] Agent performance analytics dashboard

### Enterprise Features
- [ ] SSO / SAML integration
- [ ] SOC 2 compliance preparation
- [ ] Data residency options (EU, US, APAC)
- [ ] Private cloud deployment option
- [ ] Custom embedding model support (bring your own model)
- [ ] On-premise MCP Server deployment

---

## Q4 2026 (Weeks 25+): Platform Maturity

### Marketplace
- [ ] Agent template marketplace (pre-built agents for common tasks)
- [ ] Connector marketplace (DB, API, SaaS integrations)
- [ ] Community-contributed behavior rules

### Monetization
- [ ] Stripe billing integration
- [ ] Usage-based pricing tiers
- [ ] Free tier (limited queries/docs)
- [ ] Enterprise tier (unlimited, custom models, SLA)
- [ ] Annual contract billing

### AI/ML Enhancements
- [ ] Fine-tuned agent models per tenant domain
- [ ] Automatic schema optimization suggestions
- [ ] Anomaly detection in query patterns
- [ ] Predictive query routing (which model for which task)

### Developer Experience
- [ ] Public API documentation (OpenAPI/Swagger)
- [ ] SDK for Python, JavaScript, Ruby, Go
- [ ] CLI tool for local development + testing
- [ ] Webhook testing sandbox
- [ ] Agent debugging tools (step-through execution)

---

## Long-Term Vision (2027+)

### Self-Serve Agent Platform
- Zero-code agent builder (drag-and-drop workflow designer)
- Visual schema mapper (connect tables visually)
- Pre-built agent templates for: inventory management, customer support, sales reporting, HR onboarding

### Cross-System Orchestration
- Agent can coordinate across multiple systems (DB + API + File)
- Transactional guarantees across systems (compensating actions on failure)
- Event-driven agent chaining (output of Agent A → input to Agent B)

### AI-Native Operations
- Agent that writes and deploys its own MCP servers
- Agent that auto-discovers new data sources
- Agent that suggests workflow optimizations based on usage patterns

### Platform Play
- White-label solution for system integrators
- Partner program for consulting firms
- Certification program for Flux Gateway specialists

---

## Technical Debt & Maintenance (Continuous)

- [ ] Dependency updates (weekly automated PRs)
- [ ] Security vulnerability scanning (daily)
- [ ] Performance regression testing (per-release)
- [ ] Documentation updates (per-feature)
- [ ] User feedback loop (in-app feedback + NPS surveys)
