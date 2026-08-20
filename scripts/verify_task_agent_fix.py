"""Verify TaskAgent fix: should ask for missing time, not fake completion.

Scenarios:
    1. 「帮我记一个每天早上早起的待办」 → 应回问时间（不应直接建无时间待办）
    2. 「每天早上7点提醒我早起」 → 应建明早7点 reminder（或说明当前不支持周期）
"""

import asyncio
import sys
from pathlib import Path

import httpx2 as httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

API = "http://localhost:8000/api/v1"

SCENARIOS = [
    ("没具体时间-待办", "帮我记一个每天早上早起的待办"),
    ("重复意图-提醒", "每天早上7点提醒我早起"),
]


async def main() -> None:
    if len(sys.argv) < 3:
        print("用法: verify_task_agent_fix.py <email> <password>")
        sys.exit(2)

    email, password = sys.argv[1], sys.argv[2]

    async with httpx.AsyncClient(base_url=API, timeout=60.0) as client:
        login = await client.post("/auth/login", json={"email": email, "password": password})
        if login.status_code != 200:
            print(f"登录失败: {login.status_code} {login.text[:200]}")
            sys.exit(1)
        csrf = client.cookies.get("zhiban_csrf")
        headers = {"X-CSRF-Token": csrf or ""}

        for label, content in SCENARIOS:
            conv = await client.post(
                "/conversations", json={"title": f"TaskAgentFix-{label}"}, headers=headers
            )
            conv_id = conv.json()["id"]
            msg = await client.post(
                f"/conversations/{conv_id}/messages",
                json={"content": content, "model": "deepseek-v4-flash"},
                headers=headers,
            )
            run_id = msg.json()["run_id"]

            full_text = ""
            async with client.stream("GET", f"/runs/{run_id}/stream") as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        import json as _json
                        try:
                            d = _json.loads(line[7:])
                            if d.get("data", {}).get("delta"):
                                full_text += d["data"]["delta"]
                        except: pass

            print(f"\n=== [{label}] 「{content}」 ===")
            print(f"回答:\n{full_text}\n")
            print("-" * 60)

        await client.post("/auth/logout", headers=headers)


if __name__ == "__main__":
    asyncio.run(main())