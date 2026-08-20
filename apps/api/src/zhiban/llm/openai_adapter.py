"""OpenAI-compatible LLM adapter for real model providers.

Handles reasoning models (e.g. Kimi K2.5) that emit ``reasoning_content``
alongside ``content``: only ``content`` is surfaced as the answer body, and
``reasoning_content`` is never sent to the client or logged.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx2 as httpx

from zhiban.llm.base import ChatMessage, LLMChunk, LLMResponse
from zhiban.llm.errors import ErrorKind, LLMError, classify_http_error


def _message_to_openai(msg: ChatMessage) -> dict[str, Any]:
    result: dict[str, Any] = {"role": msg.role, "content": msg.content}
    if msg.tool_call_id:
        result["tool_call_id"] = msg.tool_call_id
    if msg.name:
        result["name"] = msg.name
    if msg.tool_calls:
        result["tool_calls"] = msg.tool_calls
    return result


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with jitter: 1s, 2s, 4s base (capped)."""
    import random

    base = min(2**attempt, 8)
    return float(base + random.uniform(0, 0.5))


class OpenAIAdapter:
    model: str

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
        max_retries: int = 2,
        reasoning_effort: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort
        self._client = httpx.AsyncClient(timeout=timeout)

    def _extra_payload(self) -> dict[str, Any]:
        """Provider-specific request options (e.g. reasoning control)."""
        extra: dict[str, Any] = {}
        if self.reasoning_effort:
            extra["reasoning_effort"] = self.reasoning_effort
        return extra

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_to_openai(m) for m in messages],
            "stream": False,
        }
        payload.update(self._extra_payload())
        if tools:
            payload["tools"] = tools

        last_error: LLMError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if response.status_code >= 400:
                    error = classify_http_error(response.status_code, response.text[:500])
                    if error.retryable and attempt < self.max_retries:
                        last_error = error
                        await asyncio.sleep(_backoff_seconds(attempt))
                        continue
                    raise error
                data = response.json()
                return self._parse_response(data)
            except LLMError:
                raise
            except httpx.TimeoutException:
                error = LLMError(
                    ErrorKind.dependency_transient,
                    "模型请求超时",
                    retryable=True,
                )
                if attempt < self.max_retries:
                    last_error = error
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise error from None
            except httpx.HTTPError as exc:
                error = LLMError(
                    ErrorKind.dependency_transient,
                    f"模型网络错误: {exc}",
                    retryable=True,
                )
                if attempt < self.max_retries:
                    last_error = error
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise error from exc
        assert last_error is not None
        raise last_error

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_to_openai(m) for m in messages],
            "stream": True,
        }
        payload.update(self._extra_payload())
        if tools:
            payload["tools"] = tools

        # Retry only until the first byte; once content has been emitted we must
        # not replay the turn (SPEC-AG-053).
        last_error: LLMError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with self._client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        error = classify_http_error(
                            response.status_code, body.decode("utf-8", "replace")[:500]
                        )
                        if error.retryable and attempt < self.max_retries:
                            last_error = error
                            await asyncio.sleep(_backoff_seconds(attempt))
                            continue
                        raise error
                    async for chunk in self._iter_chunks(response):
                        yield chunk
                    return
            except LLMError:
                raise
            except httpx.TimeoutException:
                error = LLMError(ErrorKind.dependency_transient, "模型流式请求超时", retryable=True)
                if attempt < self.max_retries:
                    last_error = error
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise error from None
            except httpx.HTTPError as exc:
                error = LLMError(
                    ErrorKind.dependency_transient, f"模型网络错误: {exc}", retryable=True
                )
                if attempt < self.max_retries:
                    last_error = error
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise error from exc
        assert last_error is not None
        raise last_error

    async def _iter_chunks(self, response: httpx.Response) -> AsyncIterator[LLMChunk]:
        """Iterate SSE lines, accumulating tool-call deltas and dropping reasoning."""
        tool_call_deltas: dict[int, dict[str, Any]] = {}
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                yield LLMChunk(delta="", finish_reason="stop")
                break
            try:
                data = json.loads(data_str)
                delta = data["choices"][0].get("delta", {})
                # Reasoning models put their chain-of-thought in
                # `reasoning_content`; only surface `content` to callers.
                content = delta.get("content", "")
                finish = data["choices"][0].get("finish_reason")

                tool_calls = None
                for tc in delta.get("tool_calls", []) or []:
                    idx = tc.get("index", 0)
                    slot = tool_call_deltas.setdefault(
                        idx,
                        {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function", {})
                    if fn.get("name"):
                        slot["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["function"]["arguments"] += fn["arguments"]
                    tool_calls = list(tool_call_deltas.values())

                if content or finish or tool_calls is not None:
                    yield LLMChunk(delta=content or "", finish_reason=finish, tool_calls=tool_calls)
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        choice = data["choices"][0]
        usage = data.get("usage", {})
        msg = choice.get("message", {})
        tool_calls = msg.get("tool_calls")
        # Surface only the final answer content, never reasoning_content.
        content = msg.get("content", "") or ""
        return LLMResponse(
            content=content,
            finish_reason=choice.get("finish_reason", "stop"),
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            tool_calls=tool_calls,
        )
