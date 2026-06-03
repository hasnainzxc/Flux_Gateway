"""Async SQLAlchemy engine + session factory. Pool sized for ~30 concurrent DB conns."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings

# echo=True in dev logs all SQL — useful for debugging, noisy in prod
engine = create_async_engine(
    settings.database_url,
    echo=settings.is_development,
    pool_size=20,
    max_overflow=10,
)

# expire_on_commit=False so we can access attrs after commit without re-fetching
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session per request, auto-closes on exit."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
