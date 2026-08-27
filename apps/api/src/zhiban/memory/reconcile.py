"""Semantic reconciliation of a new fact against existing memories.

When the user explicitly asks to remember something, we want the model to decide
whether this is a *new* fact, an *update* to an existing fact, a *supersession*
(the fact reversed: "喜欢" -> "不喜欢"), or a *duplicate* to ignore — rather than
blindly adding a near-duplicate.

The model only **proposes**; the caller deterministically validates the target
memory (must exist and belong to this user) before applying anything. This keeps
model intelligence without letting a hallucinated id corrupt storage.
"""

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.db.models import Memory
from zhiban.llm.base import ChatMessage, LLMAdapter
from zhiban.memory.dedup import fact_similarity


@dataclass(slots=True)
class ReconcileDecision:
    action: str  # "add" | "update" | "supersede" | "ignore"
    target: Memory | None = None
    new_fact: str | None = None


_RECONCILE_SYSTEM = (
    "你是记忆调和器。给定一条新事实和用户现有的相关记忆，判断该如何处理这条新事实，"
    "输出严格 JSON。\n"
    "\n"
    "四种动作：\n"
    "- add：新事实是全新的，与现有记忆无关，直接新增。\n"
    "- ignore：新事实与某条现有记忆语义完全相同（重复），忽略，不要重复记。\n"
    "- update：新事实是对某条现有记忆的补充/修正（同一件事，但内容更完整或措辞更好），"
    "更新那条记忆的内容。\n"
    "- supersede：新事实与某条现有记忆**正相反**（如「喜欢」变「不喜欢」），"
    "用新事实取代旧记忆。\n"
    "\n"
    "输出格式（严格 JSON，不要任何其它文字）：\n"
    "{\n"
    "  \"action\": \"add\" | \"ignore\" | \"update\" | \"supersede\",\n"
    "  \"target_id\": \"<要操作的旧记忆 id，仅 update/supersede/ignore 需要，否则省略>\",\n"
    "  \"new_fact\": \"<合并/修正后的新事实文本，仅 update 需要，否则省略>\",\n"
    "  \"reason\": \"<一句话原因>\"\n"
    "}\n"
    "\n"
    "规则：\n"
    "1. 只输出 JSON 对象。\n"
    "2. target_id 必须是输入中真实存在的记忆 id，不要编造。\n"
    "3. 拿不准时用 add（宁多勿错删）。\n"
)


def _user_prompt(new_fact: str, candidates: list[Memory]) -> str:
    lines = ["新事实：", f"  {new_fact}", "", "用户现有的相关记忆："]
    for m in candidates:
        lines.append(f"  - id={m.id} | content={m.content}")
    lines.append("")
    lines.append("请判断如何处理新事实，输出 JSON。")
    return "\n".join(lines)


def _parse(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def reconcile_memory(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    new_fact: str,
    llm: LLMAdapter,
    top_k: int = 5,
) -> ReconcileDecision:
    """Decide how ``new_fact`` relates to the user's existing memories.

    Coarse-filters candidate memories by lexical similarity (cheap) and only
    asks the LLM when there is at least one plausible candidate. Returns a
    decision the caller must still validate.
    """
    memories = list(
        (
            await session.execute(
                select(Memory).where(
                    Memory.user_id == user_id,
                    Memory.status == "active",
                    Memory.deleted_at.is_(None),
                )
            )
        )
        .scalars()
    )
    if not memories:
        return ReconcileDecision(action="add")

    # Coarse filter: keep top_k by lexical similarity.
    ranked = sorted(
        memories,
        key=lambda m: fact_similarity(new_fact, m.content),
        reverse=True,
    )
    candidates = [m for m in ranked[:top_k] if fact_similarity(new_fact, m.content) > 0.0]
    if not candidates:
        return ReconcileDecision(action="add")

    try:
        response = await llm.chat(
            [
                ChatMessage(role="system", content=_RECONCILE_SYSTEM),
                ChatMessage(role="user", content=_user_prompt(new_fact, candidates)),
            ]
        )
    except Exception:  # noqa: BLE001 - reconcile is best-effort
        return ReconcileDecision(action="add")

    result = _parse(response.content)
    action = result.get("action", "add")
    if action not in ("add", "ignore", "update", "supersede"):
        action = "add"

    # Validate target id (deterministic safety net against hallucinated ids).
    target: Memory | None = None
    raw_target = result.get("target_id")
    if raw_target:
        try:
            tid = uuid.UUID(str(raw_target))
        except (ValueError, TypeError):
            tid = None
        for m in candidates:
            if m.id == tid:
                target = m
                break

    # update/supersede/ignore require a valid target; otherwise fall back to add.
    if action in ("update", "supersede", "ignore") and target is None:
        action = "add"

    new_fact_text = result.get("new_fact") or new_fact

    return ReconcileDecision(action=action, target=target, new_fact=new_fact_text)
