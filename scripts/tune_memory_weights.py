"""Tune memory retrieval scoring weights + thresholds against the eval set.

Grid-searches the RankerConfig parameter space (lexical mode, no embedding so
the search is deterministic and fast) and reports the config that maximizes
recall@3.

Usage:
    PYTHONPATH=apps/api/src uv run --no-sync python scripts/tune_memory_weights.py
"""

import asyncio
import json
import os
import sys
import uuid
from itertools import product
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from zhiban.db.models import Memory, User
from zhiban.memory.search import RankerConfig, search_memories

sys.path.insert(0, str(Path(__file__).resolve().parent))

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://zhiban:zhiban_dev_only@localhost:5432/zhiban_test",
)
EVAL_FILE = (
    Path(__file__).resolve().parent.parent / "apps" / "api" / "tests" / "eval_memory_retrieval.json"
)


def _recall_at_k(expected: set[str], ranked: list[str], k: int) -> float:
    if not expected:
        return 1.0  # negative query: correct if nothing relevant returned
    hits = len(expected & set(ranked[:k]))
    return hits / len(expected)


async def _evaluate(
    session_factory,
    user_id: uuid.UUID,
    queries: list[dict],
    id_map: dict[str, str],
    config: RankerConfig,
) -> float:
    """Mean recall@3 over the eval set under a given config (lexical mode)."""
    scores: list[float] = []
    async with session_factory() as session:
        for q in queries:
            expected_ids = {id_map[mid] for mid in q["expected"]}
            results = await search_memories(
                session, user_id=user_id, query=q["query"], embedding=None, config=config
            )
            ranked = [str(r.memory.id) for r in results]
            scores.append(_recall_at_k(expected_ids, ranked, 3))
    return sum(scores) / len(scores)


async def main() -> None:
    data = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    pool = data["memory_pool"]
    queries = data["queries"]

    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Seed fixture once (no embedding; lexical-only search space).
    EVAL_EMAIL = "eval-retrieval@example.com"
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.email == EVAL_EMAIL))
        ).scalar_one_or_none()
        if user is None:
            user = User(email=EVAL_EMAIL, password_hash="x", display_name="eval")
            session.add(user)
            await session.flush()
        await session.execute(delete(Memory).where(Memory.user_id == user.id))
        await session.flush()
        id_map: dict[str, str] = {}
        for item in pool:
            content = f"{item['subject']} {item['predicate']} {item['value']}"
            mem = Memory(
                user_id=user.id,
                memory_type=item["memory_type"],
                subject=item["subject"],
                predicate=item["predicate"],
                value=item["value"],
                content=content,
                source_kind="implicit",
                status="active",
                confidence=item.get("confidence", 1.0),
                importance=item.get("importance", 0.5),
                fingerprint=uuid.uuid4().hex,
                conflict_key=uuid.uuid4().hex,
                source_message_ids=[],
                evidence_quote="",
            )
            session.add(mem)
            await session.flush()
            id_map[item["id"]] = str(mem.id)
        await session.commit()
        user_id = user.id

    # Search space (lexical mode: vector weight is irrelevant, keep small).
    lexical_weights = [0.20, 0.25, 0.30, 0.35, 0.40]
    recency_weights = [0.10, 0.15, 0.20]
    min_final_scores = [0.45, 0.50, 0.55, 0.60]
    min_max_signals = [0.20, 0.30, 0.40]

    best = (0.0, None)
    total = (
        len(lexical_weights)
        * len(recency_weights)
        * len(min_final_scores)
        * len(min_max_signals)
    )
    done = 0
    for wl, wr, mfs, mms in product(
        lexical_weights, recency_weights, min_final_scores, min_max_signals
    ):
        # Keep other weights fixed at defaults; importance/confidence/type sum
        # is constant, only lexical + recency reallocated.
        config = RankerConfig(
            w_lexical=wl,
            w_recency=wr,
            min_final_score=mfs,
            min_max_signal=mms,
        )
        mean_recall = await _evaluate(session_factory, user_id, queries, id_map, config)
        done += 1
        if mean_recall > best[0]:
            best = (mean_recall, config)
        if done % 40 == 0 or done == total:
            print(f"  进度 {done}/{total}  当前最优 recall@3 = {best[0]:.3f}")

    print("\n=== 调优结果 ===")
    print(f"最优 recall@3 = {best[0]:.3f}")
    c = best[1]
    print(f"  w_lexical = {c.w_lexical}")
    print(f"  w_recency = {c.w_recency}")
    print(f"  min_final_score = {c.min_final_score}")
    print(f"  min_max_signal = {c.min_max_signal}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
