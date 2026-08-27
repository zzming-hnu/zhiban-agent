"""线上验证记忆演化链：写入→冲突更新→验证 superseded 链路。

用法（在服务器上，通过容器执行）：
  docker exec zhiban-prod-app-1 python /tmp/verify_memory_evolution.py
"""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from zhiban.core.config import get_settings
from zhiban.db.models import Memory
from zhiban.memory.schemas import MemoryCandidatePayload
from zhiban.memory.service import MemoryService
from zhiban.memory.types import Decision


def _candidate(*, value: str, mid: uuid.UUID, quote: str) -> MemoryCandidatePayload:
    return MemoryCandidatePayload(
        memory_type="preference",
        subject="self",
        predicate="喜欢",
        value=value,
        source_message_ids=[mid],
        evidence_quote=quote,
        confidence=0.9,
        importance=0.7,
    )


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url.get_secret_value())
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # 使用线上已有的测试用户（apitest@example.com），避免外键约束失败。
        uid = uuid.UUID("e5b62dc7-4362-485d-b378-f3cd3609fc72")
        svc = MemoryService(session)

        mid1 = uuid.uuid4()
        texts1 = {mid1: "我现在喜欢吃辣的"}
        d1, _ = await svc.process_candidate(
            user_id=uid,
            candidate=_candidate(value="吃辣", mid=mid1, quote="我现在喜欢吃辣的"),
            source_kind="explicit",
            extractor_version="v1",
            available_message_ids={mid1},
            available_message_texts=texts1,
        )
        print(f"[1] 第一次写入 decision={d1.value}")

        mid2 = uuid.uuid4()
        texts2 = {mid2: "我现在不喜欢吃辣了"}
        d2, _ = await svc.process_candidate(
            user_id=uid,
            candidate=_candidate(value="不吃辣", mid=mid2, quote="我现在不喜欢吃辣了"),
            source_kind="explicit",
            extractor_version="v1",
            available_message_ids={mid2},
            available_message_texts=texts2,
        )
        print(f"[2] 第二次写入（同 slot 不同值）decision={d2.value}")

        # 验证 active 列表
        active = await svc.list_memories(user_id=uid)
        print(f"[3] active 记忆数={len(active)}")
        for m in active:
            print(f"    active: value={m.value!r} status={m.status}")

        # 验证全部记录（含 superseded）
        all_rows = (await session.execute(select(Memory).where(Memory.user_id == uid))).scalars().all()
        for m in all_rows:
            sup = f"-> {str(m.superseded_by_id)[:8]}" if m.superseded_by_id else "无"
            print(f"    记录: value={m.value!r} status={m.status} superseded_by={sup}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
