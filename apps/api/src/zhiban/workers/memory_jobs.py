"""Worker handlers for memory-related background jobs."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.core.config import get_settings
from zhiban.db.models import Job
from zhiban.llm.factory import create_llm_adapter
from zhiban.memory.flush import flush_conversation_memory

logger = structlog.get_logger(__name__)


async def handle_memory_extract(session: AsyncSession, job: Job) -> None:
    """Extract memories for a conversation after a run completes."""
    payload = job.payload
    conversation_id = uuid.UUID(payload["conversation_id"])
    user_id = job.user_id
    if user_id is None:
        raise ValueError("memory.extract job missing user_id")

    settings = get_settings()
    llm = create_llm_adapter(settings)

    ok = await flush_conversation_memory(
        session,
        user_id=user_id,
        conversation_id=conversation_id,
        llm=llm,
    )
    if not ok:
        raise RuntimeError("memory extraction failed (best-effort)")

    await logger.ainfo(
        "memory_extraction_done",
        conversation_id=str(conversation_id),
        user_hash=str(user_id)[:8],
    )

    # Auto-trigger consolidation once the user has accumulated enough memories.
    from zhiban.memory.consolidate import DEFAULT_CONSOLIDATE_THRESHOLD, count_active_memories
    from zhiban.workers.jobs import enqueue_job

    active_count = await count_active_memories(session, user_id=user_id)
    if active_count >= DEFAULT_CONSOLIDATE_THRESHOLD:
        await enqueue_job(
            session,
            user_id=user_id,
            job_type="memory.consolidate",
            payload={},
            # One consolidation per user at a time; the key is stable so we never
            # pile up duplicate consolidate jobs for the same user.
            idempotency_key=f"memconsolidate:{user_id}",
        )
        await session.commit()


async def handle_memory_consolidate(session: AsyncSession, job: Job) -> None:
    """Consolidate a user's memories (dedupe + resolve conflicts)."""
    from zhiban.memory.consolidate import consolidate_memories

    user_id = job.user_id
    if user_id is None:
        raise ValueError("memory.consolidate job missing user_id")

    settings = get_settings()
    llm = create_llm_adapter(settings)

    result = await consolidate_memories(session, user_id=user_id, llm=llm)
    await logger.ainfo(
        "memory_consolidation_done",
        user_hash=str(user_id)[:8],
        superseded=result.superseded,
        reason=result.reason,
    )
