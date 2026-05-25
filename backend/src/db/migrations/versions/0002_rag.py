from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002_rag"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("connection_id", sa.UUID(), sa.ForeignKey("connections.id"), nullable=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), default="uploading"),
        sa.Column("chunk_count", sa.Integer(), default=0),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("token_count", sa.Integer(), default=0),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "citations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("chunk_id", sa.UUID(), sa.ForeignKey("chunks.id"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("query_id", sa.UUID(), nullable=True),
        sa.Column("relevance_score", sa.Float(), default=0.0),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_index("idx_documents_tenant", "documents", ["tenant_id"])
    op.create_index("idx_chunks_document", "chunks", ["document_id"])
    op.create_index("idx_chunks_tenant", "chunks", ["tenant_id"])
    op.create_index("idx_citations_chunk", "citations", ["chunk_id"])
    op.create_index("idx_citations_tenant", "citations", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("citations")
    op.drop_table("chunks")
    op.drop_table("documents")
