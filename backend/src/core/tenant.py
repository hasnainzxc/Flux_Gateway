"""Tenant context var — set by auth middleware, read by DB layer for row-level isolation."""

from __future__ import annotations

from contextvars import ContextVar

# Async-safe per-request tenant. Set in deps.authenticate, consumed by tenant_isolation.py
current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)
