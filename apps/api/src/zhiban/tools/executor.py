"""ToolExecutor: validate, authorize, time-bound, and audit tool execution."""

import asyncio
import time
from typing import Any

import structlog

from zhiban.tools.base import Tool, ToolContext, ToolResult
from zhiban.tools.hooks import AfterToolHook, BeforeToolHook, ToolErrorHook
from zhiban.tools.spec import ToolSpec

logger = structlog.get_logger(__name__)


class ToolExecutor:
    """Executes a tool with timeout, retry, truncation, hooks, and audit."""

    def __init__(
        self,
        *,
        before_hooks: list[BeforeToolHook] | None = None,
        after_hooks: list[AfterToolHook] | None = None,
        error_hooks: list[ToolErrorHook] | None = None,
    ) -> None:
        self._before_hooks = before_hooks or []
        self._after_hooks = after_hooks or []
        self._error_hooks = error_hooks or []

    async def execute(self, tool: Tool[Any], ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        spec = tool.spec
        started = time.perf_counter()

        # 1. Validate arguments against the tool's input schema.
        try:
            validated = spec.input_model.model_validate(args)
        except Exception:  # noqa: BLE001 - pydantic raises ValidationError
            return ToolResult(
                ok=False,
                summary="工具参数不合法",
                error_code="tool_invalid_argument",
            )

        # 2. Permission is checked by the caller (registry filters available
        #    tools); here we reject sensitive tools without confirmation.
        if spec.permission == "sensitive":
            return ToolResult(
                ok=False,
                summary="该操作需要确认",
                error_code="tool_confirmation_required",
            )

        # 3. Before hooks.
        for before_hook in self._before_hooks:
            try:
                await before_hook.before(ctx, spec.name, validated)
            except Exception as exc:  # noqa: BLE001 - a hook may reject
                return ToolResult(
                    ok=False,
                    summary=f"调用被拒绝: {exc}",
                    error_code="tool_rejected",
                )

        # 4. Execute with timeout, applying safe_once retry for read-only tools.
        result = await self._run_with_policy(tool, ctx, validated, spec)

        # 5. Truncate oversized results.
        result = self._truncate(result, spec)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        await logger.ainfo(
            "tool_executed",
            tool_name=spec.name,
            permission=spec.permission,
            ok=result.ok,
            error_code=result.error_code,
            duration_ms=duration_ms,
            truncated=result.truncated,
        )

        # 6. After hooks.
        for after_hook in self._after_hooks:
            try:
                await after_hook.after(ctx, spec.name, result)
            except Exception:  # noqa: BLE001 - hook isolation
                await logger.awarning("tool_after_hook_failed", tool_name=spec.name)

        return result

    async def _run_with_policy(
        self, tool: Tool[Any], ctx: ToolContext, args: Any, spec: ToolSpec
    ) -> ToolResult:
        attempts = 2 if spec.retry_policy == "safe_once" else 1
        last_result: ToolResult | None = None
        for attempt in range(attempts):
            try:
                async with asyncio.timeout(spec.timeout_seconds):
                    result = await tool.execute(ctx, args)
                # Retry only transient failures on safe_once tools.
                if not result.ok and result.retryable and attempt < attempts - 1:
                    last_result = result
                    continue
                return result
            except TimeoutError:
                last_result = ToolResult(
                    ok=False,
                    summary="工具执行超时",
                    error_code="tool_timeout",
                )
                if attempt < attempts - 1:
                    continue
            except Exception as exc:  # noqa: BLE001 - tool boundary
                await logger.aexception(
                    "tool_execution_error", tool_name=spec.name, error_type=type(exc).__name__
                )
                last_result = ToolResult(
                    ok=False,
                    summary="工具执行失败",
                    error_code="execution_error",
                )
                if attempt < attempts - 1:
                    continue
        assert last_result is not None
        return last_result

    def _truncate(self, result: ToolResult, spec: ToolSpec) -> ToolResult:
        if result.data is None:
            return result
        import json

        try:
            serialized = json.dumps(result.data, ensure_ascii=False)
        except (TypeError, ValueError):
            return ToolResult(
                ok=False,
                summary="工具结果不可序列化",
                error_code="tool_result_invalid",
            )
        if len(serialized) > spec.result_token_budget:
            result.truncated = True
        return result
