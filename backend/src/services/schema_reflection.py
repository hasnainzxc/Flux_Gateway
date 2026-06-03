"""Schema reflection service — introspect PostgreSQL databases via information_schema + pg_catalog."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog

from src.core.security import decrypt_value

logger = structlog.get_logger(__name__)


class SchemaReflectionService:
    """
    Connects to external PostgreSQL databases and extracts full schema metadata:
    tables, columns, primary keys, foreign keys, indexes, row counts, sizes.
    """

    def __init__(self, connection_string: str):
        self._dsn = connection_string

    async def reflect(self) -> dict[str, Any]:
        """
        Full schema introspection. Returns structured graph with tables, relationships, metadata.
        Used by agent for SQL generation + validation.
        """
        # Connect directly to external DB — no connection pooling (one-shot reflection)
        conn = await asyncpg.connect(self._dsn)

        try:
            # Parallel-ish: each query is independent, but asyncpg is single-conn
            tables = await self._reflect_tables(conn)
            rows = await self._reflect_columns(conn)
            pks = await self._reflect_primary_keys(conn)
            fks = await self._reflect_foreign_keys(conn)
            indexes = await self._reflect_indexes(conn)
            version_info = await conn.fetchrow("SELECT version()")  # PostgreSQL version string

            # Build column metadata grouped by table — enriched with PK/FK info below
            columns_by_table: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                tname = row["table_name"]
                columns_by_table.setdefault(tname, []).append({
                    "name": row["column_name"],
                    "data_type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                    "default": row["column_default"],
                    "max_length": row["character_maximum_length"],
                    "numeric_precision": row["numeric_precision"],
                    "numeric_scale": row["numeric_scale"],
                    "is_primary_key": False,  # enriched below from PK query
                    "foreign_key": None,  # enriched below from FK query
                })

            pk_columns: dict[str, set[str]] = {}
            for row in pks:
                pk_columns.setdefault(row["table_name"], set()).add(row["column_name"])

            for tname, cols in columns_by_table.items():
                for col in cols:
                    if col["name"] in pk_columns.get(tname, set()):
                        col["is_primary_key"] = True

            relationships: list[dict[str, str]] = []
            for row in fks:
                tname = row["table_name"]
                colname = row["column_name"]
                relationships.append({
                    "from_table": tname,
                    "from_column": colname,
                    "to_table": row["foreign_table_name"],
                    "to_column": row["foreign_column_name"],
                    "constraint_name": row["constraint_name"],
                })
                if tname in columns_by_table:
                    for col in columns_by_table[tname]:
                        if col["name"] == colname:
                            col["foreign_key"] = {
                                "table": row["foreign_table_name"],
                                "column": row["foreign_column_name"],
                                "constraint_name": row["constraint_name"],
                            }

            table_graphs: list[dict[str, Any]] = []
            for row in tables:
                tname = row["table_name"]
                table_graphs.append({
                    "name": tname,
                    "schema": row["table_schema"],
                    "columns": columns_by_table.get(tname, []),
                    "indexes": [
                        {
                            "name": idx["indexname"],
                            "columns": idx["indexdef"],
                            "unique": idx.get("unique", False),
                        }
                        for idx in indexes
                        if idx["tablename"] == tname
                    ],
                    "row_count_estimate": row.get("row_estimate"),
                    "table_size_bytes": row.get("table_size_bytes"),
                })

            return {
                "db_type": "postgresql",
                "db_version": version_info[0] if version_info else "unknown",
                "reflected_at": datetime.now(UTC).isoformat(),
                "schema_version": int(datetime.now(UTC).timestamp()),
                "tables": table_graphs,
                "relationships": relationships,
            }
        finally:
            await conn.close()

    async def test_connection(self) -> bool:
        """Quick connectivity test — SELECT 1 with 10s timeout."""
        try:
            conn = await asyncpg.connect(self._dsn, timeout=10)
            await conn.execute("SELECT 1")
            await conn.close()
            return True
        except Exception:
            return False

    async def _reflect_tables(self, conn: asyncpg.Connection) -> list[Any]:
        query = """
            SELECT
                t.table_name,
                t.table_schema,
                s.n_live_tup AS row_estimate,
                pg_total_relation_size(
                    quote_ident(t.table_schema)
                    || '.' || quote_ident(t.table_name)
                ) AS table_size_bytes
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s
                ON s.schemaname = t.table_schema AND s.relname = t.table_name
            WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
              AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
        """
        return await conn.fetch(query)  # type: ignore[no-any-return]

    async def _reflect_columns(self, conn: asyncpg.Connection) -> list[Any]:
        rows = await conn.fetch("""
            SELECT
                table_name,
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_name, ordinal_position
        """)
        return rows  # type: ignore[no-any-return]

    async def _reflect_primary_keys(self, conn: asyncpg.Connection) -> list[Any]:
        rows = await conn.fetch("""
            SELECT
                kcu.table_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY kcu.table_name, kcu.ordinal_position
        """)
        return rows  # type: ignore[no-any-return]

    async def _reflect_foreign_keys(self, conn: asyncpg.Connection) -> list[Any]:
        rows = await conn.fetch("""
            SELECT
                kcu.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY kcu.table_name, kcu.ordinal_position
        """)
        return rows  # type: ignore[no-any-return]

    async def _reflect_indexes(self, conn: asyncpg.Connection) -> list[Any]:
        rows = await conn.fetch("""
            SELECT
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY tablename, indexname
        """)
        return rows  # type: ignore[no-any-return]


async def reflect_schema_for_connection(encrypted_conn_string: bytes) -> dict[str, Any]:
    """Decrypt connection string + run full schema reflection. Raises on decrypt failure."""
    decrypted = decrypt_value(encrypted_conn_string)  # Fernet decrypt — fails if tampered
    service = SchemaReflectionService(decrypted)
    return await service.reflect()


async def test_connection(encrypted_conn_string: bytes) -> bool:
    """Decrypt connection string + test connectivity. Returns False on any error."""
    decrypted = decrypt_value(encrypted_conn_string)
    service = SchemaReflectionService(decrypted)
    return await service.test_connection()
