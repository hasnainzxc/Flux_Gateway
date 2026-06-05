"""Tenant isolation tests — verify tenant A cannot access tenant B data."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.db.models import ApiKey, Tenant
from src.db.session import async_session_factory

pytestmark = pytest.mark.asyncio


async def test_tenant_isolation_list_keys(
    client: AsyncClient, bootstrap_key: str
) -> None:
    """
    Create a second tenant + key, then verify the first tenant's key
    cannot list the second tenant's API keys (tenant isolation at ORM level).
    """
    from hashlib import sha256
    import secrets
    import uuid as _uuid

    # Create tenant B in DB
    async with async_session_factory() as session:
        tenant_b = Tenant(
            id=_uuid.uuid4(),
            name="Tenant B",
            slug="tenant-b",
        )
        session.add(tenant_b)

        raw_key_b = f"sk-tenantb-{secrets.token_hex(16)}"
        key_b = ApiKey(
            tenant_id=tenant_b.id,
            name="tenant-b-key",
            key_hash=sha256(raw_key_b.encode()).hexdigest(),
            key_prefix=raw_key_b[:8],
        )
        session.add(key_b)
        await session.commit()

    # Use tenant B's key to list keys — should only see tenant B's keys
    response_b = await client.get(
        "/api/v1/api-keys/", headers={"X-API-Key": raw_key_b}
    )
    assert response_b.status_code == 200
    keys_b = response_b.json()
    assert isinstance(keys_b, list)

    # None of tenant B's keys should have the bootstrap key's name
    bootstrap_names = {k["name"] for k in keys_b}
    assert "pytest-fixture-key" not in bootstrap_names, (
        "Tenant B can see Tenant A's API keys — isolation broken!"
    )


async def test_tenant_middleware_sets_context(
    client: AsyncClient, bootstrap_key: str
) -> None:
    """Authenticated request sets current_tenant_id context variable correctly."""
    # The bootstrap key's tenant is the one created in conftest
    response = await client.get(
        "/api/v1/api-keys/", headers={"X-API-Key": bootstrap_key}
    )
    assert response.status_code == 200

    # Create a key in this tenant and verify it appears in the list
    create_resp = await client.post(
        "/api/v1/api-keys/",
        json={"name": "context-test-key"},
        headers={"X-API-Key": bootstrap_key},
    )
    assert create_resp.status_code == 201
    key_name = create_resp.json()["name"]

    # List keys again — the new key must be visible within the same tenant
    list_resp = await client.get(
        "/api/v1/api-keys/", headers={"X-API-Key": bootstrap_key}
    )
    assert list_resp.status_code == 200
    names = [k["name"] for k in list_resp.json()]
    assert key_name in names
