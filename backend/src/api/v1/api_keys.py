"""API key CRUD — generate, list, revoke. Raw key shown only once on create."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import require_tenant
from src.db.models import ApiKey
from src.db.session import get_db

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: str | None
    expires_at: str | None
    created_at: str


class ApiKeyCreateResponse(ApiKeyResponse):
    raw_key: str


@router.get("/", response_model=list[ApiKeyResponse])
async def list_api_keys(
    session: AsyncSession = Depends(get_db),
    _tenant: str = Depends(require_tenant),
) -> list[ApiKeyResponse]:
    result = await session.execute(
        select(ApiKey).order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        ApiKeyResponse(
            id=str(k.id),
            name=k.name,
            key_prefix=k.key_prefix,
            is_active=k.is_active,
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            created_at=k.created_at.isoformat() if k.created_at else "",
        )
        for k in keys
    ]


@router.post("/", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    session: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(require_tenant),
) -> ApiKeyCreateResponse:
    from hashlib import sha256

    # Generate 64-char hex key with sk- prefix (e.g. sk-a1b2c3d4...)
    raw_key = f"sk-{secrets.token_hex(32)}"
    key_hash = sha256(raw_key.encode()).hexdigest()  # store hash, never the raw key
    key_prefix = raw_key[:10]  # first 10 chars for UI display ("sk-a1b2c3d4")

    expires_at = None
    if payload.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=payload.expires_in_days)

    api_key = ApiKey(
        tenant_id=uuid.UUID(tenant_id),
        name=payload.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    return ApiKeyCreateResponse(
        id=str(api_key.id),
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        last_used_at=None,
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
        created_at=api_key.created_at.isoformat() if api_key.created_at else "",
        raw_key=raw_key,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _tenant: str = Depends(require_tenant),
) -> None:
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    # Soft-delete: mark inactive rather than hard delete — preserves audit trail
    api_key.is_active = False
    await session.commit()
