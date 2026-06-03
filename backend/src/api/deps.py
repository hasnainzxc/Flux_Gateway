"""Auth dependencies — dual-mode: API key (sk-...) or JWT Bearer token."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.oidc import decode_access_token
from src.core.tenant import current_tenant_id
from src.db.models import ApiKey
from src.db.session import get_db

# auto_error=False so we can return custom 401 instead of FastAPI default
security_scheme = HTTPBearer(auto_error=False)

# Pluggable OIDC provider — set at startup, used for token introspection if needed
_oidc_provider: Callable[..., object] | None = None


def set_oidc_provider(provider: Callable[..., object]) -> None:
    """Register OIDC provider callable — reserved for future token introspection."""
    global _oidc_provider
    _oidc_provider = provider


async def authenticate(
    request: Request,
    session: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),  # noqa: B008
) -> str:
    """
    Unified auth entrypoint. Routes by token prefix:
    - sk-* -> API key lookup (SHA-256 hash match)
    - anything else -> JWT decode
    Sets current_tenant_id context var on success.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    token = credentials.credentials

    # Route by token prefix: sk-* = API key, anything else = JWT bearer
    if token.startswith("sk-"):
        return await _auth_api_key(token, session, request)
    else:
        return _auth_jwt(token, request)


async def _auth_api_key(raw_key: str, session: AsyncSession, request: Request) -> str:
    """Hash the raw key, look up in DB. Only active keys pass."""
    from hashlib import sha256

    # SHA-256 the raw key — never store or log the plaintext
    key_hash = sha256(raw_key.encode()).hexdigest()

    from datetime import datetime

    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
            # Reject expired keys — NULL expires_at means never expires
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )

    # Check expiry — keys with expires_at in the past are rejected
    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    # Set tenant context var — consumed by tenant_isolation.py for row-level filtering
    tenant_id = str(api_key.tenant_id)
    current_tenant_id.set(tenant_id)
    return tenant_id


def _auth_jwt(token: str, request: Request) -> str:
    """Decode JWT, extract tenant_id, set context var. Raises 401 on bad/expired token."""
    payload = decode_access_token(token)
    tenant_id: str = payload["tenant_id"]
    # Set tenant context var — consumed by tenant_isolation.py for row-level filtering
    current_tenant_id.set(tenant_id)
    return tenant_id


def require_tenant(request: Request) -> str:
    """Guard — use after authenticate to ensure tenant was actually resolved."""
    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant not resolved",
        )
    return tenant_id
