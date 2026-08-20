"""Unit tests for search sanitization, mock adapter, and summary tool."""

import uuid
from collections.abc import AsyncIterator

import pytest
from zhiban.llm.base import ChatMessage, LLMChunk, LLMResponse
from zhiban.tools.base import ToolContext
from zhiban.tools.builtin.summary import SummaryTool
from zhiban.tools.builtin.web_search import WebSearchTool
from zhiban.tools.executor import ToolExecutor
from zhiban.tools.search.base import SearchResult
from zhiban.tools.search.mock import MockSearchAdapter
from zhiban.tools.search.sanitize import sanitize_result, sanitize_snippet


def _ctx() -> ToolContext:
    return ToolContext(user_id=uuid.uuid4(), run_id=uuid.uuid4())


# --- sanitize ---


def test_sanitize_strips_html() -> None:
    text = "<script>alert(1)</script><p>正常内容</p>"
    assert "script" not in sanitize_snippet(text)
    assert "正常内容" in sanitize_snippet(text)


def test_sanitize_caps_length() -> None:
    assert len(sanitize_snippet("长" * 2000, max_chars=100)) <= 101


def test_sanitize_result_preserves_url() -> None:
    result = SearchResult(
        title="<b>标题</b>",
        url="https://example.com",
        snippet="<img src=x onerror=1>正文",
    )
    cleaned = sanitize_result(result)
    assert cleaned.url == "https://example.com"
    assert "<" not in cleaned.title
    assert "<" not in cleaned.snippet


# --- mock search ---


@pytest.mark.asyncio
async def test_mock_search_returns_deterministic_results() -> None:
    adapter = MockSearchAdapter()
    results = await adapter.search("pgvector", 3)
    assert len(results) >= 1
    assert any("pgvector" in r.title for r in results)


@pytest.mark.asyncio
async def test_web_search_tool_sanitizes_and_cites() -> None:
    tool = WebSearchTool(MockSearchAdapter())
    result = await ToolExecutor().execute(tool, _ctx(), {"query": "pgvector", "max_results": 3})
    assert result.ok is True
    assert result.citations
    assert all(url.startswith("http") for url in result.citations)


# --- summary ---


class _FakeSummaryLLM:
    model = "fake-summary"

    async def chat(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> LLMResponse:
        return LLMResponse(content="- 要点一\n- 要点二")

    async def chat_stream(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMChunk]:
        yield LLMChunk(delta="- 要点一", finish_reason="stop")


@pytest.mark.asyncio
async def test_summary_tool_uses_llm() -> None:
    tool = SummaryTool(_FakeSummaryLLM())
    result = await ToolExecutor().execute(
        tool, _ctx(), {"text": "这是一段需要总结的文本内容", "style": "bullets"}
    )
    assert result.ok is True
    assert "要点" in result.data["summary"]


@pytest.mark.asyncio
async def test_summary_tool_rejects_empty_text() -> None:
    tool = SummaryTool(_FakeSummaryLLM())
    # Empty text fails Pydantic validation (min_length=1).
    result = await ToolExecutor().execute(tool, _ctx(), {"text": "", "style": "brief"})
    assert result.ok is False
    assert result.error_code == "tool_invalid_argument"
