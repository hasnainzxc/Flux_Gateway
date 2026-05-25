from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.chunk import Chunk
from src.db.models.document import Document
from src.services.llm import generate_embeddings_fallback

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MIN_CHUNK_SIZE = 100
EMBEDDING_BATCH_SIZE = 20


def _estimate_tokens(text: str) -> int:
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4


async def parse_document(content: bytes, file_type: str) -> str:
    if file_type == "pdf":
        import fitz

        doc = fitz.open(stream=content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    elif file_type in ("md", "txt", "html"):
        return content.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _estimate_tokens(para)

        if current_tokens + para_tokens > chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            overlap_text = "\n\n".join(current_chunk[-2:]) if len(current_chunk) >= 2 else ""
            current_chunk = [overlap_text] if overlap_text else []
            current_tokens = _estimate_tokens(overlap_text) if overlap_text else 0

        current_chunk.append(para)
        current_tokens += para_tokens

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return [c for c in chunks if _estimate_tokens(c) >= MIN_CHUNK_SIZE]


async def embed_chunks(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        batch_embeddings = await generate_embeddings_fallback(batch)
        embeddings.extend(batch_embeddings)
    return embeddings


async def process_document(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    filename: str,
    content: bytes,
    file_type: str,
    connection_id: uuid.UUID | None = None,
) -> Document:
    document = Document(
        tenant_id=tenant_id,
        connection_id=connection_id,
        filename=filename,
        file_type=file_type,
        file_size=len(content),
        status="processing",
    )
    session.add(document)
    await session.flush()

    try:
        text = await parse_document(content, file_type)
        chunks_content = chunk_text(text)

        embeddings = await embed_chunks(chunks_content)

        for idx, chunk_text_content in enumerate(chunks_content):
            token_count = _estimate_tokens(chunk_text_content)
            embedding = embeddings[idx] if idx < len(embeddings) else None
            chunk = Chunk(
                document_id=document.id,
                tenant_id=tenant_id,
                content=chunk_text_content,
                chunk_index=idx,
                embedding=embedding,
                token_count=token_count,
                chunk_metadata={"source": filename, "chunk_index": idx},
            )
            session.add(chunk)

        document.status = "completed"
        document.chunk_count = len(chunks_content)
        await session.flush()

        return document
    except Exception as e:
        document.status = "failed"
        document.error_message = str(e)
        await session.flush()
        raise


async def get_document(session: AsyncSession, document_id: uuid.UUID, tenant_id: uuid.UUID) -> Document | None:
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_documents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[Document]:
    result = await session.execute(
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def delete_document(session: AsyncSession, document_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
    doc = await get_document(session, document_id, tenant_id)
    if doc is None:
        return False
    await session.delete(doc)
    await session.flush()
    return True
