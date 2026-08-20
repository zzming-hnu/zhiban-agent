"""Verify sub-agent routing end-to-end.

Sends one message per scenario and prints the SSE event types, so you can see
whether the request was delegated to a sub-agent (`run.started` carries
`delegated: true`) or handled by the main agent's own ReAct loop.

Usage:
    PYTHONPATH=apps/api/src ./.venv/bin/python3 scripts/verify_subagents.py <email> <password>

Scenarios:
    1. 记忆（记住…）  → 期望委派 MemoryAgent
    2. 待办（帮我记个待办…） → 期望委派 TaskAgent
    3. 搜索（搜一下…） → 期望委派 SearchAgent
    4. 闲聊（你好）   → 期望不委派（主 Agent 直接回答）
"""

import asyncio
import sys
from pathlib import Path

import httpx2 as httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

API = "http://localhost:8000/api/v1"

SCENARIOS = [
    ("记忆", "记住：我的名字叫小明，喜欢喝美式咖啡"),
    ("待办", "帮我创建一个待办：明天下午3点交周报"),
    ("搜索", "搜索一下今天有什么科技新闻"),
    ("闲聊", "你好，今天过得怎么样"),
]


async def main() -> None:
    if len(sys.argv) < 3:
        print("用法: verify_subagents.py <email> <password>")
        sys.exit(2)

    email, password = sys.argv[1], sys.argv[2]

    async with httpx.AsyncClient(base_url=API, timeout=60.0) as client:
        # Login
        login = await client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        if login.status_code != 200:
            print(f"登录失败: {login.status_code} {login.text[:200]}")
            sys.exit(1)
        csrf = client.cookies.get("zhiban_csrf")
        headers = {"X-CSRF-Token": csrf or ""}

        for label, content in SCENARIOS:
            conv = await client.post(
                "/conversations", json={"title": f"验证-{label}"}, headers=headers
            )
            conv_id = conv.json()["id"]

            msg = await client.post(
                f"/conversations/{conv_id}/messages",
                json={"content": content, "model": "deepseek-v4-flash"},
                headers=headers,
            )
            run_id = msg.json()["run_id"]

            # Consume SSE, tally event types.
            delegated = False
            events: dict[str, int] = {}
            async with client.stream("GET", f"/runs/{run_id}/stream") as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("event: "):
                        events[line[7:]] = events.get(line[7:], 0) + 1
                    elif line.startswith("data: "):
                        if '"delegated": true' in line:
                            delegated = True

            print(f"\n=== [{label}] 「{content}」 ===")
            print(f"  委派子代理: {'是' if delegated else '否（主 Agent 直接处理）'}")
            for etype, count in sorted(events.items()):
                print(f"    {etype}: {count}")

        await client.post("/auth/logout", headers=headers)


if __name__ == "__main__":
    asyncio.run(main())
