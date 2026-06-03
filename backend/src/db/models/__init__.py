"""
Core SQLAlchemy ORM models — Tenant, User, ApiKey, Connection, SchemaCache, Credential.
RAG + event models imported at bottom to avoid circular refs.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    """Top-level org. Every other entity belongs to a tenant via FK."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # slug = URL-friendly org identifier, auto-derived from email on first login
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    users: Mapped[list[User]] = relationship(back_populates="tenant")
    api_keys: Mapped[list[ApiKey]] = relationship(back_populates="tenant")
    connections: Mapped[list[Connection]] = relationship(back_populates="tenant")


class User(Base):
    """User within a tenant. Linked to OIDC provider via oidc_sub."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    oidc_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class ApiKey(Base):
    """API key for programmatic access. Stores SHA-256 hash, never the raw key."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # key_hash = SHA-256(raw_key) — lookup on auth, never expose raw after creation
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # key_prefix = first 8 chars of raw key (e.g. "sk-a1b2c") for UI display
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="api_keys")


class Connection(Base):
    """External DB connection config. Connection string stored Fernet-encrypted."""

    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    db_type: Mapped[str] = mapped_column(String(50), nullable=False)  # currently only "postgresql"
    # Fernet-encrypted bytes — decrypt via src.core.security.decrypt_value
    encrypted_connection_string: Mapped[bytes] = mapped_column(nullable=False)
    # disconnected|connected|error
    status: Mapped[str] = mapped_column(String(50), default="disconnected")
    last_reflected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="connections")
    schema_cache: Mapped[list[SchemaCache]] = relationship(back_populates="connection")


class SchemaCache(Base):
    """Persisted schema snapshot for a connection. JSON blob, versioned."""

    __tablename__ = "schema_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connections.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    # JSON string of full schema graph (tables, columns, FKs, indexes) — see schema_reflection.py
    schema_graph: Mapped[str] = mapped_column(Text, nullable=False)
    # version = unix timestamp of reflection time, used for cache invalidation
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    connection: Mapped[Connection] = relationship(back_populates="schema_cache")


class Credential(Base):
    """Encrypted credential store (OAuth tokens, API keys for 3rd-party services)."""

    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    # e.g. "github", "stripe"
    service_type: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(nullable=False)  # Fernet-encrypted blob
    # key_version supports future key rotation — decrypt with matching version
    key_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Bottom-of-file imports to avoid circular refs — these models depend on Base above.
# Re-exported so `from src.db.models import Chunk` works everywhere.
from src.db.models.chunk import Chunk as Chunk  # noqa: E402
from src.db.models.citation import Citation as Citation  # noqa: E402
from src.db.models.document import Document as Document  # noqa: E402
from src.db.models.event import BehaviorRule as BehaviorRule  # noqa: E402
from src.db.models.event import EventLog as EventLog  # noqa: E402
from src.db.models.event import UsageRecord as UsageRecord  # noqa: E402
from src.db.models.event import WebhookConfig as WebhookConfig  # noqa: E402
