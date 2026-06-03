"""LLM client wrappers — OpenRouter (OpenAI-compatible) for chat + embeddings."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from src.core.config import settings

# Singleton OpenAI client — reused across all LLM calls
_client: AsyncOpenAI | None = None


def get_openrouter_client() -> AsyncOpenAI:
    """Lazy-init OpenRouter client (OpenAI-compatible API)."""
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
    """
    Chat completion -> (text, token_count).
    Default model: gpt-4o-mini (cheap, fast). Override for complex tasks.
    """
    client = get_openrouter_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        max_tokens=max_tokens,
    )
    # Handle edge case where model returns no content (empty response)
    content = response.choices[0].message.content or ""
    tokens = response.usage.total_tokens if response.usage else 0
    return content, tokens


async def llm_complete_json(
    messages: list[dict[str, str]],
    model: str = "openai/gpt-4o-mini",
    temperature: float = 0.0,
) -> tuple[dict[str, Any], int]:
    """
    Chat completion with JSON mode enforced. Returns (parsed_dict, token_count).
    Use for structured output (SQL generation, classification, etc.).
    NOTE: temperature=0.0 for deterministic output — critical for SQL generation.
    """
    client = get_openrouter_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        response_format={"type": "json_object"},  # force JSON output from model
    )
    content = response.choices[0].message.content
    tokens = response.usage.total_tokens if response.usage else 0
    import json

    # Parse JSON — empty content returns empty dict (graceful degradation)
    return (json.loads(content) if content else {}), tokens


async def generate_embeddings(
    texts: list[str],
    model: str = "openai/text-embedding-3-small",
) -> list[list[float]]:
    """Generate 1536-dim embeddings via OpenRouter. Batch-friendly."""
    client = get_openrouter_client()
    response = await client.embeddings.create(
        model=model,
        input=texts,
    )
    return [item.embedding for item in response.data]


# Lazy-loaded local fallback embedder (sentence-transformers)
_LocalEmbedder: object = None


def _get_local_embedder() -> object | None:
    """Try to load sentence-transformers for offline/fallback embeddings."""
    global _LocalEmbedder
    if _LocalEmbedder is not None:
        return _LocalEmbedder
    try:
        from sentence_transformers import SentenceTransformer

        # all-MiniLM-L6-v2 = 384-dim, DB expects 1536.
        # Dim mismatch handled in generate_embeddings_fallback via zero-padding.
        _LocalEmbedder = SentenceTransformer("all-MiniLM-L6-v2")
        return _LocalEmbedder
    except ImportError:
        return None


async def generate_embeddings_fallback(
    texts: list[str],
) -> list[list[float]]:
    """
    Try OpenRouter embeddings first. On failure, fall back to local sentence-transformers.
    Runs local model in thread pool to avoid blocking async loop.
    """
    try:
        return await generate_embeddings(texts)
    except Exception:
        # API failed — try local model (all-MiniLM-L6-v2, 384-dim)
        embedder = _get_local_embedder()
        if embedder is None:
            raise RuntimeError(
                "OpenRouter embeddings failed and no local embedder available"
            ) from None
        import asyncio

        # Run CPU-bound encoding in thread pool — don't block async event loop
        results = await asyncio.to_thread(embedder.encode, texts, normalize_embeddings=True)  # type: ignore[attr-defined]
        vectors = [r.tolist() for r in results]

        # Local model outputs 384-dim, DB expects 1536 — zero-pad to match pgvector column
        # This is a degraded fallback; primary embeddings (OpenRouter) should always be preferred
        target_dim = 1536
        padded = []
        for v in vectors:
            if len(v) < target_dim:
                padded.append(v + [0.0] * (target_dim - len(v)))
            else:
                padded.append(v[:target_dim])
        return padded
