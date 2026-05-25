from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_tenant
from src.db.session import get_db
from src.services import rag_ingestion, rag_query

router = APIRouter(prefix="/rag", tags=["rag"])


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    error_message: str | None
    created_at: str

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    file_type_map = {"pdf": "pdf", "md": "md", "txt": "txt", "html": "html"}
    file_type = file_type_map.get(ext)
    if file_type is None:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")

    content = await file.read()
    max_size = 50 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    try:
        doc = await rag_ingestion.process_document(
            session=session,
            tenant_id=uuid.UUID(tenant_id),
            filename=file.filename,
            content=content,
            file_type=file_type,
        )
        await session.commit()
        rag_query._invalidate_bm25_index(uuid.UUID(tenant_id))
        return DocumentResponse(
            id=str(doc.id),
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status,
            chunk_count=doc.chunk_count,
            error_message=doc.error_message,
            created_at=doc.created_at.isoformat() if doc.created_at else "",
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}") from e


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> DocumentListResponse:
    docs = await rag_ingestion.list_documents(
        session=session, tenant_id=uuid.UUID(tenant_id), limit=limit, offset=offset
    )
    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=str(d.id),
                filename=d.filename,
                file_type=d.file_type,
                file_size=d.file_size,
                status=d.status,
                chunk_count=d.chunk_count,
                error_message=d.error_message,
                created_at=d.created_at.isoformat() if d.created_at else "",
            )
            for d in docs
        ],
        total=len(docs),
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> None:
    deleted = await rag_ingestion.delete_document(
        session=session, document_id=uuid.UUID(document_id), tenant_id=uuid.UUID(tenant_id)
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.commit()
    rag_query._invalidate_bm25_index(uuid.UUID(tenant_id))


class SearchResult(BaseModel):
    id: str
    content: str
    score: float
    document_id: str
    chunk_index: int
    token_count: int


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    body: SearchRequest,
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> SearchResponse:
    results = await rag_query.hybrid_search(
        session=session,
        tenant_id=uuid.UUID(tenant_id),
        query=body.query,
        top_k=body.top_k,
    )
    return SearchResponse(
        results=[SearchResult(**r) for r in results],
        query=body.query,
        total=len(results),
    )


class CitationInfo(BaseModel):
    index: int
    chunk_id: str
    document_id: str
    score: float
    excerpt: str


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationInfo]
    tokens_used: int


class AskRequest(BaseModel):
    query: str
    top_k: int = 10


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    body: AskRequest,
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> AskResponse:
    from src.services.llm import llm_complete

    results = await rag_query.hybrid_search(
        session=session, tenant_id=uuid.UUID(tenant_id), query=body.query, top_k=body.top_k
    )

    if not results:
        return AskResponse(
            answer="No relevant documents found.",
            citations=[],
            tokens_used=0,
        )

    context, citations = await rag_query.build_context_from_results(results)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant answering questions based on provided context documents. "
                "Reference sources using [1], [2] etc. corresponding to the context chunk numbers. "
                "If the context does not contain enough information, say so clearly."
            ),
        },
        {
            "role": "user",
            "content": f"Context:\n\n{context}\n\nQuestion: {body.query}\n\nAnswer with citations:",
        },
    ]

    answer = await llm_complete(messages)

    return AskResponse(
        answer=answer,
        citations=[CitationInfo(**c) for c in citations],
        tokens_used=sum(r["token_count"] for r in results) + len(answer) // 4,
    )


class CitationDetail(BaseModel):
    chunk_id: str
    content: str
    document_id: str
    chunk_index: int
    token_count: int
    created_at: str


@router.get("/citations/{chunk_id}", response_model=CitationDetail)
async def get_citation_detail(
    chunk_id: str,
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> CitationDetail:
    from sqlalchemy import select

    from src.db.models.chunk import Chunk

    result = await session.execute(
        select(Chunk).where(
            Chunk.id == uuid.UUID(chunk_id),
            Chunk.tenant_id == uuid.UUID(tenant_id),
        )
    )
    chunk = result.scalar_one_or_none()
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    return CitationDetail(
        chunk_id=str(chunk.id),
        content=chunk.content,
        document_id=str(chunk.document_id),
        chunk_index=chunk.chunk_index,
        token_count=chunk.token_count,
        created_at=chunk.created_at.isoformat() if chunk.created_at else "",
    )
