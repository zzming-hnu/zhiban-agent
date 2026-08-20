"""Unit tests for conversation title generation (no database)."""

from collections.abc import AsyncIterator

import pytest
from zhiban.agent.title import generate_title
from zhiban.llm.base import ChatMessage, LLMChunk, LLMResponse


class FakeTitleLLM:
    model = "fake-title"

    def __init__(self, content: str) -> None:
        self._content = content

    async def chat(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> LLMResponse:
        return LLMResponse(content=self._content)

    async def chat_stream(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMChunk]:
        yield LLMChunk(delta=self._content, finish_reason="stop")


class FailingTitleLLM:
    model = "failing-title"

    async def chat(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> LLMResponse:
        raise RuntimeError("boom")

    async def chat_stream(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMChunk]:
        yield LLMChunk(delta="", finish_reason="stop")
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_generate_title_strips_quotes_and_truncates() -> None:
    llm = FakeTitleLLM("「帮我规划答辩准备」")
    title = await generate_title(llm, "帮我规划一下答辩准备的重点")
    assert title == "帮我规划答辩准备"


@pytest.mark.asyncio
async def test_generate_title_returns_empty_on_failure() -> None:
    llm = FailingTitleLLM()
    title = await generate_title(llm, "任意内容")
    assert title == ""
