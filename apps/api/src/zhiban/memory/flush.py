"""Memory Flush: extract stable history into memories before compaction."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.db.models import Conversation, Message
from zhiban.llm.base import LLMAdapter
from zhiban.memory.extractor import EXTRACTOR_VERSION, detect_explicit_request, extract_candidates
from zhiban.memory.schemas import MemoryCandidatePayload
from zhiban.memory.service import MemoryService


async def flush_conversation_memory(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    llm: LLMAdapter,
) -> bool:
    """Extract memories from messages after the flush cursor.

    Returns True on success (cursor advanced or nothing to do); False on failure.
    """
    conv = (
        await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.status != "deleted",
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        return True

    # Load user messages after the flush cursor (or all if none).
    query = select(Message).where(
        Message.conversation_id == conversation_id,
        Message.user_id == user_id,
        Message.role == "user",
        Message.deleted_at.is_(None),
    )
    if conv.memory_flushed_through_message_id is not None:
        query = query.where(
            Message.created_at
            > select(Message.created_at)
            .where(Message.id == conv.memory_flushed_through_message_id)
            .scalar_subquery()
        )
    query = query.order_by(Message.created_at.asc()).limit(20)
    messages = list((await session.execute(query)).scalars())

    if not messages:
        return True

    # Extract candidates from user messages. Skip messages that are explicit
    # "remember this" requests: those are already handled synchronously by the
    # MemoryAgent via the memory.add tool, so re-extracting them here would
    # produce a duplicate (implicit copy) of the same fact.
    indexed = [
        (i, m.content)
        for i, m in enumerate(messages)
        if not detect_explicit_request(m.content)
    ]
    if not indexed:
        # Nothing to implicitly extract, but still advance the cursor.
        conv.memory_flushed_through_message_id = messages[-1].id
        await session.commit()
        return True
    try:
        candidates = await extract_candidates(llm, indexed)
    except Exception:  # noqa: BLE001 - flush is best-effort
        return False

    # Map message index back to message id.
    id_by_index = {i: m.id for i, m in enumerate(messages)}
    text_by_id = {m.id: m.content for m in messages}

    service = MemoryService(session)
    for candidate in candidates:
        # Map the LLM's batch-local integer indices back to real message UUIDs.
        source_ids: list[uuid.UUID] = []
        for i in candidate.source_message_ids:
            sid = id_by_index.get(int(i))
            if sid is not None:
                source_ids.append(sid)
        if not source_ids:
            continue
        # Rebuild a fully-validated payload with UUID source_message_ids.
        payload = MemoryCandidatePayload(
            memory_type=candidate.memory_type,
            category=candidate.category,
            fact=candidate.fact,
            subject=candidate.subject,
            predicate=candidate.predicate,
            value=candidate.value,
            negated=candidate.negated,
            source_message_ids=source_ids,
            evidence_quote=candidate.evidence_quote,
            confidence=candidate.confidence,
            importance=candidate.importance,
            valid_until=datetime.fromisoformat(candidate.valid_until)
            if candidate.valid_until
            else None,
        )
        # Determine source kind per candidate is not straightforward here;
        # use implicit (extraction context) by default.
        await service.process_candidate(
            user_id=user_id,
            candidate=payload,
            source_kind="implicit",
            extractor_version=EXTRACTOR_VERSION,
            available_message_ids=set(text_by_id.keys()),
            available_message_texts=text_by_id,
        )

    # Advance the flush cursor to the last processed message.
    conv.memory_flushed_through_message_id = messages[-1].id
    await session.commit()
    return True
