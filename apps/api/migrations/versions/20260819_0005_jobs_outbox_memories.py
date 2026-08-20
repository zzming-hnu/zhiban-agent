"""Add jobs, outbox_events, memories, and memory_candidates tables.

Revision ID: 20260819_0005
Revises: 20260818_0004
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "20260819_0005"
down_revision: str | Sequence[str] | None = "20260818_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_pk() -> list[sa.Column]:
    return [
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        )
    ]


def upgrade() -> None:
    # --- jobs ---
    op.create_table(
        "jobs",
        *_uuid_pk(),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True, index=True
        ),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "succeeded", "failed", "dead", name="job_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("lease_owner", sa.String(64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_summary", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_jobs_idempotency", "jobs", ["job_type", "idempotency_key"], unique=True)
    op.create_index(
        "ix_jobs_claim",
        "jobs",
        ["priority", "available_at", "id"],
        postgresql_where=sa.text("status IN ('pending', 'failed')"),
    )

    # --- outbox_events ---
    op.create_table(
        "outbox_events",
        *_uuid_pk(),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True, index=True
        ),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False, unique=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "sending", "sent", "failed", "dead", name="outbox_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_pending",
        "outbox_events",
        ["available_at", "id"],
        postgresql_where=sa.text("status IN ('pending', 'failed')"),
    )

    # --- memories ---
    op.create_table(
        "memories",
        *_uuid_pk(),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("memory_type", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(80), nullable=False),
        sa.Column("predicate", sa.String(80), nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False, server_default="explicit"),
        sa.Column(
            "status",
            sa.Enum("active", "superseded", "deleted", "expired", name="memory_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("importance", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("conflict_key", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("source_message_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("evidence_quote", sa.Text, nullable=False, server_default=""),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_evidenced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieval_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("superseded_by_id", UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_memories_active_fingerprint",
        "memories",
        ["user_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_memories_user_type_status", "memories", ["user_id", "memory_type", "status"]
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
    op.create_index(
        "ix_memories_expiry",
        "memories",
        ["user_id", "expires_at"],
        postgresql_where=sa.text("status = 'active' AND expires_at IS NOT NULL"),
    )

    # --- memory_candidates ---
    op.create_table(
        "memory_candidates",
        *_uuid_pk(),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column(
            "conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True
        ),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("source_message_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("extractor_version", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "accepted",
                "rejected",
                "failed_retryable",
                "dead",
                name="candidate_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("reject_reason", sa.String(64), nullable=True),
        sa.Column("target_memory_id", UUID(as_uuid=True), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_memory_candidates_idempotency",
        "memory_candidates",
        ["user_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_memory_candidates_pending",
        "memory_candidates",
        ["status", "created_at"],
        postgresql_where=sa.text("status IN ('pending', 'failed_retryable')"),
    )


def downgrade() -> None:
    op.drop_table("memory_candidates")
    op.drop_table("memories")
    op.drop_table("outbox_events")
    op.drop_table("jobs")
    op.execute("DROP TYPE IF EXISTS candidate_status")
    op.execute("DROP TYPE IF EXISTS memory_status")
    op.execute("DROP TYPE IF EXISTS outbox_status")
    op.execute("DROP TYPE IF EXISTS job_status")
