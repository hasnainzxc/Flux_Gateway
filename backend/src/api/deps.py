from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.oidc import decode_access_token
from src.core.tenant import current_tenant_id
from src.db.models import ApiKey
from src.db.session import get_db

security_scheme = HTTPBearer(auto_error=False)

_oidc_provider: Callable[..., object] | None = None


def set_oidc_provider(provider: Callable[..., object]) -> None:
    global _oidc_provider
    _oidc_provider = provider


async def authenticate(
    request: Request,
    session: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),  # noqa: B008
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    token = credentials.credentials

    if token.startswith("sk-"):
        return await _auth_api_key(token, session, request)
    else:
        return _auth_jwt(token, request)


async def _auth_api_key(raw_key: str, session: AsyncSession, request: Request) -> str:
    from hashlib import sha256

    key_hash = sha256(raw_key.encode()).hexdigest()

    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )

    tenant_id = str(api_key.tenant_id)
    current_tenant_id.set(tenant_id)
    return tenant_id


def _auth_jwt(token: str, request: Request) -> str:
    payload = decode_access_token(token)
    tenant_id: str = payload["tenant_id"]
    current_tenant_id.set(tenant_id)
    return tenant_id


def require_tenant(request: Request) -> str:
    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant not resolved",
        )
    return tenant_id
