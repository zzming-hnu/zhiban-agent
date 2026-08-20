"""Bounded agent loop with final round, fallback, and streaming events."""

import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import structlog

from zhiban.agent.context import ContextManager, ToolResultRecord
from zhiban.agent.events import (
    AGENT_THINKING,
    MESSAGE_COMPLETED,
    MESSAGE_DELTA,
    RUN_COMPLETED,
    RUN_STARTED,
    TOOL_CALL_COMPLETED,
    TOOL_CALL_FAILED,
    TOOL_CALL_STARTED,
    WARNING_DEGRADED,
    AgentEvent,
    EventSequencer,
)
from zhiban.core.config import Settings
from zhiban.llm.base import ChatMessage, LLMAdapter, LLMResponse, ToolCall
from zhiban.llm.errors import ErrorKind, LLMError
from zhiban.tools.base import ToolContext, ToolResult
from zhiban.tools.executor import ToolExecutor
from zhiban.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


# Tools whose successful completion should produce a deterministic confirmation
# instead of triggering an extra LLM round.
_WRITE_TOOL_PREFIXES = ("todo.", "reminder.", "memory.add", "memory.update", "memory.delete")


def _is_write_tool(tool_name: str) -> bool:
    return any(tool_name.startswith(p) for p in _WRITE_TOOL_PREFIXES)


def _canonical_args(tool_name: str, args: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps([tool_name, args], sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _parse_tool_calls(response: LLMResponse) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for tc in response.tool_calls or []:
        func = tc.get("function", {})
        name = func.get("name", "")
        raw_args = func.get("arguments", "{}")
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
        else:
            args = raw_args if isinstance(raw_args, dict) else {}
        calls.append(ToolCall(id=tc.get("id", f"tc_{uuid.uuid4().hex}"), name=name, arguments=args))
    return calls


def _normalize_tool_call_name(provider_name: str, registry: ToolRegistry | None) -> str:
    """Reverse a provider tool name (e.g. ``memory_add``) back to the
    internal dotted form (``memory.add``) when possible. Falls back to the
    provider name if the registry has no match.
    """
    if registry is None:
        return provider_name
    return registry.resolve_tool_name(provider_name) or provider_name


class _BoundedAgent:
    def __init__(
        self,
        *,
        llm: LLMAdapter,
        settings: Settings,
        registry: ToolRegistry,
        executor: ToolExecutor,
        context: ContextManager,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> None:
        self.llm = llm
        self.settings = settings
        self.registry = registry
        self.executor = executor
        self.context = context
        self.run_id = run_id
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.sequencer = EventSequencer()
        self._deadline = time.monotonic() + settings.agent_total_timeout_seconds

    def _event(self, event_type: str, **kwargs: Any) -> AgentEvent:
        return AgentEvent(
            type=event_type,
            seq=self.sequencer.next(),
            run_id=self.run_id,
            **kwargs,
        )

    def _ensure_budget(self) -> None:
        if time.monotonic() > self._deadline:
            raise LLMError(ErrorKind.dependency_transient, "Agent 总超时", retryable=False)

    async def run(self, messages: list[ChatMessage]) -> AsyncIterator[AgentEvent]:
        yield self._event(RUN_STARTED, data={"model": self.llm.model})

        tool_schemas = self.registry.openai_schemas() if self.registry else None
        history_signatures: list[str] = []
        tool_results: list[ToolResultRecord] = []
        full_text = ""
        empty_count = 0
        round_no = 0
        produced_delta = False

        try:
            while round_no < self.settings.agent_max_tool_rounds:
                self._ensure_budget()
                round_no += 1
                yield self._event(AGENT_THINKING, data={"round": round_no})

                # Stream this round token-by-token, accumulating tool calls.
                stream_text = ""
                stream_tool_calls: list[dict[str, Any]] | None = None
                try:
                    # Bound the main-round stream so a stuck provider cannot
                    # wedge the run forever (use the final-round timeout so each
                    # individual stream call has its own budget).
                    async with asyncio.timeout(self.settings.agent_final_round_timeout_seconds):
                        async for chunk in self.llm.chat_stream(messages, tools=tool_schemas):
                            if chunk.delta:
                                stream_text += chunk.delta
                                produced_delta = True
                                full_text += chunk.delta
                                yield self._event(MESSAGE_DELTA, data={"delta": chunk.delta})
                            if chunk.tool_calls:
                                stream_tool_calls = chunk.tool_calls
                except TimeoutError:
                    await logger.aexception("main_round_stream_timeout")
                    full_text = self._limit_fallback()
                    break
                except LLMError:
                    raise

                # No tool calls -> the streamed text is the final answer.
                if not stream_tool_calls:
                    if stream_text.strip():
                        break
                    empty_count += 1
                    if empty_count >= 2:
                        full_text = self._empty_fallback()
                        break
                    messages.append(
                        ChatMessage(role="system", content="上一轮没有有效输出，请直接回答用户。")
                    )
                    continue

                # Model requested tool calls: parse and execute them.
                raw_calls = _parse_tool_calls(
                    LLMResponse(content=stream_text, tool_calls=stream_tool_calls)
                )
                # Providers like DeepSeek require tool names to match
                # ^[a-zA-Z0-9_-]+$, so we expose dotted names with underscores.
                # Reverse the mapping back to the internal dotted form here.
                calls = [
                    ToolCall(
                        id=call.id,
                        name=_normalize_tool_call_name(call.name, self.registry),
                        arguments=call.arguments,
                    )
                    for call in raw_calls
                ]
                signatures = [_canonical_args(c.name, c.arguments) for c in calls]

                # Repeated tool call detection.
                if any(sig in history_signatures for sig in signatures):
                    yield self._event(
                        WARNING_DEGRADED,
                        data={"reason": "重复工具调用，转入收尾"},
                    )
                    break

                history_signatures.extend(signatures)

                # Append the assistant tool-call turn to the message list.
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=stream_text,
                        tool_calls=stream_tool_calls,
                    )
                )

                # Execute tool calls.
                for call in calls:
                    self._ensure_budget()
                    yield self._event(
                        TOOL_CALL_STARTED,
                        tool_call_id=call.id,
                        data={"tool_name": call.name, "arguments": call.arguments},
                    )
                    result = await self._execute_tool(call)
                    if result.ok:
                        yield self._event(
                            TOOL_CALL_COMPLETED,
                            tool_call_id=call.id,
                            data={
                                "tool_name": call.name,
                                "summary": result.summary,
                                "data": result.data,
                            },
                        )
                    else:
                        yield self._event(
                            TOOL_CALL_FAILED,
                            tool_call_id=call.id,
                            data={
                                "tool_name": call.name,
                                "error_code": result.error_code,
                                "summary": result.summary,
                            },
                        )
                    record = ToolResultRecord(
                        tool_call_id=call.id,
                        tool_name=call.name,
                        summary=result.summary,
                        citations=result.citations,
                        ok=result.ok,
                        error_code=result.error_code,
                    )
                    tool_results.append(record)
                    tool_content = result.summary
                    if result.data is not None:
                        import json as _json

                        data_json = _json.dumps(result.data, ensure_ascii=False)
                        tool_content = f"{result.summary}\n[结构化数据] {data_json}"
                    messages.append(
                        ChatMessage(
                            role="tool",
                            content=tool_content,
                            tool_call_id=call.id,
                            name=call.name,
                        )
                    )

            # If write tools (todo/reminder/memory) completed successfully this
            # turn, reply with a deterministic confirmation immediately instead
            # of an extra LLM round — the user should not wait for a model to
            # rephrase "已创建".
            write_summaries = [
                r.summary for r in tool_results if r.ok and _is_write_tool(r.tool_name)
            ]
            if write_summaries and not full_text:
                full_text = "已为你处理：\n" + "\n".join(f"- {s}" for s in write_summaries)
                produced_delta = True
                yield self._event(MESSAGE_DELTA, data={"delta": full_text})

            # Final round (no tools) if no text was produced.
            if not produced_delta or not full_text:
                full_text = ""
                async for delta in self._final_round_stream(messages):
                    if delta:
                        full_text += delta
                        yield self._event(MESSAGE_DELTA, data={"delta": delta})

            yield self._event(
                MESSAGE_COMPLETED,
                data={"content": full_text},
            )
            yield self._event(RUN_COMPLETED, data={"finish_reason": "stop"})

        except LLMError:
            # Re-raise so the caller (run stream endpoint) emits a single,
            # consistent run.failed event and marks the run failed.
            raise

    async def _call_llm(
        self,
        messages: list[ChatMessage],
        tool_schemas: list[dict[str, Any]] | None,
        *,
        stream: bool,
    ) -> LLMResponse:
        if stream:
            text_parts: list[str] = []
            finish = "stop"
            async for chunk in self.llm.chat_stream(messages, tools=tool_schemas):
                if chunk.delta:
                    text_parts.append(chunk.delta)
                if chunk.finish_reason:
                    finish = chunk.finish_reason
            return LLMResponse(content="".join(text_parts), finish_reason=finish)
        return await self.llm.chat(messages, tools=tool_schemas)

    async def _final_round_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        import asyncio

        self._ensure_budget()
        suffix = ChatMessage(
            role="system",
            content="工具额度已耗尽，请基于已有结果直接回答；信息不足时如实说明。",
        )
        messages.append(suffix)
        produced_any = False
        try:
            # Bound the final round to a timeout so a stuck streaming connection
            # cannot wedge the run forever.
            async with asyncio.timeout(self.settings.agent_final_round_timeout_seconds):
                async for chunk in self.llm.chat_stream(messages, tools=None):
                    if chunk.delta:
                        produced_any = True
                        yield chunk.delta
        except (TimeoutError, LLMError):
            if not produced_any:
                yield self._limit_fallback()

    async def _final_round_text(self, messages: list[ChatMessage]) -> str:
        parts: list[str] = []
        async for delta in self._final_round_stream(messages):
            parts.append(delta)
        text = "".join(parts).strip()
        if not text:
            return self._limit_fallback()
        return text

    def _empty_fallback(self) -> str:
        return "抱歉，我暂时无法生成有效回复。请稍后重试，或换个方式描述你的问题。"

    def _limit_fallback(self) -> str:
        return "我已完成可用的处理，但信息不足以给出完整结论。请补充细节或稍后重试。"

    async def _execute_tool(self, call: ToolCall) -> ToolResult:
        tool = self.registry.get(call.name) if self.registry else None
        if tool is None:
            return ToolResult(
                ok=False,
                summary=f"未知工具：{call.name}",
                error_code="unknown_tool",
            )
        ctx = ToolContext(
            user_id=self.user_id,
            run_id=self.run_id,
            conversation_id=self.conversation_id,
        )
        return await self.executor.execute(tool, ctx, call.arguments)


async def run_agent_stream(
    llm: LLMAdapter,
    settings: Settings,
    registry: ToolRegistry,
    executor: ToolExecutor,
    context: ContextManager,
    *,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    messages: list[ChatMessage],
) -> AsyncIterator[AgentEvent]:
    """Run one bounded agent turn, yielding domain events."""
    agent = _BoundedAgent(
        llm=llm,
        settings=settings,
        registry=registry,
        executor=executor,
        context=context,
        run_id=run_id,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    async for event in agent.run(messages):
        yield event
