"""Tests for layered memory injection (explicit always-on, implicit on-demand)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.auth.security import hash_password
from zhiban.conversations.runs_router import _load_explicit_memories
from zhiban.db.models import Memory, User
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
    source_kind: str,
    content: str,
) -> None:
    memory = Memory(
        user_id=user_id,
        memory_type="preference",
        category="other",
        subject="self",
        predicate="x",
        value=content,
        content=content,
        source_kind=source_kind,
        status=MemoryStatus.active,
        confidence=1.0,
        importance=0.5,
        fingerprint=uuid.uuid4().hex,
        conflict_key=uuid.uuid4().hex,
        source_message_ids=[],
        evidence_quote="",
    )
    session.add(memory)
    await session.flush()


@pytest.mark.integration
async def test_explicit_memories_are_always_loaded(
    session: AsyncSession, clean_database: None
) -> None:
    user = await _make_user(session, f"inj-{uuid.uuid4().hex[:8]}@example.com")
    await session.commit()

    await _add_memory(session, user_id=user.id, source_kind="explicit", content="喜欢简洁回答")
    await _add_memory(session, user_id=user.id, source_kind="implicit", content="早上跑步")
    await session.commit()

    lines = await _load_explicit_memories(session, user.id)
    # Only explicit memories are in the core list.
    assert any("简洁" in line for line in lines)
    assert not any("跑步" in line for line in lines)


@pytest.mark.integration
async def test_explicit_memories_exclude_deleted(
    session: AsyncSession, clean_database: None
) -> None:
    user = await _make_user(session, f"inj-{uuid.uuid4().hex[:8]}@example.com")
    await session.commit()

    await _add_memory(session, user_id=user.id, source_kind="explicit", content="喜欢少糖")
    await session.commit()

    # Soft-delete the memory.
    from sqlalchemy import select

    mem = (
        await session.execute(
            select(Memory).where(Memory.user_id == user.id, Memory.source_kind == "explicit")
        )
    ).scalar_one()
    mem.status = MemoryStatus.deleted
    await session.commit()

    lines = await _load_explicit_memories(session, user.id)
    assert lines == []
