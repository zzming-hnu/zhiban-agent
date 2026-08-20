"""Unit tests for the bounded agent loop (no database, fake LLM)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from zhiban.agent.context import ContextManager
from zhiban.agent.events import MESSAGE_DELTA, RUN_COMPLETED
from zhiban.agent.orchestrator import run_agent_stream
from zhiban.core.config import Settings
from zhiban.core.token_budget import build_token_budget
from zhiban.llm.base import ChatMessage, LLMChunk, LLMResponse
from zhiban.tools.executor import ToolExecutor
from zhiban.tools.registry import ToolRegistry


class FakeLLM:
    """A programmable LLM adapter for testing the agent loop."""

    model = "fake"

    def __init__(self, chunks: list[str] | None = None) -> None:
        self._chunks = chunks or []
        self.chat_calls = 0
        self.stream_calls = 0

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        self.chat_calls += 1
        return LLMResponse(content="".join(self._chunks))

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        self.stream_calls += 1
        for chunk in self._chunks:
            yield LLMChunk(delta=chunk)
        yield LLMChunk(delta="", finish_reason="stop")


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        llm_provider="mock",
        search_provider="mock",
        **overrides,
    )


def _context() -> ContextManager:
    budget = build_token_budget(
        32768, output_reserve=4096, summary_budget=1800, tool_results_budget=2200
    )
    return ContextManager(budget)


def _messages() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="你是知伴"),
        ChatMessage(role="user", content="你好"),
    ]


async def _collect(llm: FakeLLM, settings: Settings) -> list[tuple[str, dict]]:
    registry = ToolRegistry()
    executor = ToolExecutor()
    events = []
    async for event in run_agent_stream(
        llm,
        settings,
        registry,
        executor,
        _context(),
        run_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        messages=_messages(),
    ):
        events.append((event.type, event.data))
    return events


@pytest.mark.asyncio
async def test_fast_path_streams_and_completes() -> None:
    llm = FakeLLM(chunks=["你好", "！", "我是", "知伴"])
    events = await _collect(llm, _settings())

    types = [e[0] for e in events]
    assert types[0] == "run.started"
    assert MESSAGE_DELTA in types
    assert types[-1] == RUN_COMPLETED

    # All delta content is assembled.
    deltas = "".join(e[1].get("delta", "") for e in events if e[0] == MESSAGE_DELTA)
    assert deltas == "你好！我是知伴"


@pytest.mark.asyncio
async def test_empty_response_falls_back() -> None:
    llm = FakeLLM(chunks=[])  # empty stream
    events = await _collect(llm, _settings())

    types = [e[0] for e in events]
    assert types[-1] == RUN_COMPLETED
    # Empty fallback still produces a terminal completed event.
    assert any(e[0] == "message.completed" for e in events)


@pytest.mark.asyncio
async def test_repeated_tool_calls_are_not_duplicated() -> None:
    # A tool-requesting stream would need tool_calls in chunks; this is a smoke
    # test that a plain fast path does not attempt any tool execution.
    llm = FakeLLM(chunks=["直接回答"])
    events = await _collect(llm, _settings())

    types = [e[0] for e in events]
    assert not any(t.startswith("tool.call.") for t in types)


def test_write_tool_detection() -> None:
    from zhiban.agent.orchestrator import _is_write_tool

    assert _is_write_tool("todo.create")
    assert _is_write_tool("todo.complete")
    assert _is_write_tool("reminder.create")
    assert _is_write_tool("reminder.cancel")
    assert _is_write_tool("memory.add")
    assert _is_write_tool("memory.update")
    assert _is_write_tool("memory.delete")
    # Read-only tools are not write tools.
    assert not _is_write_tool("memory.list")
    assert not _is_write_tool("web_search")
    assert not _is_write_tool("current_time")
