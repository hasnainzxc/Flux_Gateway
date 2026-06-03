"""
Automatic row-level tenant isolation via SQLAlchemy ORM hooks.
Intercepts all SELECT queries on tenant-aware tables and injects WHERE tenant_id = <current>.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from src.core.tenant import current_tenant_id

# Tables that must be filtered by tenant_id automatically.
# Add new tenant-scoped tables here or they'll leak cross-tenant data.
# NOTE: documents, chunks, citations, event_log, behavior_rules, webhook_configs,
# usage_records are NOT in this set — they filter explicitly in queries.
TENANT_AWARE_TABLES = {"api_keys", "connections", "schema_cache", "credentials"}


@event.listens_for(Session, "do_orm_execute")
def inject_tenant_filter(orm_execute_state: Any) -> None:
    """
    Hook into every ORM SELECT. If a tenant context is set and the query
    touches a tenant-aware table, auto-append WHERE tenant_id = <current_tenant>.
    Skips if no tenant set (e.g., system-level queries, migrations).
    """
    if orm_execute_state.is_select:
        tenant_id = current_tenant_id.get()
        if tenant_id is None:
            return

        statement: Select[Any] = orm_execute_state.statement
        for table in statement.froms:
            table_name = getattr(table, "name", None)
            if table_name is not None and table_name in TENANT_AWARE_TABLES:
                orm_execute_state.statement = statement.where(
                    table.c.tenant_id == tenant_id
                )
