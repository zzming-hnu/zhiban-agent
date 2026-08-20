"""Add todos and reminders tables.

Revision ID: 20260819_0008
Revises: 20260819_0007
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260819_0008"
down_revision: str | Sequence[str] | None = "20260819_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_pk() -> list[sa.Column]:
    return [
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        )
    ]


def upgrade() -> None:
    op.create_table(
        "todos",
        *_uuid_pk(),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("detail", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.Enum("pending", "done", "cancelled", name="todo_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("priority", sa.Integer, nullable=False, server_default="1"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_todos_user_status_due",
        "todos",
        ["user_id", "status", "due_at", "id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "reminders",
        *_uuid_pk(),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("todo_id", UUID(as_uuid=True), sa.ForeignKey("todos.id"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Shanghai"),
        sa.Column(
            "status",
            sa.Enum("scheduled", "delivering", "delivered", "cancelled", name="reminder_status"),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("delivery_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("dedupe_key", sa.String(64), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_reminders_dedupe",
        "reminders",
        ["user_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_reminders_due",
        "reminders",
        ["status", "remind_at", "id"],
        postgresql_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("reminders")
    op.drop_table("todos")
    op.execute("DROP TYPE IF EXISTS reminder_status")
    op.execute("DROP TYPE IF EXISTS todo_status")
