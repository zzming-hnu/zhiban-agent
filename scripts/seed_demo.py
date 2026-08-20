"""Seed demo accounts and data for the defense/demo.

Idempotent: skips users that already exist.
Creates two demo users (demo-a / demo-b) with preferences, a memory, and a todo.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

from sqlalchemy import select  # noqa: E402
from zhiban.auth.security import hash_password  # noqa: E402
from zhiban.core.config import Settings  # noqa: E402
from zhiban.core.resources import AppResources  # noqa: E402
from zhiban.db.models import Memory, Todo, User  # noqa: E402
from zhiban.db.session import create_session_factory  # noqa: E402
from zhiban.memory.ids import conflict_key, memory_fingerprint  # noqa: E402

DEMO_USERS = [
    {"email": "demo-a@example.com", "password": "demo12345", "display_name": "演示用户A"},
    {"email": "demo-b@example.com", "password": "demo12345", "display_name": "演示用户B"},
]


async def seed() -> None:
    settings = Settings()
    resources = AppResources.from_settings(settings)
    session_factory = create_session_factory(resources.database)

    async with session_factory() as session:
        for spec in DEMO_USERS:
            existing = (
                await session.execute(select(User).where(User.email == spec["email"]))
            ).scalar_one_or_none()
            if existing is not None:
                print(f"[skip] {spec['email']} 已存在")
                continue

            user = User(
                email=spec["email"],
                password_hash=hash_password(spec["password"]),
                display_name=spec["display_name"],
            )
            session.add(user)
            await session.flush()

            # 演示记忆：偏好
            fingerprint = memory_fingerprint(
                user_id=user.id,
                memory_type="preference",
                subject="self",
                predicate="喜欢",
                value="简洁的中文回答",
            )
            ckey = conflict_key(
                user_id=user.id,
                memory_type="preference",
                subject="self",
                predicate="喜欢",
            )
            session.add(
                Memory(
                    user_id=user.id,
                    memory_type="preference",
                    category="communication_preference",
                    subject="self",
                    predicate="喜欢",
                    value="简洁的中文回答",
                    content="self 喜欢 简洁的中文回答",
                    source_kind="explicit",
                    status="active",
                    confidence=1.0,
                    importance=0.8,
                    fingerprint=fingerprint,
                    conflict_key=ckey,
                    source_message_ids=[],
                    evidence_quote="",
                )
            )

            # 演示待办
            session.add(
                Todo(
                    user_id=user.id,
                    title="准备毕业答辩演示稿",
                    detail="",
                    status="pending",
                    priority=1,
                )
            )
            print(f"[created] {spec['email']}")

        await session.commit()

    await resources.close()
    print("seed done")


if __name__ == "__main__":
    asyncio.run(seed())
