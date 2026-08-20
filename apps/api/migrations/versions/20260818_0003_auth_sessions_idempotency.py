"""Add auth_sessions, idempotency_records; extend users/conversations/messages.

Revision ID: 20260818_0003
Revises: 20260817_0002
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "20260818_0003"
down_revision: str | Sequence[str] | None = "20260817_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users: extend ---
    op.add_column(
        "users", sa.Column("locale", sa.String(20), nullable=False, server_default="zh-CN")
    )
    op.add_column(
        "users", sa.Column("settings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    )
    op.add_column(
        "users",
        sa.Column("privacy_settings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    user_status = postgresql.ENUM(
        "active", "deleting", "deleted", name="user_status", create_type=False
    )
    op.execute("CREATE TYPE user_status AS ENUM ('active', 'deleting', 'deleted')")
    op.add_column(
        "users",
        sa.Column("status", user_status, nullable=False, server_default="active"),
    )

    # --- conversations: extend ---
    op.add_column(
        "conversations", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "conversations", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "conversations", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )

    # --- messages: extend ---
    op.add_column("messages", sa.Column("client_message_id", sa.String(128), nullable=True))
    op.add_column("messages", sa.Column("parent_message_id", UUID(as_uuid=True), nullable=True))
    op.add_column("messages", sa.Column("token_count", sa.Integer(), nullable=True))
    op.add_column(
        "messages",
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "messages",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.add_column("messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_messages_client_id",
        "messages",
        ["conversation_id", "client_message_id"],
    )

    # --- auth_sessions ---
    op.create_table(
        "auth_sessions",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("refresh_token_hash", sa.String(255), nullable=False, index=True),
        sa.Column("user_agent_hash", sa.String(255), nullable=True),
        sa.Column("ip_prefix", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # --- idempotency_records ---
    op.create_table(
        "idempotency_records",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("route", sa.String(255), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", JSONB, nullable=True),
        sa.Column(
            "state",
            sa.Enum("processing", "completed", name="idempotency_state"),
            nullable=False,
            server_default="processing",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_idempotency_scope",
        "idempotency_records",
        ["user_id", "method", "route", "key"],
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.execute("DROP TYPE IF EXISTS idempotency_state")

    op.drop_table("auth_sessions")

    op.drop_constraint("uq_messages_client_id", "messages", type_="unique")
    op.drop_column("messages", "deleted_at")
    op.drop_column("messages", "updated_at")
    op.drop_column("messages", "metadata")
    op.drop_column("messages", "token_count")
    op.drop_column("messages", "parent_message_id")
    op.drop_column("messages", "client_message_id")

    op.drop_column("conversations", "deleted_at")
    op.drop_column("conversations", "archived_at")
    op.drop_column("conversations", "version")

    op.drop_column("users", "status")
    op.execute("DROP TYPE IF EXISTS user_status")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "privacy_settings")
    op.drop_column("users", "settings")
    op.drop_column("users", "locale")
