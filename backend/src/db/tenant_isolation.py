from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from src.core.tenant import current_tenant_id

TENANT_AWARE_TABLES = {"api_keys", "connections", "schema_cache", "credentials"}


@event.listens_for(Session, "do_orm_execute")
def inject_tenant_filter(orm_execute_state: Any) -> None:
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
