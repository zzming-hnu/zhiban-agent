"""Todo and reminder domain logic with timezone and idempotency handling."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.core.errors import AppError
from zhiban.db.models import Reminder, Todo
from zhiban.todos.repository import ReminderRepository, TodoRepository
from zhiban.todos.timezone import format_absolute, to_utc, validate_timezone

RECURRENCE_NONE = "none"
RECURRENCE_DAILY = "daily"
RECURRENCE_WEEKLY = "weekly"
RECURRENCES = (RECURRENCE_NONE, RECURRENCE_DAILY, RECURRENCE_WEEKLY)


def next_occurrence(remind_at: datetime, recurrence: str) -> datetime:
    """Return the next occurrence for a recurrence rule (relative to remind_at)."""
    if recurrence == RECURRENCE_DAILY:
        return remind_at + timedelta(days=1)
    if recurrence == RECURRENCE_WEEKLY:
        return remind_at + timedelta(weeks=1)
    return remind_at


class TodoService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.repo = TodoRepository(session)

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        detail: str,
        due_at: datetime | None,
        timezone: str,
        priority: int,
    ) -> Todo:
        due_utc = None
        if due_at is not None:
            if not validate_timezone(timezone):
                raise AppError(code="invalid_timezone", message="时区不合法", status_code=422)
            due_utc = to_utc(due_at, timezone)
        todo = await self.repo.create(
            user_id=user_id,
            title=title,
            detail=detail,
            due_at=due_utc,
            priority=priority,
        )
        await self._session.commit()
        return todo

    async def list_todos(self, *, user_id: uuid.UUID, limit: int = 100) -> list[Todo]:
        return await self.repo.list_active(user_id=user_id, limit=limit)

    async def get_or_404(self, *, user_id: uuid.UUID, todo_id: uuid.UUID) -> Todo:
        todo = await self.repo.get(user_id=user_id, todo_id=todo_id)
        if todo is None:
            raise AppError(code="not_found", message="待办不存在", status_code=404)
        return todo

    async def complete(self, *, user_id: uuid.UUID, todo_id: uuid.UUID) -> Todo:
        todo = await self.get_or_404(user_id=user_id, todo_id=todo_id)
        await self.repo.mark_done(todo)
        todo.version += 1
        await self._session.commit()
        return todo

    async def cancel(self, *, user_id: uuid.UUID, todo_id: uuid.UUID) -> Todo:
        todo = await self.get_or_404(user_id=user_id, todo_id=todo_id)
        await self.repo.mark_cancelled(todo)
        todo.version += 1
        await self._session.commit()
        return todo

    async def progress(self, *, user_id: uuid.UUID) -> dict[str, int]:
        todos = await self.repo.list_active(user_id=user_id, limit=1000)
        now = datetime.now(UTC)
        done = sum(1 for t in todos if t.status == "done")
        pending = sum(1 for t in todos if t.status == "pending")
        overdue = sum(
            1 for t in todos if t.status == "pending" and t.due_at is not None and t.due_at < now
        )
        return {"total": len(todos), "done": done, "pending": pending, "overdue": overdue}


class ReminderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.repo = ReminderRepository(session)

    def _dedupe_key(self, user_id: uuid.UUID, title: str, remind_at: datetime) -> str:
        material = "\x1f".join([str(user_id), title, remind_at.isoformat()])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        remind_at: datetime,
        timezone: str,
        todo_id: uuid.UUID | None = None,
        recurrence: str = RECURRENCE_NONE,
        recurrence_end_at: datetime | None = None,
    ) -> Reminder:
        if not validate_timezone(timezone):
            raise AppError(code="invalid_timezone", message="时区不合法", status_code=422)
        if recurrence not in RECURRENCES:
            raise AppError(code="invalid_recurrence", message="重复规则不合法", status_code=422)

        remind_utc = to_utc(remind_at, timezone)
        if remind_utc <= datetime.now(UTC):
            raise AppError(
                code="past_time",
                message="提醒时间必须是将来的时间",
                status_code=422,
            )

        dedupe_key = self._dedupe_key(user_id, title, remind_utc)
        existing = await self.repo.get_by_dedupe_key(user_id=user_id, dedupe_key=dedupe_key)
        if existing is not None:
            # Idempotent: return the existing reminder instead of duplicating.
            return existing

        reminder = await self.repo.create(
            user_id=user_id,
            title=title,
            remind_at=remind_utc,
            timezone=timezone,
            dedupe_key=dedupe_key,
            todo_id=todo_id,
            recurrence=recurrence,
            recurrence_end_at=recurrence_end_at,
        )
        await self._session.commit()
        return reminder

    async def list_reminders(self, *, user_id: uuid.UUID, limit: int = 100) -> list[Reminder]:
        return await self.repo.list_active(user_id=user_id, limit=limit)

    async def get_or_404(self, *, user_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder:
        reminder = await self.repo.get(user_id=user_id, reminder_id=reminder_id)
        if reminder is None:
            raise AppError(code="not_found", message="提醒不存在", status_code=404)
        return reminder

    async def cancel(self, *, user_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder:
        reminder = await self.get_or_404(user_id=user_id, reminder_id=reminder_id)
        await self.repo.mark_cancelled(reminder)
        reminder.version += 1
        await self._session.commit()
        return reminder

    async def deliver_now(self, *, user_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder:
        """Deliver a reminder immediately (demo/test only; idempotent)."""
        reminder = await self.get_or_404(user_id=user_id, reminder_id=reminder_id)
        if reminder.status == "scheduled":
            await self.repo.mark_delivered(reminder)
            reminder.version += 1
            await self._session.commit()
        return reminder

    async def list_pending_notification(
        self, *, user_id: uuid.UUID, limit: int = 20
    ) -> list[Reminder]:
        """Return delivered reminders the user has not been shown yet."""
        return await self.repo.list_delivered_unnotified(user_id=user_id, limit=limit)

    async def mark_notified(self, *, user_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder:
        reminder = await self.get_or_404(user_id=user_id, reminder_id=reminder_id)
        await self.repo.mark_notified(reminder)
        await self._session.commit()
        return reminder

    def format_time(self, reminder: Reminder) -> str:
        return format_absolute(reminder.remind_at, reminder.timezone)
