"""Add recurrence fields to reminders for recurring reminders.

Revision ID: 20260820_0010
Revises: 20260819_0009
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0010"
down_revision: str | Sequence[str] | None = "20260819_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reminders",
        sa.Column(
            "recurrence",
            sa.String(16),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "reminders",
        sa.Column("recurrence_end_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reminders", "recurrence_end_at")
    op.drop_column("reminders", "recurrence")
