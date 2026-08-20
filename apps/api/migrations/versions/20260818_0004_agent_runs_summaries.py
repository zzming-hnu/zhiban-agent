"""Add agent_runs and conversation_summaries tables.

Revision ID: 20260818_0004
Revises: 20260818_0003
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "20260818_0004"
down_revision: str | Sequence[str] | None = "20260818_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False
        ),
        sa.Column(
            "assistant_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "waiting_confirmation",
                "completed",
                "failed",
                "cancelled",
                name="run_status",
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("route", sa.String(32), nullable=True),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("tool_rounds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # At most one active run per conversation.
    op.create_index(
        "uq_agent_runs_active_conversation",
        "agent_runs",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'waiting_confirmation')"),
    )

    op.create_table(
        "conversation_summaries",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "from_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False
        ),
        sa.Column(
            "through_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False
        ),
        sa.Column("summary", JSONB, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("conversation_summaries")
    op.drop_table("agent_runs")
    op.execute("DROP TYPE IF EXISTS run_status")
