"""Connection CRUD — manage external DB connections. Passwords encrypted at rest."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import authenticate, require_tenant
from src.core.security import encrypt_value
from src.db.models import Connection
from src.db.session import get_db

router = APIRouter(prefix="/connections", tags=["connections"])


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    db_type: str = Field(default="postgresql")
    host: str
    port: int = 5432
    database: str
    username: str
    password: str


class ConnectionResponse(BaseModel):
    id: str
    name: str
    db_type: str
    status: str
    last_reflected_at: str | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[ConnectionResponse])
async def list_connections(
    session: AsyncSession = Depends(get_db),
    _auth: str = Depends(authenticate),
    _tenant: str = Depends(require_tenant),
) -> list[ConnectionResponse]:
    result = await session.execute(select(Connection).order_by(Connection.created_at.desc()))
    connections = result.scalars().all()
    return [
        ConnectionResponse(
            id=str(c.id),
            name=c.name,
            db_type=c.db_type,
            status=c.status,
            last_reflected_at=c.last_reflected_at.isoformat() if c.last_reflected_at else None,
            created_at=c.created_at.isoformat() if c.created_at else "",
            updated_at=c.updated_at.isoformat() if c.updated_at else "",
        )
        for c in connections
    ]


@router.post("/", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    payload: ConnectionCreate,
    session: AsyncSession = Depends(get_db),
    _auth: str = Depends(authenticate),
    tenant_id: str = Depends(require_tenant),
) -> ConnectionResponse:
    # Build DSN from individual fields — password embedded in URL
    conn_string = (
        f"postgresql://{payload.username}:{payload.password}"
        f"@{payload.host}:{payload.port}/{payload.database}"
    )
    # Fernet-encrypt the full connection string before persisting
    encrypted = encrypt_value(conn_string)

    connection = Connection(
        tenant_id=uuid.UUID(tenant_id),
        name=payload.name,
        db_type=payload.db_type,
        encrypted_connection_string=encrypted,
    )
    session.add(connection)
    await session.commit()
    await session.refresh(connection)

    return ConnectionResponse(
        id=str(connection.id),
        name=connection.name,
        db_type=connection.db_type,
        status=connection.status,
        last_reflected_at=None,
        created_at=connection.created_at.isoformat() if connection.created_at else "",
        updated_at=connection.updated_at.isoformat() if connection.updated_at else "",
    )


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    connection_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _auth: str = Depends(authenticate),
    _tenant: str = Depends(require_tenant),
) -> ConnectionResponse:
    result = await session.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    return ConnectionResponse(
        id=str(connection.id),
        name=connection.name,
        db_type=connection.db_type,
        status=connection.status,
        last_reflected_at=(
            connection.last_reflected_at.isoformat()
            if connection.last_reflected_at
            else None
        ),
        created_at=connection.created_at.isoformat() if connection.created_at else "",
        updated_at=connection.updated_at.isoformat() if connection.updated_at else "",
    )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _auth: str = Depends(authenticate),
    _tenant: str = Depends(require_tenant),
) -> None:
    result = await session.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    await session.delete(connection)
    await session.commit()
