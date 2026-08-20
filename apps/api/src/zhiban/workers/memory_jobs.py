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
