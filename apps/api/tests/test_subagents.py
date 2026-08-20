"""Unit + integration tests for sub-agent routing and MemoryAgent."""

import uuid
from collections.abc import AsyncIterator

import pytest
from zhiban.agent.router import KNOWN_TARGETS, _parse_decision
from zhiban.agent.subagent import SubAgentContext
from zhiban.agent.subagents.memory_agent import MemoryAgent
from zhiban.llm.base import ChatMessage, LLMChunk, LLMResponse
from zhiban.memory.service import MemoryService


class NoToolLLM:
    """An LLM that never returns tool calls (just a final text)."""

    model = "fake"

    def __init__(self, text: str = "已处理") -> None:
        self._text = text

    async def chat(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> LLMResponse:
        return LLMResponse(content=self._text)

    async def chat_stream(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMChunk]:
        yield LLMChunk(delta=self._text)
        yield LLMChunk(delta="", finish_reason="stop")


def test_router_known_targets() -> None:
    assert set(KNOWN_TARGETS) == {"memory", "task", "search", "general"}


def test_router_parses_all_targets() -> None:
    assert _parse_decision('{"target": "memory", "reason": "记住"}').target == "memory"
    assert _parse_decision('{"target": "task", "reason": "待办"}').target == "task"
    assert _parse_decision('{"target": "search", "reason": "搜索"}').target == "search"
    assert _parse_decision('{"target": "general", "reason": "闲聊"}').target == "general"
    assert _parse_decision('{"target": "none", "reason": ""}').target == "none"


def test_subagent_names() -> None:
    assert MemoryAgent.name == "memory"


@pytest.mark.integration
async def test_memory_agent_returns_structured_summary(
    session, clean_database: None
) -> None:
    """MemoryAgent returns a structured summary via its bounded loop."""
    from zhiban.db.models import User

    user = User(email=f"sa-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
    session.add(user)
    await session.commit()

    service = MemoryService(session)
    agent = MemoryAgent(service, NoToolLLM("已记住"))

    result = await agent.run(
        SubAgentContext(
            user_id=user.id,
            conversation_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            user_input="记住我喜欢喝咖啡",
        )
    )
    assert result.ok is True
    assert result.summary == "已记住"
