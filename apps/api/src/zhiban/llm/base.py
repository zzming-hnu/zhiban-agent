"""LLM adapter protocol and message types."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class LLMResponse:
    content: str
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class LLMChunk:
    delta: str
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@runtime_checkable
class LLMAdapter(Protocol):
    model: str

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse: ...

    def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[LLMChunk]: ...


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A normalized tool call extracted from an LLM response."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
