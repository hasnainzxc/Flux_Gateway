from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from src.core.config import settings

_client: AsyncOpenAI | None = None


def get_openrouter_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )
    return _client


async def llm_complete(
    messages: list[dict[str, str]],
    model: str = "openai/gpt-4o-mini",
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> tuple[str, int]:
    client = get_openrouter_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or ""
    tokens = response.usage.total_tokens if response.usage else 0
    return content, tokens


async def llm_complete_json(
    messages: list[dict[str, str]],
    model: str = "openai/gpt-4o-mini",
    temperature: float = 0.0,
) -> tuple[dict[str, Any], int]:
    client = get_openrouter_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    tokens = response.usage.total_tokens if response.usage else 0
    import json

    return (json.loads(content) if content else {}), tokens


async def generate_embeddings(
    texts: list[str],
    model: str = "openai/text-embedding-3-small",
) -> list[list[float]]:
    client = get_openrouter_client()
    response = await client.embeddings.create(
        model=model,
        input=texts,
    )
    return [item.embedding for item in response.data]


_LocalEmbedder: object = None


def _get_local_embedder() -> object | None:
    global _LocalEmbedder
    if _LocalEmbedder is not None:
        return _LocalEmbedder
    try:
        from sentence_transformers import SentenceTransformer

        _LocalEmbedder = SentenceTransformer("all-MiniLM-L6-v2")
        return _LocalEmbedder
    except ImportError:
        return None


async def generate_embeddings_fallback(
    texts: list[str],
) -> list[list[float]]:
    try:
        return await generate_embeddings(texts)
    except Exception:
        embedder = _get_local_embedder()
        if embedder is None:
            raise RuntimeError(
                "OpenRouter embeddings failed and no local embedder available"
            ) from None
        import asyncio

        results = await asyncio.to_thread(embedder.encode, texts, normalize_embeddings=True)  # type: ignore[attr-defined]
        return [r.tolist() for r in results]
