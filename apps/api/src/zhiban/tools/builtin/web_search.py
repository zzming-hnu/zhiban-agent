"""Web search tool — wraps a SearchAdapter and returns sanitized results."""

from dataclasses import asdict

from pydantic import BaseModel, Field

from zhiban.tools.base import ToolContext, ToolResult
from zhiban.tools.search.base import SearchAdapter
from zhiban.tools.search.sanitize import sanitize_result
from zhiban.tools.spec import ToolSpec


class WebSearchInput(BaseModel):
    model_config = {"extra": "forbid"}

    query: str = Field(description="搜索关键词", min_length=1, max_length=200)
    max_results: int = Field(default=3, ge=1, le=5)


class WebSearchTool:
    spec = ToolSpec(
        name="web_search",
        description="搜索网络获取实时信息。当用户询问最新事件、事实查询或需要联网搜索时使用。",
        input_model=WebSearchInput,
        permission="read",
        timeout_seconds=12.0,
        idempotency="optional",
        retry_policy="safe_once",
    )

    def __init__(self, adapter: SearchAdapter) -> None:
        self._adapter = adapter

    async def execute(self, ctx: ToolContext, args: WebSearchInput) -> ToolResult:
        try:
            results = await self._adapter.search(args.query, args.max_results)
        except Exception:  # noqa: BLE001 - search failure is non-fatal
            return ToolResult(
                ok=False,
                summary="搜索暂时不可用，未完成在线检索",
                error_code="search_unavailable",
                retryable=True,
            )

        sanitized = [sanitize_result(r) for r in results]
        if not sanitized:
            return ToolResult(
                ok=True,
                data=[],
                summary=f"没有找到关于「{args.query}」的相关结果",
                citations=[],
            )
        return ToolResult(
            ok=True,
            data=[asdict(r) for r in sanitized],
            summary=f"找到 {len(sanitized)} 条关于「{args.query}」的搜索结果（演示数据）",
            citations=[r.url for r in sanitized],
        )
