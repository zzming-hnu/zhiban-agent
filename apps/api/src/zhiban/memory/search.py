"""Hybrid memory retrieval: user-scoped lexical + vector + explainable scoring."""

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.db.models import Memory
from zhiban.memory.lexical import BM25LexicalIndex, lexical_similarity

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


@dataclass(frozen=True, slots=True)
class RankerConfig:
    """Tunable scoring weights and thresholds for memory retrieval.

    Exposing these as a dataclass lets an offline evaluation harness search
    the parameter space and pick data-driven values instead of hard-coded
    guesses.
    """

    w_vector: float = 0.30
    w_lexical: float = 0.20
    w_recency: float = 0.15
    w_importance: float = 0.12
    w_confidence: float = 0.10
    w_type: float = 0.08
    min_vector_similarity: float = 0.55
    min_final_score: float = 0.45
    min_max_signal: float = 0.20

    @property
    def weights(self) -> dict[str, float]:
        return {
            "vector": self.w_vector,
            "lexical": self.w_lexical,
            "recency": self.w_recency,
            "importance": self.w_importance,
            "confidence": self.w_confidence,
            "type": self.w_type,
        }


DEFAULT_RANKER_CONFIG = RankerConfig()


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
    config: RankerConfig = DEFAULT_RANKER_CONFIG,
) -> list[ScoredMemory]:
    """Hybrid retrieval with hard user scoping first.

    Falls back to lexical (jieba + BM25) + recency when ``embedding`` is None.
    Scoring weights and thresholds come from ``config`` so an offline harness
    can tune them against the eval set.
    """
    now = datetime.now(UTC)
    w = config.weights

    # Load all active memories for this user, then score them in Python. The
    # memory set per user is small (tens), so in-memory BM25 is fast and avoids
    # the previous ILIKE substring match that failed for Chinese.
    memories = list(
        (await session.execute(select(Memory).where(*_active_scope(user_id)))).scalars()
    )
    if not memories:
        return []

    # Build a BM25 index over memory contents for lexical scoring.
    bm25 = BM25LexicalIndex([m.content for m in memories])

    scored: dict[uuid.UUID, ScoredMemory] = {}
    for i, mem in enumerate(memories):
        # Lexical signal: token-overlap coverage (robust for small memory sets)
        # blended with BM25 (better ranking when the set is larger).
        coverage = lexical_similarity(query, mem.content)
        bm25_norm = min(1.0, bm25.score(query, i) / 3.0)
        lexical = max(coverage, bm25_norm)
        age_days = max(0.0, (now - mem.updated_at).total_seconds() / 86400)
        recency = _recency(age_days, mem.memory_type)
        score = (
            w["vector"] * 0.0
            + w["lexical"] * lexical
            + w["recency"] * recency
            + w["importance"] * (mem.importance or 0.5)
            + w["confidence"] * (mem.confidence or 1.0)
            + w["type"] * 1.0
        )
        scored[mem.id] = ScoredMemory(
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
            # A memory without an embedding (degraded write) yields a NULL
            # distance; skip it rather than crash.
            if distance is None:
                continue
            similarity = max(0.0, 1.0 - float(distance))
            if similarity < config.min_vector_similarity:
                continue
            age_days = max(0.0, (now - mem.updated_at).total_seconds() / 86400)
            recency = _recency(age_days, mem.memory_type)
            lexical = scored[mem.id].breakdown["lexical"] if mem.id in scored else 0.0
            score = (
                w["vector"] * similarity
                + w["lexical"] * lexical
                + w["recency"] * recency
                + w["importance"] * (mem.importance or 0.5)
                + w["confidence"] * (mem.confidence or 1.0)
                + w["type"] * 1.0
            )
            scored[mem.id] = ScoredMemory(
                mem, score, {"lexical": lexical, "recency": recency, "vector": similarity}
            )

    # Filter by injection threshold and sort.
    results = [
        s
        for s in scored.values()
        if s.score >= config.min_final_score
        and max(s.breakdown["vector"], s.breakdown["lexical"]) >= config.min_max_signal
    ]
    results.sort(key=lambda s: s.score, reverse=True)
    return results[:limit]
