"""Todo and reminder REST API."""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.auth.dependencies import PrincipalDep
from zhiban.db.models import Reminder, Todo
from zhiban.db.session import create_session_factory
from zhiban.todos.schemas import (
    CreateReminderRequest,
    CreateTodoRequest,
    ReminderView,
    TodoView,
)
from zhiban.todos.service import ReminderService, TodoService

router = APIRouter(tags=["todos"])


async def _get_session(request: Request) -> AsyncIterator[AsyncSession]:
    resources = request.app.state.resources
    factory = create_session_factory(resources.database)
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(_get_session)]


def _todo_view(todo: Todo) -> TodoView:
    return TodoView(
        id=str(todo.id),
        title=todo.title,
        detail=todo.detail,
        status=todo.status,
        due_at=todo.due_at,
        priority=todo.priority,
        created_at=todo.created_at,
        updated_at=todo.updated_at,
        completed_at=todo.completed_at,
    )


def _reminder_view(reminder: Reminder) -> ReminderView:
    return ReminderView(
        id=str(reminder.id),
        title=reminder.title,
        remind_at=reminder.remind_at,
        timezone=reminder.timezone,
        recurrence=reminder.recurrence,
        recurrence_end_at=reminder.recurrence_end_at,
        status=reminder.status,
        delivery_status=reminder.delivery_status,
        delivered_at=reminder.delivered_at,
        created_at=reminder.created_at,
    )


# --- Todos ---


@router.post("/todos", response_model=TodoView, status_code=201)
async def create_todo(
    body: CreateTodoRequest,
    principal: PrincipalDep,
    session: DbSession,
) -> TodoView:
    service = TodoService(session)
    todo = await service.create(
        user_id=principal.user_id,
        title=body.title,
        detail=body.detail,
        due_at=body.due_at,
        timezone=body.timezone,
        priority=body.priority,
    )
    return _todo_view(todo)


@router.get("/todos", response_model=list[TodoView])
async def list_todos(principal: PrincipalDep, session: DbSession) -> list[TodoView]:
    service = TodoService(session)
    todos = await service.list_todos(user_id=principal.user_id)
    return [_todo_view(t) for t in todos]


@router.post("/todos/{todo_id}/complete", response_model=TodoView)
async def complete_todo(
    todo_id: uuid.UUID, principal: PrincipalDep, session: DbSession
) -> TodoView:
    service = TodoService(session)
    todo = await service.complete(user_id=principal.user_id, todo_id=todo_id)
    return _todo_view(todo)


@router.delete("/todos/{todo_id}", status_code=204)
async def cancel_todo(todo_id: uuid.UUID, principal: PrincipalDep, session: DbSession) -> Response:
    service = TodoService(session)
    await service.cancel(user_id=principal.user_id, todo_id=todo_id)
    return Response(status_code=204)


@router.get("/todos/progress")
async def todo_progress(principal: PrincipalDep, session: DbSession) -> dict[str, int]:
    service = TodoService(session)
    return await service.progress(user_id=principal.user_id)


# --- Reminders ---


@router.post("/reminders", response_model=ReminderView, status_code=201)
async def create_reminder(
    body: CreateReminderRequest,
    principal: PrincipalDep,
    session: DbSession,
) -> ReminderView:
    service = ReminderService(session)
    reminder = await service.create(
        user_id=principal.user_id,
        title=body.title,
        remind_at=body.remind_at,
        timezone=body.timezone,
        todo_id=uuid.UUID(body.todo_id) if body.todo_id else None,
        recurrence=body.recurrence,
        recurrence_end_at=body.recurrence_end_at,
    )
    return _reminder_view(reminder)


@router.get("/reminders", response_model=list[ReminderView])
async def list_reminders(principal: PrincipalDep, session: DbSession) -> list[ReminderView]:
    service = ReminderService(session)
    reminders = await service.list_reminders(user_id=principal.user_id)
    return [_reminder_view(r) for r in reminders]


@router.delete("/reminders/{reminder_id}", status_code=204)
async def cancel_reminder(
    reminder_id: uuid.UUID, principal: PrincipalDep, session: DbSession
) -> Response:
    service = ReminderService(session)
    await service.cancel(user_id=principal.user_id, reminder_id=reminder_id)
    return Response(status_code=204)


@router.post("/reminders/{reminder_id}/deliver-now", response_model=ReminderView)
async def deliver_reminder_now(
    reminder_id: uuid.UUID, principal: PrincipalDep, session: DbSession
) -> ReminderView:
    """Immediately deliver a reminder (demo/test convenience; idempotent)."""
    service = ReminderService(session)
    reminder = await service.deliver_now(user_id=principal.user_id, reminder_id=reminder_id)
    return _reminder_view(reminder)


@router.get("/reminders/pending-notifications", response_model=list[ReminderView])
async def pending_notifications(principal: PrincipalDep, session: DbSession) -> list[ReminderView]:
    """Return delivered reminders the user has not been shown yet (for polling)."""
    service = ReminderService(session)
    reminders = await service.list_pending_notification(user_id=principal.user_id)
    return [_reminder_view(r) for r in reminders]


@router.post("/reminders/{reminder_id}/notified", response_model=ReminderView)
async def mark_notified(
    reminder_id: uuid.UUID, principal: PrincipalDep, session: DbSession
) -> ReminderView:
    """Mark a reminder as shown to the user (so it is not re-toasted)."""
    service = ReminderService(session)
    reminder = await service.mark_notified(user_id=principal.user_id, reminder_id=reminder_id)
    return _reminder_view(reminder)
