"""Add user-facing category column to memories.

Revision ID: 20260819_0007
Revises: 20260819_0006
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0007"
down_revision: str | Sequence[str] | None = "20260819_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memories",
        sa.Column("category", sa.String(32), nullable=False, server_default="other"),
    )


def downgrade() -> None:
    op.drop_column("memories", "category")
