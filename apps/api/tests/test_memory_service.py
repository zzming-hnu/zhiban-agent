"""Integration tests for the memory service (decide + persist + isolate)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.auth.security import hash_password
from zhiban.db.models import User
from zhiban.memory.schemas import MemoryCandidatePayload
from zhiban.memory.service import MemoryService
from zhiban.memory.types import Decision


async def _make_user(session: AsyncSession, email: str) -> User:
    user = User(email=email, password_hash=hash_password("password123"), display_name="x")
    session.add(user)
    await session.flush()
    return user


def _candidate(*, value: str = "少糖咖啡", confidence: float = 0.9) -> MemoryCandidatePayload:
    return MemoryCandidatePayload(
        memory_type="preference",
        subject="self",
        predicate="喜欢",
        value=value,
        source_message_ids=[uuid.uuid4()],
        evidence_quote="我喜欢少糖咖啡",
        confidence=confidence,
        importance=0.7,
    )


@pytest.mark.integration
async def test_process_candidate_adds_memory(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session, f"m-{uuid.uuid4().hex[:8]}@example.com")
    await session.commit()

    mid = uuid.uuid4()
    cand = _candidate()
    cand.source_message_ids = [mid]

    service = MemoryService(session)
    decision, record = await service.process_candidate(
        user_id=user.id,
        candidate=cand,
        source_kind="explicit",
        extractor_version="v1",
        available_message_ids={mid},
        available_message_texts={mid: "我喜欢少糖咖啡"},
    )

    assert decision == Decision.add
    assert record.status == "accepted"

    memories = await service.list_memories(user_id=user.id)
    assert len(memories) == 1
    assert memories[0].memory_type == "preference"
    assert memories[0].value == "少糖咖啡"


@pytest.mark.integration
async def test_duplicate_candidate_is_ignored(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session, f"m-{uuid.uuid4().hex[:8]}@example.com")
    await session.commit()

    mid = uuid.uuid4()
    cand = _candidate()
    cand.source_message_ids = [mid]
    texts = {mid: "我喜欢少糖咖啡"}

    service = MemoryService(session)
    d1, _ = await service.process_candidate(
        user_id=user.id,
        candidate=cand,
        source_kind="explicit",
        extractor_version="v1",
        available_message_ids={mid},
        available_message_texts=texts,
    )
    assert d1 == Decision.add

    # Same fact from a DIFFERENT message -> idempotency key differs, so the
    # decision path runs and dedupes by fingerprint -> ignore.
    mid2 = uuid.uuid4()
    cand2 = _candidate()
    cand2.source_message_ids = [mid2]
    d2, _ = await service.process_candidate(
        user_id=user.id,
        candidate=cand2,
        source_kind="explicit",
        extractor_version="v1",
        available_message_ids={mid2},
        available_message_texts={mid2: "我喜欢少糖咖啡"},
    )
    assert d2 == Decision.ignore

    memories = await service.list_memories(user_id=user.id)
    assert len(memories) == 1


@pytest.mark.integration
async def test_slot_conflict_updates(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session, f"m-{uuid.uuid4().hex[:8]}@example.com")
    await session.commit()

    mid = uuid.uuid4()
    texts = {mid: "我喜欢少糖咖啡"}

    service = MemoryService(session)
    cand1 = _candidate(value="少糖咖啡")
    cand1.source_message_ids = [mid]
    d1, _ = await service.process_candidate(
        user_id=user.id,
        candidate=cand1,
        source_kind="explicit",
        extractor_version="v1",
        available_message_ids={mid},
        available_message_texts=texts,
    )
    assert d1 == Decision.add

    # Same slot (type+subject+predicate) different value -> update.
    cand2 = _candidate(value="多糖咖啡")
    cand2.source_message_ids = [mid]
    cand2.evidence_quote = "我现在喜欢多糖咖啡"
    d2, _ = await service.process_candidate(
        user_id=user.id,
        candidate=cand2,
        source_kind="explicit",
        extractor_version="v1",
        available_message_ids={mid},
        available_message_texts={mid: "我现在喜欢多糖咖啡"},
    )
    assert d2 == Decision.update


@pytest.mark.integration
async def test_soft_delete_stops_retrieval(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session, f"m-{uuid.uuid4().hex[:8]}@example.com")
    await session.commit()

    mid = uuid.uuid4()
    cand = _candidate()
    cand.source_message_ids = [mid]
    service = MemoryService(session)
    _, _ = await service.process_candidate(
        user_id=user.id,
        candidate=cand,
        source_kind="explicit",
        extractor_version="v1",
        available_message_ids={mid},
        available_message_texts={mid: "我喜欢少糖咖啡"},
    )

    memories = await service.list_memories(user_id=user.id)
    assert len(memories) == 1
    mem_id = memories[0].id

    deleted = await service.soft_delete(user_id=user.id, memory_id=mem_id)
    assert deleted is True

    remaining = await service.list_memories(user_id=user.id)
    assert remaining == []
