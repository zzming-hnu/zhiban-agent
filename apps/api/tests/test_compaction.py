"""Integration tests for context compaction (requires PostgreSQL)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.agent.compaction import build_context_with_compaction, load_latest_summary
from zhiban.agent.context import ContextManager
from zhiban.auth.security import hash_password
from zhiban.core.config import Settings
from zhiban.core.token_budget import build_token_budget
from zhiban.db.models import (
    AgentRun,
    AuthSession,
    Conversation,
    ConversationSummary,
    Message,
    User,
)
from zhiban.llm.base import ChatMessage, LLMChunk, LLMResponse


class SummaryLLM:
    model = "fake-summary"

    async def chat(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> LLMResponse:
        return LLMResponse(content='{"goals":["完成答辩"],"constraints":[]}')

    async def chat_stream(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMChunk]:
        yield LLMChunk(delta="", finish_reason="stop")


async def _cleanup(db: AsyncSession) -> None:
    for model in (ConversationSummary, AgentRun, Message, Conversation, AuthSession, User):
        await db.execute(delete(model))
    await db.commit()


async def _make_user(db: AsyncSession) -> User:
    user = User(
        email=f"c-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        display_name="c",
    )
    db.add(user)
    await db.flush()
    return user


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        llm_provider="mock",
        search_provider="mock",
        model_context_window=4096,
        context_compact_target_ratio=0.3,
        context_soft_threshold_ratio=0.5,
        context_hard_threshold_ratio=0.7,
        context_keep_recent_turns=2,
    )


def _context_manager() -> ContextManager:
    return ContextManager(
        build_token_budget(4096, output_reserve=512, summary_budget=512, tool_results_budget=512)
    )


@pytest.mark.integration
async def test_compaction_folds_old_turns_and_keeps_recent(session: AsyncSession) -> None:
    await _cleanup(session)
    user = await _make_user(session)
    conv = Conversation(user_id=user.id, title="long")
    session.add(conv)
    await session.flush()

    # Create many long messages to exceed the soft threshold.
    created: list[Message] = []
    for i in range(20):
        msg = Message(
            conversation_id=conv.id,
            user_id=user.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"这是一条很长的第{i}条消息内容" + "重要内容" * 50,
        )
        session.add(msg)
        await session.flush()
        created.append(msg)

    current_user = created[-1]
    await session.commit()

    result = await build_context_with_compaction(
        session,
        user_id=user.id,
        conversation_id=conv.id,
        current_user_message_id=current_user.id,
        settings=_settings(),
        summary_llm=SummaryLLM(),
        context_manager=_context_manager(),
    )

    assert result.compacted is True
    assert result.summary is not None
    # A summary record was persisted.
    latest = await load_latest_summary(session, user_id=user.id, conversation_id=conv.id)
    assert latest is not None
    assert "goals" in latest.summary

    # The current user message is always preserved.
    assert any(m.role == "user" and "第19条" in m.content for m in result.messages)

    await _cleanup(session)


@pytest.mark.integration
async def test_compaction_not_triggered_for_short_conversation(session: AsyncSession) -> None:
    await _cleanup(session)
    user = await _make_user(session)
    conv = Conversation(user_id=user.id, title="short")
    session.add(conv)
    await session.flush()

    msg = Message(conversation_id=conv.id, user_id=user.id, role="user", content="你好")
    session.add(msg)
    await session.flush()
    await session.commit()

    result = await build_context_with_compaction(
        session,
        user_id=user.id,
        conversation_id=conv.id,
        current_user_message_id=msg.id,
        settings=_settings(),
        summary_llm=SummaryLLM(),
        context_manager=_context_manager(),
    )

    assert result.compacted is False
    assert result.summary is None

    await _cleanup(session)
