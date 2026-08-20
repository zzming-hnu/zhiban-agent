"""Add memory_flushed_through_message_id cursor to conversations.

Revision ID: 20260819_0006
Revises: 20260819_0005
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260819_0006"
down_revision: str | Sequence[str] | None = "20260819_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("memory_flushed_through_message_id", UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "memory_flushed_through_message_id")
