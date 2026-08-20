"""Hybrid memory retrieval: user-scoped lexical + vector + explainable scoring."""

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.db.models import Memory

# Scoring weights (sum to 1.0).
_W_VECTOR = 0.30
_W_LEXICAL = 0.25
_W_RECENCY = 0.15
_W_IMPORTANCE = 0.12
_W_CONFIDENCE = 0.10
_W_TYPE = 0.08

# Thresholds.
MIN_VECTOR_SIMILARITY = 0.55
MIN_FINAL_SCORE = 0.62
MIN_MAX_SIGNAL = 0.45

# Half-lives in days per memory type (for recency decay).
_HALF_LIFE_DAYS = {
    "temporary": 3,
    "event": 30,
    "task": 30,
    "habit": 90,
    "preference": 180,
    "person": 180,
    "identity": 365,
    "communication": 365,
}


@dataclass(slots=True)
class ScoredMemory:
    memory: Memory
    score: float
    breakdown: dict[str, float]


def _active_scope(user_id: uuid.UUID) -> tuple[ColumnElement[bool], ...]:
    return (
        Memory.user_id == user_id,
        Memory.status == "active",
        Memory.deleted_at.is_(None),
        (Memory.expires_at.is_(None)) | (Memory.expires_at > func.now()),
    )


def _recency(age_days: float, memory_type: str) -> float:
    half_life = _HALF_LIFE_DAYS.get(memory_type, 180)
    return math.exp(-age_days / half_life)


async def search_memories(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    query: str,
    embedding: list[float] | None,
    limit: int = 6,
) -> list[ScoredMemory]:
    """Hybrid retrieval with hard user scoping first.

    Falls back to lexical + recency when ``embedding`` is None (degraded mode).
    """
    now = datetime.now(UTC)

    # Lexical recall (tsvector) is not yet populated via a trigger; use ILIKE
    # on content as the lexical signal for the first version.
    lexical_results = await session.execute(
        select(Memory).where(*_active_scope(user_id), Memory.content.ilike(f"%{query}%")).limit(20)
    )
    lexical_hits = {m.id: m for m in lexical_results.scalars()}

    scored: dict[uuid.UUID, ScoredMemory] = {}
    query_terms = query.split()

    for mem_id, mem in lexical_hits.items():
        lexical = 1.0 if any(term.lower() in mem.content.lower() for term in query_terms) else 0.3
        age_days = max(0.0, (now - mem.updated_at).total_seconds() / 86400)
        recency = _recency(age_days, mem.memory_type)
        vector = 0.0
        score = (
            _W_VECTOR * vector
            + _W_LEXICAL * lexical
            + _W_RECENCY * recency
            + _W_IMPORTANCE * (mem.importance or 0.5)
            + _W_CONFIDENCE * (mem.confidence or 1.0)
            + _W_TYPE * 1.0
        )
        scored[mem_id] = ScoredMemory(
            mem, score, {"lexical": lexical, "recency": recency, "vector": 0.0}
        )

    # Vector recall if embedding is available.
    if embedding is not None:
        vector_results = await session.execute(
            select(Memory, Memory.embedding.cosine_distance(embedding).label("distance"))
            .where(*_active_scope(user_id))
            .order_by("distance")
            .limit(20)
        )
        for mem, distance in vector_results.all():
            similarity = max(0.0, 1.0 - float(distance))
            if similarity < MIN_VECTOR_SIMILARITY:
                continue
            age_days = max(0.0, (now - mem.updated_at).total_seconds() / 86400)
            recency = _recency(age_days, mem.memory_type)
            lexical = scored[mem.id].breakdown["lexical"] if mem.id in scored else 0.0
            score = (
                _W_VECTOR * similarity
                + _W_LEXICAL * lexical
                + _W_RECENCY * recency
                + _W_IMPORTANCE * (mem.importance or 0.5)
                + _W_CONFIDENCE * (mem.confidence or 1.0)
                + _W_TYPE * 1.0
            )
            scored[mem.id] = ScoredMemory(
                mem, score, {"lexical": lexical, "recency": recency, "vector": similarity}
            )

    # Filter by injection threshold and sort.
    results = [
        s
        for s in scored.values()
        if s.score >= MIN_FINAL_SCORE
        and max(s.breakdown["vector"], s.breakdown["lexical"]) >= MIN_MAX_SIGNAL
    ]
    results.sort(key=lambda s: s.score, reverse=True)
    return results[:limit]
