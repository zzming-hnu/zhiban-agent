"""Current time tool — returns the current time in a given timezone."""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from zhiban.tools.base import ToolContext, ToolResult
from zhiban.tools.spec import ToolSpec


class CurrentTimeInput(BaseModel):
    model_config = {"extra": "forbid"}

    timezone: str = Field(default="Asia/Shanghai", description="IANA timezone name")


class CurrentTimeTool:
    spec = ToolSpec(
        name="current_time",
        description="获取当前时间，可以指定时区",
        input_model=CurrentTimeInput,
        permission="read",
        timeout_seconds=5.0,
        idempotency="optional",
        retry_policy="never",
    )

    async def execute(self, ctx: ToolContext, args: CurrentTimeInput) -> ToolResult:
        try:
            tz = ZoneInfo(args.timezone)
        except Exception:
            tz = ZoneInfo("Asia/Shanghai")
        now = datetime.now(tz)
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return ToolResult(
            ok=True,
            data={
                "time": now.isoformat(),
                "timezone": str(tz),
                "date": now.strftime("%Y-%m-%d"),
                "weekday": weekdays[now.weekday()],
            },
            summary=f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M')} ({args.timezone})",
        )
