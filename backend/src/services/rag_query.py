from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.chunk import Chunk
from src.services.llm import generate_embeddings_fallback

BM25_K1 = 1.5
BM25_B = 0.75
RRF_K = 60
VECTOR_WEIGHT = 0.7
BM25_WEIGHT = 0.3

_bm25_indexes: dict[UUID, BM25Index] = {}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class BM25Index:
    def __init__(self) -> None:
        self.corpus_tokens: list[list[str]] = []
        self.doc_lengths: list[int] = []
        self.avgdl: float = 0.0
        self.df: dict[str, int] = defaultdict(int)
        self.N: int = 0
        self.chunk_ids: list[UUID] = []

    def index_chunks(self, chunks: list[tuple[UUID, str]]) -> None:
        for chunk_id, content in chunks:
            tokens = _tokenize(content)
            self.corpus_tokens.append(tokens)
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            self.chunk_ids.append(chunk_id)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.df[token] += 1
        self.N = len(self.corpus_tokens)
        if self.N > 0:
            self.avgdl = sum(self.doc_lengths) / self.N

    def compute_idf(self, term: str) -> float:
        if term not in self.df or self.df[term] == 0:
            return 0.0
        return math.log(1 + (self.N - self.df[term] + 0.5) / (self.df[term] + 0.5))

    def score(self, query_tokens: list[str]) -> list[tuple[UUID, float]]:
        if self.N == 0:
            return []
        scores: list[tuple[UUID, float]] = []
        for idx, doc_tokens in enumerate(self.corpus_tokens):
            doc_len = self.doc_lengths[idx]
            tf_counts = Counter(doc_tokens)
            score = 0.0
            for token in query_tokens:
                if token not in self.df:
                    continue
                tf = tf_counts.get(token, 0)
                idf = self.compute_idf(token)
                numerator = tf * (BM25_K1 + 1)
                denominator = tf + BM25_K1 * (1 - BM25_B + BM25_B * doc_len / self.avgdl)
                score += idf * numerator / denominator
            if score > 0:
                scores.append((self.chunk_ids[idx], score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores


async def _get_or_build_bm25_index(
    session: AsyncSession, tenant_id: UUID
) -> BM25Index:
    if tenant_id in _bm25_indexes:
        return _bm25_indexes[tenant_id]

    result = await session.execute(
        select(Chunk.id, Chunk.content)
        .where(Chunk.tenant_id == tenant_id)
        .order_by(Chunk.chunk_index)
    )
    rows = result.all()

    bm25 = BM25Index()
    bm25.index_chunks([(row[0], row[1]) for row in rows])
    _bm25_indexes[tenant_id] = bm25
    return bm25


def _invalidate_bm25_index(tenant_id: UUID) -> None:
    _bm25_indexes.pop(tenant_id, None)


async def vector_search(
    session: AsyncSession,
    tenant_id: UUID,
    query_embedding: list[float],
    top_k: int = 10,
) -> list[tuple[UUID, float]]:

    distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    similarity = (1 - distance).label("similarity")

    result = await session.execute(
        select(Chunk.id, similarity)
        .where(
            Chunk.tenant_id == tenant_id,
            Chunk.embedding.isnot(None),
        )
        .order_by(distance)
        .limit(top_k)
    )
    return [(row[0], float(row[1])) for row in result.all()]


async def bm25_search(
    session: AsyncSession,
    tenant_id: UUID,
    query: str,
    top_k: int = 10,
) -> list[tuple[UUID, float]]:
    bm25 = await _get_or_build_bm25_index(session, tenant_id)
    query_tokens = _tokenize(query)
    results = bm25.score(query_tokens)
    return results[:top_k]


def reciprocal_rank_fusion(
    vector_results: list[tuple[UUID, float]],
    bm25_results: list[tuple[UUID, float]],
    k: int = RRF_K,
    vector_weight: float = VECTOR_WEIGHT,
    bm25_weight: float = BM25_WEIGHT,
) -> list[tuple[UUID, float]]:
    scores: dict[UUID, float] = defaultdict(float)

    for rank, (chunk_id, _) in enumerate(vector_results):
        scores[chunk_id] += vector_weight / (k + rank + 1)

    for rank, (chunk_id, _) in enumerate(bm25_results):
        scores[chunk_id] += bm25_weight / (k + rank + 1)

    fused = list(scores.items())
    fused.sort(key=lambda x: x[1], reverse=True)
    return fused


async def hybrid_search(
    session: AsyncSession,
    tenant_id: UUID,
    query: str,
    top_k: int = 10,
) -> list[dict]:
    query_embedding_list = await generate_embeddings_fallback([query])
    query_embedding = query_embedding_list[0]

    vec_results = await vector_search(session, tenant_id, query_embedding, top_k * 2)
    bm25_results = await bm25_search(session, tenant_id, query, top_k * 2)

    fused = reciprocal_rank_fusion(vec_results, bm25_results)
    top_chunk_ids = [chunk_id for chunk_id, _ in fused[:top_k]]

    if not top_chunk_ids:
        return []

    result = await session.execute(
        select(Chunk).where(Chunk.id.in_(top_chunk_ids))
    )
    chunk_map = {c.id: c for c in result.scalars().all()}

    output = []
    for chunk_id, score in fused[:top_k]:
        chunk = chunk_map.get(chunk_id)
        if chunk:
            output.append({
                "id": str(chunk.id),
                "content": chunk.content,
                "score": round(score, 4),
                "document_id": str(chunk.document_id),
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
            })
    return output


async def build_context_from_results(
    results: list[dict],
    max_tokens: int = 3000,
) -> tuple[str, list[dict]]:
    context_parts: list[str] = []
    citations: list[dict] = []
    token_count = 0

    for i, r in enumerate(results):
        chunk_tokens = r.get("token_count", len(r["content"]) // 4)
        if token_count + chunk_tokens > max_tokens:
            break
        context_parts.append(f"[{i+1}] {r['content']}")
        citations.append({
            "index": i + 1,
            "chunk_id": r["id"],
            "document_id": r["document_id"],
            "score": r["score"],
            "excerpt": r["content"][:200],
        })
        token_count += chunk_tokens

    return "\n\n".join(context_parts), citations
