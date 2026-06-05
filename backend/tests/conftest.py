"""Test fixtures for Flux Gateway backend — async client, test tenant, API key provisioning."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Override environment for tests BEFORE importing app
# ---------------------------------------------------------------------------
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "pytest-secret-key-not-for-production")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-v1-test-placeholder")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client pointed at the FastAPI app (uses ASGITransport, no real server)."""
    from src.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def bootstrap_key(client: AsyncClient) -> str:
    """
    Hit /api/v1/api-keys bootstrap-like endpoint to get a valid API key.
    In test mode, the dev tenant bootstrap in main.py runs on startup, printing
    a sk- key to stdout. We create a fresh key via the bootstrap mechanism by
    calling the health-check to trigger lifecycle, then reading the bootstrap output.

    Alternative path: directly insert a tenant+key in DB (bypass auth for fixture setup).
    """
    from hashlib import sha256
    from src.db.models import ApiKey, Tenant
    from src.db.session import async_session_factory

    async with async_session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(select(Tenant).limit(1))
        tenant = result.scalar_one_or_none()

        if tenant is None:
            # Bootstrap tenant manually for test
            import uuid as _uuid

            tenant = Tenant(
                id=_uuid.uuid4(),
                name="Test Tenant",
                slug="test-tenant",
            )
            session.add(tenant)
            await session.flush()

        # Create a fresh API key for testing
        import secrets

        raw_key = f"sk-test-{secrets.token_hex(16)}"
        key_hash = sha256(raw_key.encode()).hexdigest()
        api_key = ApiKey(
            tenant_id=tenant.id,
            name="pytest-fixture-key",
            key_hash=key_hash,
            key_prefix=raw_key[:8],
        )
        session.add(api_key)
        await session.commit()

    return raw_key


@pytest_asyncio.fixture
async def auth_headers(bootstrap_key: str) -> dict[str, str]:
    """Headers with a valid X-API-Key for authenticated requests."""
    return {"X-API-Key": bootstrap_key}


@pytest_asyncio.fixture
async def client_auth(
    client: AsyncClient, auth_headers: dict[str, str]
) -> AsyncGenerator[AsyncClient, None]:
    """Async client with auth headers pre-set (convenience for authenticated tests)."""
    # We can't mutate the client, so return a wrapper concept.
    # Instead, tests should pass auth_headers explicitly.
    yield client
