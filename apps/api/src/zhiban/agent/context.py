"""Context assembly with token budget, recent window, and rolling summary."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from zhiban.agent.prompts import compose_system_prompt
from zhiban.core.token_budget import TokenBudget, estimate_tokens
from zhiban.llm.base import ChatMessage

# The full system prompt is composed from base + tool_use + memory_rules.
SYSTEM_PROMPT = compose_system_prompt()

# Structured schema for rolling summaries (SPEC-AG-046).
SUMMARY_SCHEMA_HINT = (
    "请输出一个 JSON 对象，字段为："
    "goals（数组）、decisions（数组）、open_questions（数组）、"
    "constraints（数组）、referenced_entities（数组）、"
    "tool_facts（数组，每项为 {fact, source_tool_call_id}）。"
)


@dataclass(slots=True)
class ConversationSummary:
    summary: dict[str, Any]
    from_message_id: uuid.UUID | None = None
    through_message_id: uuid.UUID | None = None
    token_count: int = 0
    model: str = ""


@dataclass(slots=True)
class ContextSnapshot:
    messages: list[ChatMessage]
    system_tokens: int
    summary_tokens: int
    recent_window_tokens: int
    current_user_tokens: int
    tool_results_tokens: int
    total_tokens: int
    compacted: bool = False


@dataclass(slots=True)
class ToolResultRecord:
    tool_call_id: str
    tool_name: str
    summary: str
    citations: list[str] = field(default_factory=list)
    ok: bool = True
    error_code: str | None = None


class ContextManager:
    """Assembles the ordered context and folds stale tool results."""

    def __init__(self, budget: TokenBudget) -> None:
        self.budget = budget

    def build_messages(
        self,
        *,
        recent: list[ChatMessage],
        current_user: str,
        summary: ConversationSummary | None = None,
        memories: list[ChatMessage] | None = None,
        tool_results: list[ToolResultRecord] | None = None,
    ) -> ContextSnapshot:
        messages: list[ChatMessage] = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        summary_tokens = 0
        if summary is not None:
            content = self._render_summary(summary)
            summary_tokens = estimate_tokens(content)
            messages.append(ChatMessage(role="system", content=content))

        if memories:
            messages.extend(memories)

        # Recent window: keep within the recent-window budget, dropping oldest.
        kept: list[ChatMessage] = []
        window_used = 0
        for msg in reversed(recent):
            cost = estimate_tokens(msg.content)
            if window_used + cost > self.budget.recent_window and kept:
                break
            kept.append(msg)
            window_used += cost
        messages.extend(reversed(kept))

        messages.append(ChatMessage(role="user", content=current_user))

        tool_result_tokens = 0
        if tool_results:
            for record in tool_results:
                rendered = self._render_tool_result(record)
                tool_result_tokens += estimate_tokens(rendered)
                messages.append(ChatMessage(role="tool", content=rendered))

        return ContextSnapshot(
            messages=messages,
            system_tokens=estimate_tokens(SYSTEM_PROMPT),
            summary_tokens=summary_tokens,
            recent_window_tokens=window_used,
            current_user_tokens=estimate_tokens(current_user),
            tool_results_tokens=tool_result_tokens,
            total_tokens=sum(estimate_tokens(m.content) for m in messages),
        )

    def _render_summary(self, summary: ConversationSummary) -> str:
        parts = ["[历史对话摘要]"]
        for key in ("goals", "decisions", "open_questions", "constraints", "referenced_entities"):
            value = summary.summary.get(key)
            if value:
                parts.append(f"{key}: {value}")
        tool_facts = summary.summary.get("tool_facts")
        if tool_facts:
            facts = []
            for fact in tool_facts:
                if isinstance(fact, dict):
                    facts.append(str(fact.get("fact", "")))
            if facts:
                parts.append("tool_facts: " + "; ".join(facts))
        return "\n".join(parts)

    def _render_tool_result(self, record: ToolResultRecord) -> str:
        status = "成功" if record.ok else f"失败({record.error_code or '未知'})"
        text = f"[工具 {record.tool_name} {status}] {record.summary}"
        if record.citations:
            text += "\n来源: " + ", ".join(record.citations)
        return text


def fold_tool_result(record: ToolResultRecord, *, max_chars: int = 500) -> str:
    """Fold a stale tool result into a bounded structural summary."""
    summary = record.summary
    if len(summary) > max_chars:
        summary = summary[:max_chars] + "…"
    status = "成功" if record.ok else f"失败({record.error_code or '未知'})"
    text = f"[{record.tool_name} {status}] {summary}"
    if record.citations:
        text += f" 来源: {' '.join(record.citations[:3])}"
    return text
