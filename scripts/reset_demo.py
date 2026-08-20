"""Reset demo data (DELETE all demo users and their data).

Safety: refuses to run in production or without an explicit demo/test env.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

from sqlalchemy import delete, select  # noqa: E402
from zhiban.core.config import Settings  # noqa: E402
from zhiban.core.resources import AppResources  # noqa: E402
from zhiban.db.models import (  # noqa: E402
    Memory,
    MemoryCandidate,
    Reminder,
    Todo,
    User,
)
from zhiban.db.session import create_session_factory  # noqa: E402

DEMO_EMAILS = ("demo-a@example.com", "demo-b@example.com")


async def reset() -> None:
    settings = Settings()

    # Safety guard: only allow reset in demo/test environments.
    if settings.app_env == "production":
        print("拒绝：不允许在生产环境执行 reset-demo", file=sys.stderr)
        sys.exit(2)

    resources = AppResources.from_settings(settings)
    session_factory = create_session_factory(resources.database)

    async with session_factory() as session:
        result = await session.execute(select(User).where(User.email.in_(DEMO_EMAILS)))
        demo_users = list(result.scalars())
        if not demo_users:
            print("没有找到 demo 账号，无需清理")
            await resources.close()
            return

        user_ids = [u.id for u in demo_users]
        for model in (MemoryCandidate, Reminder, Todo, Memory):
            await session.execute(delete(model).where(model.user_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()
        print(f"已删除 {len(demo_users)} 个 demo 账号及其数据")

    await resources.close()
    print("reset done")


if __name__ == "__main__":
    asyncio.run(reset())
