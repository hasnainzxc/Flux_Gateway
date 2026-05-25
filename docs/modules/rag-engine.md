# Isolated Hybrid RAG Engine

> **Module**: `backend/src/services/rag_ingestion.py`, `rag_query.py`  
> **API**: `backend/src/api/v1/rag.py`  
> **Models**: `backend/src/db/models/document.py`, `chunk.py`, `citation.py`

## Purpose

Multi-tenant semantic search over unstructured operational documents (PDFs, Markdown, HTML, plain text). Combines pgvector dense embeddings with BM25 lexical keyword matching. Every response includes a deterministic Citation Tracking Graph — verifiable audit trail that kills AI hallucinations.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Ingestion Pipeline                          │
│                                                                  │
│  Client Uploads       ┌──────────┐    ┌──────────┐             │
│  ┌─────┐  ┌─────┐     │ Document │    │ Semantic │             │
│  │ PDF │  │ MD  │ ──► │ Parser   │───►│ Chunker  │             │
│  │     │  │     │     │          │    │          │             │
│  └─────┘  └─────┘     └──────────┘    └────┬─────┘             │
│      S3 / Local Folders                     │                   │
│                                             ▼                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              Embedding Generation                     │      │
│  │  Each chunk → Embedding Model → 1536d vector          │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                       │
│                         ▼                                       │
│  ┌──────────────────────────────────────────────────────┐      │
│  │           pgvector Storage (per-tenant)               │      │
│  │  ┌─────────────────────────────────────────────────┐ │      │
│  │  │ chunks table:                                    │ │      │
│  │  │  id, tenant_id, doc_id, chunk_index,             │ │      │
│  │  │  content (text), embedding (vector(1536)),      │ │      │
│  │  │  metadata(jsonb), created_at                     │ │      │
│  │  └─────────────────────────────────────────────────┘ │      │
│  │  HARDCODED: WHERE tenant_id = X on EVERY query       │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                  │
│                         ▼                                       │
│  ┌──────────────────────────────────────────────────────┐      │
│  │          BM25 Index (per-tenant, memory)              │      │
│  │  Token → {chunk_id: term_frequency}                   │      │
│  │  Rebuilt on ingestion, incremental updates            │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      Query Pipeline                              │
│                                                                  │
│  User Prompt                                                      │
│      │                                                            │
│      ▼                                                            │
│  ┌──────────────┐                                                │
│  │ Embed Query  │ → 1536d vector                                 │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ├────────────────────┐                                    │
│         ▼                    ▼                                    │
│  ┌──────────────┐   ┌──────────────┐                            │
│  │ Vector Search│   │ BM25 Search  │                            │
│  │ (cosine ≤)   │   │ (keyword tf) │                            │
│  │ WHERE        │   │ WHERE        │                            │
│  │ tenant_id=X  │   │ tenant_id=X  │                            │
│  └──────┬───────┘   └──────┬───────┘                            │
│         │                    │                                     │
│         └────────┬───────────┘                                    │
│                  ▼                                                │
│  ┌──────────────────────────────────────┐                        │
│  │    Reciprocal Rank Fusion (RRF)      │                        │
│  │    score = Σ 1/(k + rank_i)          │                        │
│  │    Merge + deduplicate top-K         │                        │
│  └──────────────────┬───────────────────┘                        │
│                     ▼                                            │
│  ┌──────────────────────────────────────┐                        │
│  │    Context Assembly                  │                        │
│  │    chunks → formatted text +         │                        │
│  │    citation metadata                 │                        │
│  └──────────────────┬───────────────────┘                        │
│                     ▼                                            │
│  ┌──────────────────────────────────────┐                        │
│  │    LLM Response Generation           │                        │
│  │    Answer + inline citations         │                        │
│  └──────────────────┬───────────────────┘                        │
│                     ▼                                            │
│  ┌──────────────────────────────────────┐                        │
│  │    Citation Tracking Response        │                        │
│  │    {                                │                        │
│  │      "answer": "... [1] ... [2]",   │                        │
│  │      "citations": [                 │                        │
│  │        {                            │                        │
│  │          "id": "chunk:abc123",      │                        │
│  │          "doc": "policy_2025.pdf",  │                        │
│  │          "page": 3,                 │                        │
│  │          "score": 0.92,             │                        │
│  │          "excerpt": "..."           │                        │
│  │        }                            │                        │
│  │      ]                              │                        │
│  │    }                                │                        │
│  └──────────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

## Chunking Strategy

```python
# Semantic chunking — splits on natural boundaries
# Configurable per tenant
CHUNK_SIZE = 1000        # tokens (not chars) — use tiktoken
CHUNK_OVERLAP = 200      # overlap for continuity
MIN_CHUNK_SIZE = 100     # discard tiny fragments

# For PDFs: split on headings, paragraphs
# For Markdown: split on ## headers
# For code: split on function/class boundaries
```

## Hybrid Search Algorithm

```python
async def hybrid_search(
    tenant_id: str,
    query: str,
    top_k: int = 10,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
) -> list[SearchResult]:
    
    # 1. Vector search
    query_embedding = await embed(query)
    vector_results = await db.execute(
        select(Chunk)
        .where(Chunk.tenant_id == tenant_id)  # HARDCODED
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k * 2)  # oversample for fusion
    )
    
    # 2. BM25 lexical search
    keyword_results = bm25_index.search(
        query, 
        tenant_id=tenant_id,  # HARDCODED
        top_k=top_k * 2
    )
    
    # 3. Reciprocal Rank Fusion
    fused = reciprocal_rank_fusion(
        vector_results, 
        keyword_results, 
        k=60  # RRF constant
    )
    
    return fused[:top_k]
```

## Tenant Isolation (Critical)

```python
# ORM Event Listener — enforced on ALL chunk queries
@event.listens_for(Session, "do_orm_execute")
def add_tenant_filter(execute_state):
    if execute_state.is_select and execute_state.bind_arguments.get("tenant_id"):
        tenant_id = execute_state.bind_arguments["tenant_id"]
        for col in execute_state.statement.selected_columns:
            table = getattr(col, "entity_namespace", None)
            if table and hasattr(table, "tenant_id"):
                execute_state.statement = execute_state.statement.where(
                    table.tenant_id == tenant_id
                )

# Usage: EVERY service call passes tenant_id
async def search_chunks(db: AsyncSession, tenant_id: str, query: str):
    result = await db.execute(
        select(Chunk)
        .execution_options(tenant_id=tenant_id)  # triggers listener
        .where(Chunk.embedding.cosine_distance(embedding) < 0.3)
    )
```

## Citation Tracking

Every LLM response includes:
1. **Inline markers**: `[1]`, `[2]` in answer text
2. **Citation array**: chunk_id, source_document, page_number, relevance_score, excerpt
3. **Audit log**: every citation stored in `citations` table for compliance

Frontend renders:
- Color-coded citation badges inline
- Click badge → slide-out panel with source chunk
- Confidence score per citation (green/yellow/red)
- "View source document" link where available

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/rag/documents` | Upload document for ingestion |
| GET | `/api/v1/rag/documents` | List tenant's documents |
| DELETE | `/api/v1/rag/documents/{id}` | Remove document + chunks |
| POST | `/api/v1/rag/search` | Hybrid search query |
| GET | `/api/v1/rag/citations/{chunk_id}` | Get chunk details for citation |
| POST | `/api/v1/rag/ask` | Full RAG: search → answer with citations |

## Embedding Model Selection

| Model | Dims | Local/API | Notes |
|-------|------|-----------|-------|
| OpenAI text-embedding-3-small | 1536 | API | Good quality, cheap, easy |
| all-MiniLM-L6-v2 | 384 | Local | Fast, good for MVP, run on CPU |
| BGE-large-en-v1.5 | 1024 | Local | Best quality, needs GPU for speed |

**Recommendation for MVP**: Start with OpenAI for simplicity. Add local model support in config.

## Future Enhancements

- Recursive chunk splitting (parent-child chunks for context expansion)
- Multi-modal RAG (image/table extraction from PDFs)
- Query rewriting (LLM rewrites user query for better retrieval)
- Re-ranking (cross-encoder re-ranks top-K results)
- Document-level access control (some docs restricted by user role)
