"""Semantic deduplication for memories.

The extractor now emits a natural-language ``fact`` (e.g. "用户喜欢吃辣") rather
than a subject/predicate/value triple. Because the LLM words the same fact
slightly differently on each extraction ("用户喜欢吃辣" vs "用户喜欢吃辣的食物"),
exact-text fingerprinting is not enough to prevent duplicates across the two
write paths (explicit ``memory.add`` vs implicit ``flush``).

This module provides a conservative lexical-similarity dedupe: two facts are
considered "the same" only when their token overlap is high (>= DEDUP_THRESHOLD)
in *both* directions. It is deterministic, needs no external embedding service,
and is used both at write time (flush) and by the periodic consolidation pass.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.memory.lexical import lexical_similarity
from zhiban.memory.normalize import normalize_text

# Conservative threshold: only merge when facts are near-identical. We prefer
# false negatives (a rare duplicate survives) over false positives (two distinct
# facts wrongly merged), which would silently destroy user information.
DEDUP_THRESHOLD = 0.80

# Negation markers. Two facts with opposite polarity ("喜欢" vs "不喜欢") are
# semantically distinct and must NOT be deduped, even though their lexical
# overlap is high. A fact and its negation are an *evolution* (handled by the
# supersede chain), not a duplicate.
_NEGATION_MARKERS = ("不", "没", "无", "别", "非", "否认", "拒绝")


def _has_negation(text: str) -> bool:
    return any(marker in text for marker in _NEGATION_MARKERS)


def fact_similarity(a: str, b: str) -> float:
    """Symmetric lexical similarity between two facts, in [0, 1].

    Returns 0.0 when the two facts have opposite negation polarity (one says
    "喜欢", the other "不喜欢"), so a fact and its negation are never merged as
    duplicates. Otherwise uses the min of both directional token overlaps.
    """
    na = normalize_text(a)
    nb = normalize_text(b)
    if not na or not nb:
        return 0.0
    # Opposite polarity -> never a duplicate.
    if _has_negation(na) != _has_negation(nb):
        return 0.0
    # Symmetric: require high overlap in both directions.
    return min(lexical_similarity(na, nb), lexical_similarity(nb, na))


async def find_similar_active_memory(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    fact: str,
    threshold: float = DEDUP_THRESHOLD,
) -> object | None:
    """Return an existing active memory semantically similar to ``fact``.

    Returns the first active memory (for this user) whose ``content`` is within
    ``threshold`` of ``fact``, or None. Used at write time to skip re-adding an
    already-remembered fact.
    """
    from zhiban.db.models import Memory
    from sqlalchemy import select

    memories = list(
        (
            await session.execute(
                select(Memory).where(
                    Memory.user_id == user_id,
                    Memory.status == "active",
                    Memory.deleted_at.is_(None),
                )
            )
        ).scalars()
    )
    for mem in memories:
        if fact_similarity(fact, mem.content) >= threshold:
            return mem
    return None
