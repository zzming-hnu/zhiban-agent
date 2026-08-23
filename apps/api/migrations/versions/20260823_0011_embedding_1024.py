"""Change memories.embedding dimension from 1536 to 1024.

The default embedding model was OpenAI's text-embedding-3-small (1536 dims).
We now use BAAI/bge-m3 via SiliconFlow (1024 dims), so the vector column must
match the embedding dimension.

Revision ID: 20260823_0011
Revises: 20260820_0010
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260823_0011"
down_revision: str | Sequence[str] | None = "20260820_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the HNSW index first: it uses vector_cosine_ops which requires a
    # fixed dimension, and cannot survive an ALTER COLUMN of the vector dims.
    op.drop_index(
        "ix_memories_embedding",
        table_name="memories",
        postgresql_using="hnsw",
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )

    # Change the column type from vector(1536) to vector(1024).
    op.alter_column(
        "memories",
        "embedding",
        type_=Vector(1024),
        existing_type=Vector(1536),
        nullable=True,
    )

    # Recreate the HNSW index with the new dimension.
    op.create_index(
        "ix_memories_embedding",
        "memories",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_memories_embedding",
        table_name="memories",
        postgresql_using="hnsw",
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )
    op.alter_column(
        "memories",
        "embedding",
        type_=Vector(1536),
        existing_type=Vector(1024),
        nullable=True,
    )
    op.create_index(
        "ix_memories_embedding",
        "memories",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )
