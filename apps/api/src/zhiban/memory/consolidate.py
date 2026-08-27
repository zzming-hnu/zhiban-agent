"""Memory consolidation: dedupe redundant and resolve conflicting memories.

Unlike the per-run extractor (which turns raw messages into structured facts),
consolidation is a low-frequency "tidy up" pass over the user's existing active
memories. It asks the LLM to propose which memories are:

- **redundant**: semantically duplicated facts that can be collapsed into one, or
- **conflicting**: the same slot (type+subject+predicate) with contradictory
  values, where the newer fact supersedes the older one.

The LLM only *proposes*; the service applies the proposals deterministically by
marking superseded memories via ``superseded_by_id`` (reusing the evolution-chain
mechanism), never deleting evidence.
"""

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.db.models import Memory
from zhiban.llm.base import ChatMessage, LLMAdapter
from zhiban.memory.types import MemoryStatus


# Consolidation is a best-effort pass; only run when the user has accumulated
# enough active memories for redundancy/conflict to be likely.
DEFAULT_CONSOLIDATE_THRESHOLD = 15


@dataclass(slots=True)
class ConsolidateResult:
    superseded: int
    reason: str | None = None


_CONSOLIDATE_SYSTEM = (
    "你是记忆整理器。输入是用户当前所有活跃记忆（每条含 id 和 content），"
    "请识别其中的冗余与矛盾，输出严格 JSON 对象。\n"
    "\n"
    "任务：\n"
    "1. 找出语义重复的记忆（表达同一件事的多条），保留一条最新的，其余标记为冗余。\n"
    "2. 找出互相矛盾的记忆（同一主体/谓词下值相反，如「不吃辣」vs「能吃辣」），"
    "保留最新的一条，旧的标记为被取代。\n"
    "\n"
    "输出格式（严格 JSON，不要任何其它文字）：\n"
    "{\n"
    "  \"supersede\": [\n"
    "    {\"superseded_id\": \"<被取代的记忆id>\", \"kept_id\": \"<保留的记忆id>\", \"reason\": \"<一句话原因>\"}\n"
    "  ]\n"
    "}\n"
    "\n"
    "规则：\n"
    "1. 只输出确实冗余或矛盾的记忆对，宁缺毋滥，不确定就留空数组。\n"
    "2. superseded_id 和 kept_id 必须是输入中真实存在的 id。\n"
    "3. 保留的记忆（kept_id）应是更新、更准确的那条。\n"
    "4. 不要合并内容、不要新造记忆，只做「保留谁、淘汰谁」的判断。\n"
    "5. 只输出 JSON 对象。"
)


def _consolidate_user_prompt(memories: list[Memory]) -> str:
    lines = ["以下是用户的活跃记忆："]
    for m in memories:
        lines.append(f"- id={m.id} | content={m.content}")
    lines.append("\n请识别冗余和矛盾的记忆，输出 JSON。")
    return "\n".join(lines)


def _parse_result(raw: str) -> dict:
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


async def consolidate_memories(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    llm: LLMAdapter,
    threshold: int = DEFAULT_CONSOLIDATE_THRESHOLD,
) -> ConsolidateResult:
    """Consolidate a user's active memories (dedupe + resolve conflicts).

    Loads all active memories, asks the LLM to propose supersessions, then
    deterministically applies them. Returns how many memories were superseded.
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
        .all()
    )
    if len(memories) < threshold:
        return ConsolidateResult(superseded=0, reason="below_threshold")

    # --- Phase 1: deterministic semantic dedupe (no LLM) ---
    # Merge near-duplicate facts (token overlap >= threshold). Keep the most
    # recently updated one, supersede the rest. This is deterministic and
    # conservative, so it never wrongly merges two distinct facts.
    from zhiban.memory.dedup import DEDUP_THRESHOLD, fact_similarity

    superseded = 0
    # Sort by updated_at ascending so the newest is processed last and wins.
    ordered = sorted(memories, key=lambda m: m.updated_at)
    kept_ids: set[uuid.UUID] = set()
    for i, mem in enumerate(ordered):
        if mem.id in kept_ids:
            continue
        for other in ordered[i + 1 :]:
            if other.id in kept_ids:
                continue
            if fact_similarity(mem.content, other.content) >= DEDUP_THRESHOLD:
                # `other` is newer (sorted ascending) -> it supersedes `mem`.
                mem.status = MemoryStatus.superseded
                mem.superseded_by_id = other.id
                kept_ids.add(mem.id)
                superseded += 1
                break

    # --- Phase 2: LLM proposes redundancy/conflict supersessions ---
    try:
        response = await llm.chat(
            [
                ChatMessage(role="system", content=_CONSOLIDATE_SYSTEM),
                ChatMessage(role="user", content=_consolidate_user_prompt(memories)),
            ]
        )
    except Exception:  # noqa: BLE001 - consolidation is best-effort
        if superseded:
            await session.commit()
        return ConsolidateResult(superseded=superseded, reason="llm_error_after_dedup")

    result = _parse_result(response.content)
    proposals = result.get("supersede", [])
    if not isinstance(proposals, list):
        if superseded:
            await session.commit()
        return ConsolidateResult(superseded=superseded, reason="no_proposals")

    # Index active memories by id for deterministic validation.
    by_id: dict[uuid.UUID, Memory] = {}
    for m in memories:
        by_id[m.id] = m

    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        try:
            superseded_id = uuid.UUID(str(proposal.get("superseded_id", "")))
            kept_id = uuid.UUID(str(proposal.get("kept_id", "")))
        except (ValueError, TypeError):
            continue

        # Both must be real active memories of this user, and not the same.
        old = by_id.get(superseded_id)
        kept = by_id.get(kept_id)
        if old is None or kept is None or old.id == kept.id:
            continue

        # Apply supersession deterministically.
        old.status = MemoryStatus.superseded
        old.superseded_by_id = kept.id
        superseded += 1

    if superseded:
        await session.commit()
    return ConsolidateResult(superseded=superseded)


async def count_active_memories(session: AsyncSession, *, user_id: uuid.UUID) -> int:
    """Return the number of active memories for a user (for threshold checks)."""
    from sqlalchemy import func

    return (
        await session.execute(
            select(func.count())
            .select_from(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.status == "active",
                Memory.deleted_at.is_(None),
            )
        )
    ).scalar_one()
