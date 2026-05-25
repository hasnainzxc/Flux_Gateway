# Schema Autodiscovery Engine

> **Module**: `backend/src/services/schema_reflection.py`  
> **API**: `backend/src/api/v1/schema.py`  
> **Models**: `backend/src/db/models/connection.py`, `schema_cache.py`

## Purpose

Metadata-only DB reflection → localized Dynamic Schema Graph Layer (JSON). Prevents LLM hallucination of column names and catastrophic unindexed table-scan queries.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Client Dashboard                       │
│  [Paste DB Connection String] → [Test Connection]        │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTPS + API Key
                       ▼
┌──────────────────────────────────────────────────────────┐
│              FastAPI Schema Gateway                       │
│  POST /api/v1/connections          Create connection      │
│  POST /api/v1/connections/{id}/reflect  Trigger reflection │
│  GET  /api/v1/connections/{id}/schema    Get cached graph  │
└──────────────────────┬───────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐     ┌──────────────────────┐
│ Encrypted Store  │     │  Schema Reflection   │
│ (AES-256-GCM)    │     │  Service             │
│                  │     │                      │
│ Connection       │     │  ┌────────────────┐  │
│ string encrypted │     │  │ Read-only      │  │
│ at rest          │     │  │ connection     │  │
│                  │     │  │ to target DB   │  │
└──────────────────┘     │  └────────┬───────┘  │
                         │           ▼          │
                         │  ┌────────────────┐  │
                         │  │ Query          │  │
                         │  │ information_   │  │
                         │  │ schema (meta   │  │
                         │  │ only, no rows) │  │
                         │  └────────┬───────┘  │
                         │           ▼          │
                         │  ┌────────────────┐  │
                         │  │ Build JSON     │  │
                         │  │ Metadata Graph │  │
                         │  └────────┬───────┘  │
                         │           ▼          │
                         └───────────┬──────────┘
                                     │
                                     ▼
                         ┌──────────────────────┐
                         │  Redis Schema Cache  │
                         │  Key: tenant:{id}:   │
                         │  schema:{conn_id}    │
                         │  TTL: 1 hour         │
                         └──────────────────────┘
```

## JSON Schema Graph Format

```json
{
  "db_type": "postgresql",
  "db_version": "16.3",
  "reflected_at": "2026-05-25T10:30:00Z",
  "schema_version": 1,
  "tables": [
    {
      "name": "orders",
      "schema": "public",
      "columns": [
        {
          "name": "id",
          "data_type": "integer",
          "nullable": false,
          "is_primary_key": true,
          "default": "nextval('orders_id_seq')",
          "foreign_key": null
        },
        {
          "name": "customer_id",
          "data_type": "integer",
          "nullable": false,
          "is_primary_key": false,
          "default": null,
          "foreign_key": {
            "table": "customers",
            "column": "id",
            "constraint_name": "fk_orders_customer"
          }
        },
        {
          "name": "total_amount",
          "data_type": "numeric(10,2)",
          "nullable": false,
          "is_primary_key": false,
          "default": null,
          "foreign_key": null
        },
        {
          "name": "status",
          "data_type": "varchar(50)",
          "nullable": false,
          "is_primary_key": false,
          "default": "'pending'::character varying",
          "foreign_key": null
        },
        {
          "name": "created_at",
          "data_type": "timestamp with time zone",
          "nullable": false,
          "is_primary_key": false,
          "default": "now()",
          "foreign_key": null
        }
      ],
      "indexes": [
        {
          "name": "idx_orders_customer_id",
          "columns": ["customer_id"],
          "unique": false
        },
        {
          "name": "idx_orders_status",
          "columns": ["status"],
          "unique": false
        }
      ],
      "row_count_estimate": 150000,
      "table_size_bytes": 15728640
    }
  ],
  "relationships": [
    {
      "from_table": "orders",
      "from_column": "customer_id",
      "to_table": "customers",
      "to_column": "id",
      "constraint_name": "fk_orders_customer"
    }
  ]
}
```

## Reflection Query (PostgreSQL)

```sql
-- Tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE';

-- Columns per table
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default,
    character_maximum_length,
    numeric_precision,
    numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = :table_name
ORDER BY ordinal_position;

-- Primary keys
SELECT kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'PRIMARY KEY'
  AND tc.table_schema = 'public'
  AND tc.table_name = :table_name;

-- Foreign keys
SELECT
    kcu.column_name AS from_column,
    ccu.table_name AS to_table,
    ccu.column_name AS to_column,
    tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
    ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
  AND tc.table_name = :table_name;

-- Indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = :table_name;

-- Row estimates (for query planning)
SELECT
    reltuples::bigint AS estimated_rows,
    pg_total_relation_size(quote_ident(:table_name)) AS total_bytes
FROM pg_class
WHERE relname = :table_name;
```

## Security Constraints

1. **Read-only connection**: Reflection service uses a separate DB connection with SELECT-only permissions. Never executes writes.
2. **Metadata only**: Queries `information_schema` and `pg_catalog`. Never touches user tables/rows.
3. **Encrypted storage**: Connection strings encrypted with AES-256-GCM before storage. Decryption key in env var, never in code.
4. **Tenant isolation**: Connection belongs to tenant. All schema cache queries include `WHERE tenant_id = :tenant_id`.

## Cache Invalidation

- TTL: 1 hour default (configurable)
- Manual refresh via API endpoint
- Webhook-triggered refresh (client can POST to `/api/v1/connections/{id}/refresh` on schema migration)
- Version number increments on each reflection → agent can detect stale schema

## AI Integration

When agent needs to generate SQL:
1. Fetch cached schema graph for tenant's connection
2. Inject graph as structured system prompt context:
   ```
   You have access to the following database schema:
   {json.dumps(schema_graph, indent=2)}
   
   Generate SQL queries using ONLY the table and column names provided above.
   Do NOT invent column names. Reference relationships via foreign keys listed.
   ```
3. Coder Node generates SQL using exact names from graph
4. Reviewer Node validates generated SQL against graph (column existence, FK validity)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/connections` | Store new DB connection (encrypted) |
| GET | `/api/v1/connections` | List tenant's connections |
| GET | `/api/v1/connections/{id}` | Get connection details (without connection string) |
| DELETE | `/api/v1/connections/{id}` | Remove connection |
| POST | `/api/v1/connections/{id}/reflect` | Trigger schema reflection |
| GET | `/api/v1/connections/{id}/schema` | Get cached schema graph |
| POST | `/api/v1/connections/{id}/test` | Test connection (no reflection) |

## Future Enhancements (Post-MVP)

- MySQL/MariaDB support (different `information_schema` queries)
- MongoDB schema inference (sampling-based)
- REST API schema discovery (OpenAPI/Swagger parsing)
- Schema diff detection (compare versions, alert on changes)
- Auto-generated ERD visualization in dashboard
