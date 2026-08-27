"""线上验证记忆整合：构造矛盾+冗余记忆 → 触发整合 → 验证 supersede 结果。

用法（在服务器上）：
  docker exec zhiban-prod-app-1 python /tmp/verify_memory_consolidate.py
"""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from zhiban.core.config import get_settings
from zhiban.db.models import Memory
from zhiban.llm.factory import create_llm_adapter
from zhiban.memory.consolidate import consolidate_memories
from zhiban.memory.service import MemoryService


async def _seed(session, uid: uuid.UUID, memory_type: str, subject: str, predicate: str, value: str) -> None:
    """Directly insert a memory (bypassing candidate pipeline) for a quick seed."""
    from zhiban.memory.ids import conflict_key, memory_fingerprint
    from zhiban.memory.normalize import normalize_text
    from zhiban.memory.types import MemoryStatus, SourceKind

    mem = Memory(
        user_id=uid,
        memory_type=memory_type,
        category="other",
        subject=normalize_text(subject),
        predicate=normalize_text(predicate),
        value=normalize_text(value),
        content=f"{subject} {predicate} {value}".strip(),
        source_kind=SourceKind.explicit,
        status=MemoryStatus.active,
        confidence=1.0,
        importance=0.5,
        fingerprint=memory_fingerprint(user_id=uid, memory_type=memory_type, subject=subject, predicate=predicate, value=value),
        conflict_key=conflict_key(user_id=uid, memory_type=memory_type, subject=subject, predicate=predicate),
    )
    session.add(mem)


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url.get_secret_value())
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    uid = uuid.UUID("e5b62dc7-4362-485d-b378-f3cd3609fc72")  # apitest@example.com

    async with factory() as session:
        # 清掉该用户已有记忆，避免干扰
        old = (await session.execute(select(Memory).where(Memory.user_id == uid))).scalars().all()
        for m in old:
            await session.delete(m)
        await session.commit()

        # 造 3 组矛盾/冗余记忆：
        # 1. 「喜欢 吃辣」 vs 「喜欢 不吃辣」（矛盾）
        # 2. 「喜欢 咖啡」 vs 「喜欢 咖啡」（冗余，同义）
        # 3. 「住 北京」 vs 「住 上海」（矛盾）
        seeds = [
            ("preference", "self", "喜欢", "吃辣"),
            ("preference", "self", "喜欢", "不吃辣"),
            ("preference", "self", "喜欢", "咖啡"),
            ("preference", "self", "喜欢", "喝咖啡"),
            ("identity", "self", "住在", "北京"),
            ("identity", "self", "住在", "上海"),
        ]
        for t, s, p, v in seeds:
            await _seed(session, uid, t, s, p, v)
        await session.commit()

        active_before = await session.execute(
            select(Memory).where(Memory.user_id == uid, Memory.status == "active")
        )
        print(f"[1] 整合前 active 记忆数 = {len(active_before.scalars().all())}")

        # 触发整合（强制 threshold=1 以覆盖上面的 6 条）
        llm = create_llm_adapter(settings)
        result = await consolidate_memories(session, user_id=uid, llm=llm, threshold=1)
        print(f"[2] 整合结果 superseded = {result.superseded}")

        # 验证整合后状态
        rows = (await session.execute(select(Memory).where(Memory.user_id == uid))).scalars().all()
        active_after = [m for m in rows if m.status == "active"]
        superseded_after = [m for m in rows if m.status == "superseded"]
        print(f"[3] 整合后 active = {len(active_after)}，superseded = {len(superseded_after)}")
        print("    保留的 active 记忆：")
        for m in active_after:
            print(f"      - {m.content}")
        print("    被 supersede 的记忆：")
        for m in superseded_after:
            print(f"      - {m.content} -> {str(m.superseded_by_id)[:8]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
