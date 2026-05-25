# Stage 2: Productization & Visual Engine (Weeks 5-8)

> **Goal**: Turn terminal-based config into interactive enterprise dashboard. Ship RAG pipeline + agent orchestration.

---

## Week 5: RAG Ingestion Pipeline

### Day 1-2: Document Processing
- [ ] Integrate PyMuPDF + Unstructured for document parsing
- [ ] Implement semantic chunking (tiktoken, configurable size/overlap)
- [ ] Support: PDF, Markdown, HTML, plain text
- [ ] File upload endpoint with size validation

### Day 3-4: Embedding Pipeline
- [ ] Integrate embedding model (OpenAI text-embedding-3-small for MVP)
- [ ] Batch embedding generation for chunks
- [ ] Store in pgvector with tenant_id column
- [ ] Build HNSW index for vector search performance

### Day 5: Ingestion API
- [ ] `POST /api/v1/rag/documents` — upload + process
- [ ] `GET /api/v1/rag/documents` — list tenant docs
- [ ] `DELETE /api/v1/rag/documents/{id}` — remove + cleanup chunks
- [ ] Progress tracking during ingestion

### Week 5 Deliverables
- Document upload → chunking → embedding → pgvector storage working
- All queries tenant-scoped

---

## Week 6: Hybrid Search + Citations

### Day 1-2: BM25 Implementation
- [ ] Implement per-tenant BM25 index (in-memory or Redis-backed)
- [ ] Tokenization + term frequency calculation
- [ ] Incremental index updates on ingestion
- [ ] Tenant-scoped index (no cross-tenant keywords)

### Day 3-4: Hybrid Search
- [ ] Vector search (cosine distance via pgvector)
- [ ] BM25 keyword search
- [ ] Reciprocal Rank Fusion for result merging
- [ ] `POST /api/v1/rag/search` endpoint
- [ ] `POST /api/v1/rag/ask` — full RAG: search → answer with citations

### Day 5: Citation Tracking
- [ ] Citation metadata in every RAG response
- [ ] `GET /api/v1/rag/citations/{chunk_id}` — chunk detail
- [ ] Audit log: every citation stored for compliance
- [ ] Test: upload doc → query → verify citations point to correct chunks

### Week 6 Deliverables
- Hybrid search (vector + BM25) working
- Full RAG pipeline: upload → search → answer with verifiable citations

---

## Week 7: Agent Orchestration (LangGraph)

### Day 1-2: LangGraph Setup
- [ ] Define AgentState TypedDict
- [ ] Build graph: classify_intent → researcher/coder → reviewer → self_heal → mcp_exec
- [ ] Implement conditional edges (read vs write routing)
- [ ] Implement ClassifyIntent node (cheap LLM call)
- [ ] Implement Researcher node (RAG-powered answer)

### Day 3-4: Coder + Reviewer Nodes
- [ ] Implement Coder node (schema-grounded SQL generation)
- [ ] Implement Reviewer node (sandbox dry-run placeholder — full Docker in week 9)
- [ ] Implement basic syntax validation without Docker
- [ ] Implement self-healing loop (error → fix → retry, max 3)

### Day 5: Agent API
- [ ] `POST /api/v1/agent/query` — full agent loop
- [ ] `GET /api/v1/agent/queries/{id}` — get result
- [ ] `GET /api/v1/agent/queries` — history
- [ ] Telemetry: tokens used, latency per node
- [ ] Store agent run history

### Week 7 Deliverables
- LangGraph agent fully functional
- READ path: query → RAG → answer with citations
- WRITE path: code gen → validate → self-heal (sandbox placeholder)
- Agent run history stored

---

## Week 8: Frontend Dashboard MVP

### Day 1-2: Dashboard Shell
- [ ] Next.js 16 App Router setup with dark-first theme
- [ ] shadcn/ui component installation
- [ ] Magic UI integration (animated components)
- [ ] Motion.dev page transitions
- [ ] Geist font configuration
- [ ] Dashboard layout: sidebar + header + main

### Day 3: Connections + Schema Pages
- [ ] Connections page: card grid, add dialog, test connection
- [ ] Schema Explorer: tree view of tables/columns/FKs
- [ ] Real-time connection status indicators

### Day 4: Agent Chat Interface
- [ ] Chat page: message list, input, send
- [ ] Agent response: answer text + citation badges
- [ ] Citation panel: source doc, page, score, excerpt
- [ ] Execution result display (for write actions)
- [ ] Agent trace expander (show node path)
- [ ] Token counter widget

### Day 5: Testing + Polish
- [ ] Playwright MCP E2E test: connect → explore schema → ask question → verify citations
- [ ] Responsive design testing
- [ ] Loading states + error boundaries
- [ ] Dark/light mode toggle

### Stage 2 Milestone
**Working**: Full dashboard where user connects DB, sees schema graph, uploads documents, asks NL questions, gets cited answers. Agent can generate and validate write operations.

---

## Stage 2 File Checklist

```
backend/
├── src/
│   ├── services/
│   │   ├── rag_ingestion.py       ✅
│   │   └── rag_query.py           ✅
│   ├── agents/
│   │   ├── graph.py               ✅
│   │   └── nodes/
│   │       ├── classifier.py      ✅
│   │       ├── researcher.py      ✅
│   │       ├── coder.py           ✅
│   │       ├── reviewer.py        ✅
│   │       └── self_healing.py    ✅
│   ├── api/v1/
│   │   ├── rag.py                 ✅
│   │   └── agent.py               ✅
│   └── db/models/
│       ├── document.py            ✅
│       ├── chunk.py               ✅
│       └── citation.py            ✅

frontend/
├── src/
│   ├── app/(dashboard)/
│   │   ├── connections/page.tsx   ✅
│   │   ├── schema/page.tsx        ✅
│   │   ├── chat/page.tsx          ✅
│   │   └── docs/page.tsx          ✅
│   └── components/
│       ├── chat/                  ✅
│       ├── citations/             ✅
│       ├── schema/                ✅
│       └── telemetry/             ✅
```
