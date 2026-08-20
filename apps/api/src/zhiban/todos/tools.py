"""Todo and reminder tools exposed to the agent."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from zhiban.core.errors import AppError
from zhiban.todos.service import ReminderService, TodoService
from zhiban.tools.base import ToolContext, ToolResult
from zhiban.tools.spec import ToolSpec


class CreateTodoInput(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    due_at: str | None = Field(default=None, description="截止时间（ISO 8601 带时区）")
    timezone: str = Field(default="Asia/Shanghai")


class TodoIdInput(BaseModel):
    model_config = {"extra": "forbid"}

    todo_id: str = Field(min_length=1, max_length=64)


class TodoCreateTool:
    spec = ToolSpec(
        name="todo.create",
        description="创建一个待办。当用户要求记录待办、任务、要做的事时使用。",
        input_model=CreateTodoInput,
        permission="write",
        timeout_seconds=5.0,
        idempotency="required",
        retry_policy="never",
    )

    def __init__(self, service: TodoService) -> None:
        self._service = service

    async def execute(self, ctx: ToolContext, args: CreateTodoInput) -> ToolResult:
        due_at = None
        if args.due_at:
            try:
                due_at = datetime.fromisoformat(args.due_at)
            except ValueError:
                return ToolResult(
                    ok=False, summary="截止时间格式不合法", error_code="tool_invalid_argument"
                )
        try:
            todo = await self._service.create(
                user_id=ctx.user_id,
                title=args.title,
                detail="",
                due_at=due_at,
                timezone=args.timezone,
                priority=1,
            )
        except AppError as exc:
            return ToolResult(ok=False, summary=exc.message, error_code=exc.code)
        except Exception as exc:  # noqa: BLE001 - service boundary
            return ToolResult(ok=False, summary=str(exc), error_code="execution_error")
        return ToolResult(
            ok=True,
            data={"todo_id": str(todo.id)},
            summary=f"已创建待办：{todo.title}",
        )


class TodoCompleteTool:
    spec = ToolSpec(
        name="todo.complete",
        description="将待办标记为已完成。",
        input_model=TodoIdInput,
        permission="write",
        timeout_seconds=5.0,
        idempotency="required",
        retry_policy="never",
    )

    def __init__(self, service: TodoService) -> None:
        self._service = service

    async def execute(self, ctx: ToolContext, args: TodoIdInput) -> ToolResult:
        try:
            todo_id = uuid.UUID(args.todo_id)
        except ValueError:
            return ToolResult(
                ok=False, summary="待办 ID 不合法", error_code="tool_invalid_argument"
            )
        try:
            todo = await self._service.complete(user_id=ctx.user_id, todo_id=todo_id)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, summary=str(exc), error_code="execution_error")
        return ToolResult(ok=True, summary=f"已完成待办：{todo.title}")


class CreateReminderInput(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    remind_at: str = Field(description="提醒时间（ISO 8601 带时区）")
    timezone: str = Field(default="Asia/Shanghai")
    recurrence: str = Field(
        default="none",
        description="重复规则：none=单次, daily=每天, weekly=每周",
    )
    recurrence_end_at: str | None = Field(
        default=None, description="重复结束时间（ISO 8601 带时区，可选）"
    )


class ReminderCreateTool:
    spec = ToolSpec(
        name="reminder.create",
        description="创建一个单次提醒。当用户要求在某个时间提醒某事时使用。",
        input_model=CreateReminderInput,
        permission="write",
        timeout_seconds=5.0,
        idempotency="required",
        retry_policy="never",
    )

    def __init__(self, service: ReminderService) -> None:
        self._service = service

    async def execute(self, ctx: ToolContext, args: CreateReminderInput) -> ToolResult:
        try:
            remind_at = datetime.fromisoformat(args.remind_at)
        except ValueError:
            return ToolResult(
                ok=False, summary="提醒时间格式不合法", error_code="tool_invalid_argument"
            )
        recurrence_end_at = None
        if args.recurrence_end_at:
            try:
                recurrence_end_at = datetime.fromisoformat(args.recurrence_end_at)
            except ValueError:
                return ToolResult(
                    ok=False,
                    summary="重复结束时间格式不合法",
                    error_code="tool_invalid_argument",
                )
        try:
            reminder = await self._service.create(
                user_id=ctx.user_id,
                title=args.title,
                remind_at=remind_at,
                timezone=args.timezone,
                recurrence=args.recurrence,
                recurrence_end_at=recurrence_end_at,
            )
        except AppError as exc:
            return ToolResult(ok=False, summary=exc.message, error_code=exc.code)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, summary=str(exc), error_code="execution_error")
        recurrence_label = {
            "none": "单次",
            "daily": "每天",
            "weekly": "每周",
        }.get(args.recurrence, "单次")
        return ToolResult(
            ok=True,
            data={"reminder_id": str(reminder.id)},
            summary=f"已创建{recurrence_label}提醒：{reminder.title}（{self._service.format_time(reminder)}）",
        )


class ReminderCancelTool:
    spec = ToolSpec(
        name="reminder.cancel",
        description="取消一个提醒。",
        input_model=TodoIdInput,
        permission="write",
        timeout_seconds=5.0,
        idempotency="required",
        retry_policy="never",
    )

    def __init__(self, service: ReminderService) -> None:
        self._service = service

    async def execute(self, ctx: ToolContext, args: TodoIdInput) -> ToolResult:
        try:
            reminder_id = uuid.UUID(args.todo_id)
        except ValueError:
            return ToolResult(
                ok=False, summary="提醒 ID 不合法", error_code="tool_invalid_argument"
            )
        try:
            reminder = await self._service.cancel(user_id=ctx.user_id, reminder_id=reminder_id)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, summary=str(exc), error_code="execution_error")
        return ToolResult(ok=True, summary=f"已取消提醒：{reminder.title}")
