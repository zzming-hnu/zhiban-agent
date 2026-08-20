"""Cross-user isolation tests: repository scoping and API 404 semantics."""

import uuid

import httpx2 as httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.auth.security import hash_password
from zhiban.conversations.repository import ConversationRepository, MessageRepository
from zhiban.db.models import (
    AgentRun,
    AuthSession,
    Conversation,
    ConversationSummary,
    IdempotencyRecord,
    Message,
    User,
)


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _cleanup(db: AsyncSession) -> None:
    await db.execute(delete(IdempotencyRecord))
    await db.execute(delete(ConversationSummary))
    await db.execute(delete(AgentRun))
    await db.execute(delete(Message))
    await db.execute(delete(Conversation))
    await db.execute(delete(AuthSession))
    await db.execute(delete(User))
    await db.commit()


async def _create_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, password_hash=hash_password("password123"), display_name="x")
    db.add(user)
    await db.flush()
    return user


@pytest.mark.integration
async def test_repository_enforces_user_scope(session: AsyncSession) -> None:
    await _cleanup(session)
    user_a = await _create_user(session, _email("iso-a"))
    user_b = await _create_user(session, _email("iso-b"))
    await session.commit()

    conv_repo = ConversationRepository(session)
    conv_a = await conv_repo.create(user_id=user_a.id, title="A's conversation")
    await session.commit()

    assert await conv_repo.get(user_id=user_b.id, conversation_id=conv_a.id) is None
    assert await conv_repo.get(user_id=user_a.id, conversation_id=conv_a.id) is not None

    await _cleanup(session)


@pytest.mark.integration
async def test_messages_are_scoped_by_user(session: AsyncSession) -> None:
    await _cleanup(session)
    user_a = await _create_user(session, _email("msga"))
    user_b = await _create_user(session, _email("msgb"))
    await session.commit()

    conv_repo = ConversationRepository(session)
    conv_a = await conv_repo.create(user_id=user_a.id, title="A's")
    await session.commit()

    msg_repo = MessageRepository(session)
    await msg_repo.create(
        user_id=user_a.id, conversation_id=conv_a.id, role="user", content="hello from A"
    )
    await session.commit()

    b_items = await msg_repo.list(
        user_id=user_b.id, conversation_id=conv_a.id, cursor=None, limit=10
    )
    assert b_items == []

    a_items = await msg_repo.list(
        user_id=user_a.id, conversation_id=conv_a.id, cursor=None, limit=10
    )
    assert len(a_items) == 1

    await _cleanup(session)


@pytest.mark.integration
async def test_cross_user_conversation_access_returns_404(client: httpx.AsyncClient) -> None:
    email_a = _email("xuser-a")
    email_b = _email("xuser-b")

    reg_a = await client.post(
        "/api/v1/auth/register", json={"email": email_a, "password": "password123"}
    )
    assert reg_a.status_code == 201
    conv = await client.post("/api/v1/conversations", json={"title": "A's private"})
    assert conv.status_code == 201
    conv_id = conv.json()["id"]

    csrf_a = client.cookies.get("zhiban_csrf")
    await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_a or "", "Origin": "http://localhost:3000"},
    )

    reg_b = await client.post(
        "/api/v1/auth/register", json={"email": email_b, "password": "password123"}
    )
    assert reg_b.status_code == 201

    assert (await client.get(f"/api/v1/conversations/{conv_id}")).status_code == 404
    assert (
        await client.patch(f"/api/v1/conversations/{conv_id}", json={"title": "hijack"})
    ).status_code == 404
    assert (await client.delete(f"/api/v1/conversations/{conv_id}")).status_code == 404
    assert (await client.get(f"/api/v1/conversations/{conv_id}/messages")).status_code == 404
