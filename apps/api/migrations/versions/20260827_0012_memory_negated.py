"""Add memories.negated column for explicit negation handling.

A negated memory ("does NOT like spicy") previously had to fold the negation
into the predicate ("不喜欢") or value ("不吃辣"), which made slot-conflict
detection (type+subject+predicate) miss the relationship between a fact and
its negation. A dedicated ``negated`` boolean keeps the predicate stable
("喜欢") so that "喜欢 吃辣" and "不喜欢 吃辣" share the same conflict slot.

Revision ID: 20260827_0012
Revises: 20260823_0011
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0012"
down_revision: str | Sequence[str] | None = "20260823_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memories",
        sa.Column("negated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("memories", "negated")
