"""Migration 0003: Event gateway tables — webhooks, behavior rules, event log, usage records."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003_event_gateway"
down_revision: str | None = "0002_rag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_configs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hook_id", sa.String(64), unique=True, nullable=False),
        sa.Column("secret", sa.String(255), nullable=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "behavior_rules",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("conditions", JSONB, nullable=False, server_default="{}"),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("action_config", JSONB, nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer(), default=50),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "event_log",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("hook_id", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("matched_rules", sa.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer(), default=50),
        sa.Column("status", sa.String(50), default="queued"),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "usage_records",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tokens_input", sa.BigInteger(), default=0),
        sa.Column("tokens_output", sa.BigInteger(), default=0),
        sa.Column("agent_runs", sa.Integer(), default=0),
        sa.Column("webhook_events", sa.Integer(), default=0),
        sa.Column("sandbox_executions", sa.Integer(), default=0),
        sa.Column("rag_queries", sa.Integer(), default=0),
        sa.Column("storage_bytes", sa.BigInteger(), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("idx_webhook_configs_tenant", "webhook_configs", ["tenant_id"])
    op.create_index("idx_webhook_configs_hook_id", "webhook_configs", ["hook_id"])
    op.create_index("idx_behavior_rules_tenant", "behavior_rules", ["tenant_id"])
    op.create_index("idx_behavior_rules_event_type", "behavior_rules", ["event_type"])
    op.create_index("idx_event_log_tenant_status", "event_log", ["tenant_id", "status"])
    op.create_index("idx_event_log_tenant_created", "event_log", ["tenant_id", "created_at"])
    op.create_index(
        "idx_usage_records_tenant_period", "usage_records", ["tenant_id", "period_start"]
    )


def downgrade() -> None:
    op.drop_table("usage_records")
    op.drop_table("event_log")
    op.drop_table("behavior_rules")
    op.drop_table("webhook_configs")
