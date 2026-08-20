"""Tests for embedding integration in memory write/retrieve."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.auth.security import hash_password
from zhiban.db.models import User
from zhiban.memory.schemas import MemoryCandidatePayload
from zhiban.memory.service import MemoryService
from zhiban.memory.types import Decision


class FakeEmbedding:
    """Deterministic fake embedding adapter (matches pgvector dim 1536)."""

    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim
        self.calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        # Deterministic: hash chars into a fixed-dim vector.
        vec = [0.0] * self.dim
        for i, ch in enumerate(text):
            vec[i % self.dim] += float(ord(ch) % 10) / 10.0
        return vec


class FailingEmbedding:
    async def embed(self, text: str) -> list[float]:
        raise RuntimeError("embedding down")


async def _make_user(session: AsyncSession) -> User:
    user = User(
        email=f"e-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        display_name="x",
    )
    session.add(user)
    await session.flush()
    return user


def _candidate() -> MemoryCandidatePayload:
    return MemoryCandidatePayload(
        memory_type="preference",
        category="communication_preference",
        subject="self",
        predicate="喜欢",
        value="少糖咖啡",
        source_message_ids=[uuid.uuid4()],
        evidence_quote="我喜欢少糖咖啡",
        confidence=0.9,
        importance=0.7,
    )


@pytest.mark.integration
async def test_memory_add_generates_embedding(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session)
    await session.commit()

    fake = FakeEmbedding()
    service = MemoryService(session, embedding=fake)  # type: ignore[arg-type]
    mid = uuid.uuid4()
    cand = _candidate()
    cand.source_message_ids = [mid]

    decision, _ = await service.process_candidate(
        user_id=user.id,
        candidate=cand,
        source_kind="explicit",
        extractor_version="v1",
        available_message_ids={mid},
        available_message_texts={mid: "我喜欢少糖咖啡"},
    )
    assert decision == Decision.add

    memories = await service.list_memories(user_id=user.id)
    assert len(memories) == 1
    # Embedding was generated (non-null).
    assert memories[0].embedding is not None
    assert len(memories[0].embedding) == 1536
    assert fake.calls  # embedding adapter was actually invoked


@pytest.mark.integration
async def test_memory_add_falls_back_when_embedding_fails(
    session: AsyncSession, clean_database: None
) -> None:
    user = await _make_user(session)
    await session.commit()

    service = MemoryService(session, embedding=FailingEmbedding())  # type: ignore[arg-type]
    mid = uuid.uuid4()
    cand = _candidate()
    cand.source_message_ids = [mid]

    decision, _ = await service.process_candidate(
        user_id=user.id,
        candidate=cand,
        source_kind="explicit",
        extractor_version="v1",
        available_message_ids={mid},
        available_message_texts={mid: "我喜欢少糖咖啡"},
    )
    assert decision == Decision.add

    memories = await service.list_memories(user_id=user.id)
    assert len(memories) == 1
    # Embedding is None on failure (lexical fallback).
    assert memories[0].embedding is None
