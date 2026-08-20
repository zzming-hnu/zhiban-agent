"""Integration tests for memory retrieval (lexical fallback + scoring)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.auth.security import hash_password
from zhiban.db.models import Memory, User
from zhiban.memory.search import search_memories
from zhiban.memory.types import MemoryStatus


async def _make_user(session: AsyncSession, email: str) -> User:
    user = User(email=email, password_hash=hash_password("password123"), display_name="x")
    session.add(user)
    await session.flush()
    return user


async def _add_memory(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    memory_type: str,
    subject: str,
    predicate: str,
    value: str,
) -> None:
    memory = Memory(
        user_id=user_id,
        memory_type=memory_type,
        subject=subject,
        predicate=predicate,
        value=value,
        content=f"{subject} {predicate} {value}",
        source_kind="explicit",
        status=MemoryStatus.active,
        confidence=1.0,
        importance=0.7,
        fingerprint=uuid.uuid4().hex,
        conflict_key=uuid.uuid4().hex,
        source_message_ids=[],
        evidence_quote="",
    )
    session.add(memory)
    await session.flush()


@pytest.mark.integration
async def test_lexical_fallback_returns_relevant(
    session: AsyncSession, clean_database: None
) -> None:
    user = await _make_user(session, f"s-{uuid.uuid4().hex[:8]}@example.com")
    await session.commit()
    await _add_memory(
        session,
        user_id=user.id,
        memory_type="preference",
        subject="self",
        predicate="喜欢",
        value="少糖咖啡",
    )
    await _add_memory(
        session,
        user_id=user.id,
        memory_type="habit",
        subject="self",
        predicate="习惯",
        value="早上跑步",
    )
    await session.commit()

    # Lexical fallback (embedding=None): query about coffee preference.
    results = await search_memories(session, user_id=user.id, query="少糖咖啡", embedding=None)
    assert len(results) >= 1
    assert any("少糖" in r.memory.content for r in results)


@pytest.mark.integration
async def test_search_is_user_scoped(session: AsyncSession, clean_database: None) -> None:
    user_a = await _make_user(session, f"s-{uuid.uuid4().hex[:8]}@example.com")
    user_b = await _make_user(session, f"s-{uuid.uuid4().hex[:8]}@example.com")
    await session.commit()

    await _add_memory(
        session,
        user_id=user_a.id,
        memory_type="preference",
        subject="self",
        predicate="喜欢",
        value="少糖咖啡",
    )
    await session.commit()

    # B querying for A's content returns nothing.
    results_b = await search_memories(session, user_id=user_b.id, query="少糖咖啡", embedding=None)
    assert results_b == []

    results_a = await search_memories(session, user_id=user_a.id, query="少糖咖啡", embedding=None)
    assert len(results_a) >= 1


@pytest.mark.integration
async def test_deleted_memory_not_retrieved(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session, f"s-{uuid.uuid4().hex[:8]}@example.com")
    await session.commit()

    # Add and then delete a memory.
    memory = Memory(
        user_id=user.id,
        memory_type="preference",
        subject="self",
        predicate="喜欢",
        value="少糖咖啡",
        content="self 喜欢 少糖咖啡",
        source_kind="explicit",
        status=MemoryStatus.active,
        confidence=1.0,
        importance=0.7,
        fingerprint=uuid.uuid4().hex,
        conflict_key=uuid.uuid4().hex,
        source_message_ids=[],
        evidence_quote="",
    )
    session.add(memory)
    await session.flush()
    memory.status = MemoryStatus.deleted
    await session.commit()

    results = await search_memories(session, user_id=user.id, query="少糖咖啡", embedding=None)
    assert results == []
