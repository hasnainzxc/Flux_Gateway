"""Migration 0001: Core tables — tenants, users, api_keys, connections, schema_cache."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None  # first migration, no parent
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(320), unique=True, nullable=False),
        sa.Column("oidc_sub", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "connections",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("db_type", sa.String(50), nullable=False),
        sa.Column("encrypted_connection_string", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(50), default="disconnected"),
        sa.Column("last_reflected_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "schema_cache",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("connection_id", sa.UUID(), sa.ForeignKey("connections.id"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("schema_graph", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "credentials",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("service_type", sa.String(100), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    # Indexes for hot lookup paths — key_hash for API key auth, tenant_id for row-level isolation
    op.create_index("idx_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("idx_connections_tenant", "connections", ["tenant_id"])
    op.create_index("idx_schema_cache_connection", "schema_cache", ["connection_id"])
    op.create_index("idx_credentials_tenant", "credentials", ["tenant_id"])


def downgrade() -> None:
    # Drop in reverse FK-dependency order to avoid constraint violations
    op.drop_table("credentials")
    op.drop_table("schema_cache")
    op.drop_table("connections")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("tenants")
