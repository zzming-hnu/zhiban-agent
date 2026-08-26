"""Memory retrieval evaluation harness.

Runs ``search_memories`` against a fixture of memories and queries, computing
recall@k / nDCG@k / MRR. Uses the real embedding adapter (from .env) by
default so the baseline reflects true semantic retrieval. Pass ``--lexical``
to evaluate the degraded (no-embedding) path.

Usage:
    PYTHONPATH=apps/api/src uv run python scripts/eval_memory_retrieval.py
    PYTHONPATH=apps/api/src uv run python scripts/eval_memory_retrieval.py --lexical
"""

import asyncio
import json
import math
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from zhiban.core.config import Settings
from zhiban.db.models import Memory, User
from zhiban.llm.factory import create_embedding_adapter
from zhiban.memory.search import search_memories

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://zhiban:zhiban_dev_only@localhost:5432/zhiban_test",
)

EVAL_FILE = (
    Path(__file__).resolve().parent.parent
    / "apps"
    / "api"
    / "tests"
    / "eval_memory_retrieval.json"
)

def _avg_precision(expected: set[str], ranked: list[str], k: int) -> float:
    """Average precision at k (ranked = memory ids returned in order)."""
    hits = 0
    score = 0.0
    for i, mid in enumerate(ranked[:k]):
        if mid in expected:
            hits += 1
            score += hits / (i + 1)
    return score / min(len(expected), k) if expected else 0.0


def _dcg(expected: set[str], ranked: list[str], k: int) -> float:
    dcg = 0.0
    for i, mid in enumerate(ranked[:k]):
        if mid in expected:
            dcg += 1.0 / math.log2(i + 2)
    return dcg


def _ndcg(expected: set[str], ranked: list[str], k: int) -> float:
    dcg = _dcg(expected, ranked, k)
    ideal = _dcg(expected, list(expected), k)
    return dcg / ideal if ideal else 0.0


async def _run_eval(lexical_only: bool = False) -> None:
    data = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    pool = data["memory_pool"]
    queries = data["queries"]

    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Real embedding adapter (bge-m3 via SiliconFlow), unless --lexical.
    embedding = None
    if not lexical_only:
        settings = Settings()
        embedding = create_embedding_adapter(settings)

    async with session_factory() as session:
        # Fresh fixture: reuse a fixed eval user and clear only its memories.
        EVAL_EMAIL = "eval-retrieval@example.com"
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
            vec = None
            if embedding is not None:
                vec = await embedding.embed(content)
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
                embedding=vec,
            )
            session.add(mem)
            await session.flush()
            id_map[item["id"]] = str(mem.id)
        await session.commit()

        k = 3
        recalls = {kk: [] for kk in [1, 3, 5]}
        ndcgs = []
        mrrs = []
        mode = "词法降级" if lexical_only else "语义+词法"
        print(f"模式: {mode}")
        print(f"{'query':<28} {'期望':<12} {'命中/排名'}")
        print("-" * 70)

        for q in queries:
            expected_ids = {id_map[mid] for mid in q["expected"]}
            qvec = None
            if embedding is not None:
                try:
                    qvec = await embedding.embed(q["query"])
                except Exception:  # noqa: BLE001 - fall back to lexical
                    qvec = None
            results = await search_memories(
                session, user_id=user.id, query=q["query"], embedding=qvec
            )
            ranked = [str(r.memory.id) for r in results]

            for kk in recalls:
                hits = len(expected_ids & set(ranked[:kk]))
                recalls[kk].append(hits / len(expected_ids) if expected_ids else 0.0)
            ndcgs.append(_ndcg(expected_ids, ranked, k))
            rr = 0.0
            for i, mid in enumerate(ranked):
                if mid in expected_ids:
                    rr = 1.0 / (i + 1)
                    break
            mrrs.append(rr)

            expected_labels = ",".join(q["expected"]) or "(负例)"
            hit_ranks = [ranked.index(e) + 1 for e in expected_ids if e in ranked]
            print(
                f"{q['query']:<28} {expected_labels:<12} "
                f"命中 {len(hit_ranks)}/{len(expected_ids)} 排名 {hit_ranks}"
            )

    if embedding is not None:
        await embedding.aclose()

    print("-" * 70)
    print("\n=== 评测结果 ===")
    for kk in recalls:
        print(f"recall@{kk} = {sum(recalls[kk]) / len(recalls[kk]):.3f}")
    print(f"nDCG@{k}    = {sum(ndcgs) / len(ndcgs):.3f}")
    print(f"MRR        = {sum(mrrs) / len(mrrs):.3f}")

    await engine.dispose()


if __name__ == "__main__":
    lexical = "--lexical" in sys.argv
    asyncio.run(_run_eval(lexical_only=lexical))
