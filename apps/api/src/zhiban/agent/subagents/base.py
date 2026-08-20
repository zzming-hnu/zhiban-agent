"""Shared base for tool-calling sub-agents (bounded mini-ReAct loop)."""

import json
import uuid
from typing import Any

import structlog

from zhiban.agent.subagent import SubAgentContext, SubAgentResult
from zhiban.llm.base import ChatMessage, LLMAdapter
from zhiban.tools.base import ToolContext
from zhiban.tools.executor import ToolExecutor
from zhiban.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)

DEFAULT_MAX_TOOL_ROUNDS = 3


class ToolCallingSubAgent:
    """A sub-agent that runs a bounded tool-calling loop and returns a summary.

    Subclasses provide ``name``, ``system_prompt``, and a ``ToolRegistry``
    (via ``build_registry``). The loop: LLM decides tool calls -> execute ->
    feed results back -> repeat until no tool calls or round limit, then ask
    the LLM for a final summary.
    """

    name: str = "subagent"
    system_prompt: str = "你是知伴的子代理。"
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS

    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm
        self._registry = self.build_registry()
        self._executor = ToolExecutor()

    def build_registry(self) -> ToolRegistry:
        """Return the tool registry for this sub-agent. Override in subclasses."""
        raise NotImplementedError

    async def run(self, ctx: SubAgentContext) -> SubAgentResult:
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=ctx.user_input),
        ]
        tool_schemas = self._registry.openai_schemas()

        try:
            for _round in range(self.max_tool_rounds):
                response = await self._llm.chat(messages, tools=tool_schemas)
                calls = _extract_tool_calls(response, self._registry)
                if not calls:
                    return SubAgentResult(ok=True, summary=response.content.strip())

                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )
                for call in calls:
                    tool = self._registry.get(call["name"])
                    if tool is None:
                        continue
                    result = await self._executor.execute(
                        tool,
                        ToolContext(
                            user_id=ctx.user_id,
                            run_id=ctx.run_id,
                            conversation_id=ctx.conversation_id,
                        ),
                        call["arguments"],
                    )
                    status_prefix = (
                        "✅ 成功"
                        if result.ok
                        else f"❌ 失败 (error_code={result.error_code or 'unknown'})"
                    )
                    data_text = (
                        json.dumps(result.data, ensure_ascii=False)
                        if result.data
                        else "无"
                    )
                    messages.append(
                        ChatMessage(
                            role="tool",
                            content=f"{status_prefix}\n摘要：{result.summary}\n数据：{data_text}",
                            tool_call_id=call["id"],
                            name=call["name"],
                        )
                    )
            final = await self._llm.chat(messages)
            return SubAgentResult(ok=True, summary=final.content.strip())
        except Exception as exc:  # noqa: BLE001 - sub-agent boundary
            await logger.aexception(
                "subagent_failed", subagent=self.name, error_type=type(exc).__name__
            )
            return SubAgentResult(
                ok=False,
                summary="操作暂时不可用",
                error_code=type(exc).__name__,
            )


def _extract_tool_calls(response: Any, registry: ToolRegistry) -> list[dict[str, Any]]:
    """Normalize tool calls from an LLMResponse, resolving provider names."""
    calls: list[dict[str, Any]] = []
    for tc in response.tool_calls or []:
        func = tc.get("function", {})
        provider_name = func.get("name", "")
        raw_args = func.get("arguments", "{}")
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
        else:
            args = raw_args if isinstance(raw_args, dict) else {}
        name = registry.resolve_tool_name(provider_name) or provider_name
        calls.append(
            {"id": tc.get("id", f"tc_{uuid.uuid4().hex}"), "name": name, "arguments": args}
        )
    return calls
