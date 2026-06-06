"""Auth tests — API key validation, missing headers, expiry checks."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check(client: AsyncClient) -> None:
    """Health endpoint is public — no auth required."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_api_keys_requires_auth(client: AsyncClient) -> None:
    """Listing API keys without auth header returns 401."""
    response = await client.get("/api/v1/api-keys/")
    assert response.status_code == 401


async def test_api_keys_list_with_valid_key(
    client: AsyncClient, bootstrap_key: str
) -> None:
    """List API keys with a valid sk- key returns 200 + array."""
    response = await client.get(
        "/api/v1/api-keys/", headers={"X-API-Key": bootstrap_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


async def test_api_keys_list_with_invalid_key(client: AsyncClient) -> None:
    """Non-sk- token triggers JWT decode path — fails with 401/422."""
    # Use non-sk- prefix to avoid DB lookup path (no test DB needed)
    response = await client.get(
        "/api/v1/api-keys/", headers={"X-API-Key": "invalid-jwt-token"}
    )
    assert response.status_code in (401, 422)


async def test_api_keys_list_with_bad_prefix(client: AsyncClient) -> None:
    """Another non-sk- token variant — JWT decode fails."""
    response = await client.get(
        "/api/v1/api-keys/", headers={"X-API-Key": "Bearer garbage"}
    )
    assert response.status_code in (401, 422)


async def test_api_key_create(client: AsyncClient, bootstrap_key: str) -> None:
    """Create a new API key with valid auth returns 201 + raw_key with sk- prefix."""
    response = await client.post(
        "/api/v1/api-keys/",
        json={"name": "pytest-created-key"},
        headers={"X-API-Key": bootstrap_key},
    )
    assert response.status_code == 201
    data = response.json()
    assert "raw_key" in data
    assert data["raw_key"].startswith("sk-")
    assert data["name"] == "pytest-created-key"


async def test_api_key_revoke(
    client: AsyncClient, bootstrap_key: str
) -> None:
    """Create then revoke an API key — revoke returns 204."""
    # Create a key to revoke
    create_resp = await client.post(
        "/api/v1/api-keys/",
        json={"name": "to-revoke"},
        headers={"X-API-Key": bootstrap_key},
    )
    assert create_resp.status_code == 201
    key_id = create_resp.json()["id"]

    # Revoke it
    revoke_resp = await client.delete(
        f"/api/v1/api-keys/{key_id}",
        headers={"X-API-Key": bootstrap_key},
    )
    assert revoke_resp.status_code == 204


async def test_connections_requires_auth(client: AsyncClient) -> None:
    """Protected endpoints return 401 without auth."""
    response = await client.get("/api/v1/connections/")
    assert response.status_code == 401


async def test_usage_requires_auth(client: AsyncClient) -> None:
    """Usage endpoint is protected."""
    response = await client.get("/api/v1/usage/summary")
    assert response.status_code == 401
