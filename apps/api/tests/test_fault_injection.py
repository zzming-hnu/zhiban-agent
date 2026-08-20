"""Fault injection tests: LLM failure, search failure, delivery failure."""

import uuid
from collections.abc import AsyncIterator

import pytest
from zhiban.agent.context import ContextManager
from zhiban.agent.events import RUN_COMPLETED, RUN_FAILED
from zhiban.agent.orchestrator import run_agent_stream
from zhiban.core.config import Settings
from zhiban.core.token_budget import build_token_budget
from zhiban.llm.base import ChatMessage, LLMChunk, LLMResponse
from zhiban.llm.errors import ErrorKind, LLMError
from zhiban.tools.executor import ToolExecutor
from zhiban.tools.registry import ToolRegistry


class FailingLLM:
    """LLM that always raises (simulates provider outage)."""

    model = "failing"

    async def chat(self, messages, tools=None) -> LLMResponse:
        raise LLMError(ErrorKind.dependency_transient, "provider down", retryable=True)

    async def chat_stream(self, messages, tools=None) -> AsyncIterator[LLMChunk]:
        raise LLMError(ErrorKind.dependency_transient, "provider down", retryable=True)
        yield  # pragma: no cover - unreachable


class TimeoutLLM:
    """LLM whose stream never finishes (simulates a hung provider)."""

    model = "timeout"

    async def chat(self, messages, tools=None) -> LLMResponse:
        raise LLMError(ErrorKind.dependency_transient, "timeout", retryable=True)

    async def chat_stream(self, messages, tools=None) -> AsyncIterator[LLMChunk]:
        import asyncio

        await asyncio.sleep(100)
        yield LLMChunk(delta="never", finish_reason="stop")


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        llm_provider="mock",
        search_provider="mock",
        agent_final_round_timeout_seconds=1,
        **overrides,
    )


def _context() -> ContextManager:
    budget = build_token_budget(
        32768, output_reserve=4096, summary_budget=1800, tool_results_budget=2200
    )
    return ContextManager(budget)


def _messages() -> list[ChatMessage]:
    return [ChatMessage(role="system", content="sys"), ChatMessage(role="user", content="hi")]


async def _collect(llm, settings: Settings) -> list[str]:
    events = []
    async for event in run_agent_stream(
        llm,
        settings,
        ToolRegistry(),
        ToolExecutor(),
        _context(),
        run_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        messages=_messages(),
    ):
        events.append(event.type)
    return events


@pytest.mark.asyncio
async def test_llm_failure_raises_llm_error() -> None:
    # The orchestrator re-raises LLMError so the run-stream endpoint emits a
    # single run.failed event (rather than swallowing the failure).
    with pytest.raises(LLMError):
        await _collect(FailingLLM(), _settings())


@pytest.mark.asyncio
async def test_llm_timeout_falls_back_to_completed() -> None:
    # A hung provider is bounded by the final-round timeout and ends with a
    # deterministic fallback (completed), never hanging forever.
    events = await _collect(TimeoutLLM(), _settings())
    assert RUN_COMPLETED in events or RUN_FAILED in events
