"""Context compaction: rolling summary generation when the token budget is exceeded."""

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.agent.context import SYSTEM_PROMPT, ContextManager, ConversationSummary
from zhiban.core.config import Settings
from zhiban.core.token_budget import estimate_tokens
from zhiban.db.models import ConversationSummary as SummaryRecord
from zhiban.db.models import Message
from zhiban.llm.base import ChatMessage, LLMAdapter


@dataclass(slots=True)
class CompactedContext:
    messages: list[ChatMessage]
    summary: ConversationSummary | None
    compacted: bool


def _render_summary_prompt(messages: list[ChatMessage]) -> str:
    """Build a prompt that asks the model to summarize old turns structurally."""
    lines = ["请将以下对话历史压缩为结构化的滚动摘要。", "", "对话内容："]
    for msg in messages:
        role = "用户" if msg.role == "user" else "助手"
        lines.append(f"{role}: {msg.content}")
    lines.append("")
    lines.append(
        "请输出 JSON，字段为 goals/decisions/open_questions/constraints/"
        "referenced_entities/tool_facts（tool_facts 为 [{fact, source_tool_call_id}] 数组）。"
        "只输出 JSON，不要其它文字。"
    )
    return "\n".join(lines)


async def _generate_summary(
    summary_llm: LLMAdapter, messages: list[ChatMessage]
) -> ConversationSummary:
    prompt = _render_summary_prompt(messages)
    try:
        response = await summary_llm.chat([ChatMessage(role="user", content=prompt)])
    except Exception:  # noqa: BLE001 - summary is best-effort
        return ConversationSummary(
            summary={"constraints": ["（摘要生成失败，已保留原文截断）"]},
            token_count=0,
            model=summary_llm.model,
        )

    raw = response.content.strip()
    # Strip markdown code fences if present.
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3]
    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"constraints": ["（摘要解析失败）"]}
    if not isinstance(parsed, dict):
        parsed = {"constraints": ["（摘要结构异常）"]}

    return ConversationSummary(
        summary=parsed,
        token_count=estimate_tokens(json.dumps(parsed, ensure_ascii=False)),
        model=summary_llm.model,
    )


async def load_latest_summary(
    session: AsyncSession, *, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> ConversationSummary | None:
    result = await session.execute(
        select(SummaryRecord)
        .where(
            SummaryRecord.user_id == user_id,
            SummaryRecord.conversation_id == conversation_id,
        )
        .order_by(SummaryRecord.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    return ConversationSummary(
        summary=record.summary,
        from_message_id=record.from_message_id,
        through_message_id=record.through_message_id,
        token_count=record.token_count,
        model=record.model,
    )


async def build_context_with_compaction(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user_message_id: uuid.UUID,
    settings: Settings,
    summary_llm: LLMAdapter,
    context_manager: ContextManager,
) -> CompactedContext:
    """Load history and compact it to fit the token budget.

    Strategy:
    - Load full history (user + assistant messages).
    - Estimate the token usage of the current user message + system prompt.
    - If over the soft threshold, fold the oldest turns into a rolling summary.
    - Keep the most recent `keep_recent_turns` turns intact.
    """
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.user_id == user_id,
            Message.deleted_at.is_(None),
        )
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    all_messages = list(result.scalars())

    history: list[ChatMessage] = [
        ChatMessage(role=m.role, content=m.content)
        for m in all_messages
        if m.role in ("user", "assistant") and m.id != current_user_message_id
    ]
    current_user = ChatMessage(role="user", content="")
    for m in all_messages:
        if m.id == current_user_message_id:
            current_user = ChatMessage(role="user", content=m.content)

    # Estimate current usage.
    base_tokens = estimate_tokens(SYSTEM_PROMPT) + estimate_tokens(current_user.content)
    history_tokens = sum(estimate_tokens(m.content) for m in history)

    soft_limit = int(settings.model_context_window * settings.context_soft_threshold_ratio)
    hard_limit = int(settings.model_context_window * settings.context_hard_threshold_ratio)

    latest_summary = await load_latest_summary(
        session, user_id=user_id, conversation_id=conversation_id
    )

    total = base_tokens + history_tokens + (latest_summary.token_count if latest_summary else 0)

    compacted = False
    if total > soft_limit:
        compacted = True
        # Fold the oldest turns into a summary, keep recent turns.
        keep_turns = settings.context_keep_recent_turns
        keep_messages = history[-keep_turns * 2 :] if len(history) > keep_turns * 2 else history
        to_summarize = history[: -len(keep_messages)] if len(history) > len(keep_messages) else []

        if to_summarize:
            new_summary = await _generate_summary(summary_llm, to_summarize)
            if latest_summary is not None:
                merged = dict(latest_summary.summary)
                for key, value in new_summary.summary.items():
                    if key in merged and isinstance(merged[key], list) and isinstance(value, list):
                        merged[key] = merged[key] + value
                    else:
                        merged[key] = value
                new_summary.summary = merged
            latest_summary = new_summary
            # Persist the new summary record.
            first = all_messages[0]
            through = all_messages[len(to_summarize) - 1]
            session.add(
                SummaryRecord(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    from_message_id=first.id,
                    through_message_id=through.id,
                    summary=latest_summary.summary,
                    token_count=latest_summary.token_count,
                    model=latest_summary.model,
                )
            )
            await session.flush()

        history = keep_messages

    # Hard limit: if still over, drop more history (keep at least current user).
    total = base_tokens + sum(estimate_tokens(m.content) for m in history)
    if total > hard_limit:
        while history and total > hard_limit:
            dropped = history.pop(0)
            total -= estimate_tokens(dropped.content)

    # Build the final message list.
    messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
    if latest_summary is not None:
        messages.append(
            ChatMessage(
                role="system",
                content="[历史对话摘要]\n" + json.dumps(latest_summary.summary, ensure_ascii=False),
            )
        )
    messages.extend(history)
    messages.append(current_user)

    return CompactedContext(messages=messages, summary=latest_summary, compacted=compacted)
