"""Repository for todos and reminders with enforced user scoping."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.db.models import Reminder, Todo


class TodoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        detail: str,
        due_at: datetime | None,
        priority: int,
        source_message_id: uuid.UUID | None = None,
    ) -> Todo:
        todo = Todo(
            user_id=user_id,
            title=title,
            detail=detail,
            due_at=due_at,
            priority=priority,
            source_message_id=source_message_id,
        )
        self._session.add(todo)
        await self._session.flush()
        return todo

    async def get(self, *, user_id: uuid.UUID, todo_id: uuid.UUID) -> Todo | None:
        result = await self._session.execute(
            select(Todo).where(
                Todo.id == todo_id,
                Todo.user_id == user_id,
                Todo.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_active(self, *, user_id: uuid.UUID, limit: int = 100) -> list[Todo]:
        result = await self._session.execute(
            select(Todo)
            .where(Todo.user_id == user_id, Todo.deleted_at.is_(None))
            .order_by(Todo.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def mark_done(self, todo: Todo) -> None:
        todo.status = "done"
        todo.completed_at = datetime.now(UTC)

    async def mark_cancelled(self, todo: Todo) -> None:
        todo.status = "cancelled"


class ReminderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        remind_at: datetime,
        timezone: str,
        dedupe_key: str,
        todo_id: uuid.UUID | None = None,
        recurrence: str = "none",
        recurrence_end_at: datetime | None = None,
    ) -> Reminder:
        reminder = Reminder(
            user_id=user_id,
            todo_id=todo_id,
            title=title,
            remind_at=remind_at,
            timezone=timezone,
            dedupe_key=dedupe_key,
            recurrence=recurrence,
            recurrence_end_at=recurrence_end_at,
        )
        self._session.add(reminder)
        await self._session.flush()
        return reminder

    async def get(self, *, user_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder | None:
        result = await self._session.execute(
            select(Reminder).where(
                Reminder.id == reminder_id,
                Reminder.user_id == user_id,
                Reminder.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_dedupe_key(self, *, user_id: uuid.UUID, dedupe_key: str) -> Reminder | None:
        result = await self._session.execute(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.dedupe_key == dedupe_key,
                Reminder.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_active(self, *, user_id: uuid.UUID, limit: int = 100) -> list[Reminder]:
        result = await self._session.execute(
            select(Reminder)
            .where(Reminder.user_id == user_id, Reminder.deleted_at.is_(None))
            .order_by(Reminder.remind_at.asc())
            .limit(limit)
        )
        return list(result.scalars())

    async def list_due(self, *, now: datetime, limit: int = 20) -> list[Reminder]:
        result = await self._session.execute(
            select(Reminder)
            .where(
                Reminder.status == "scheduled",
                Reminder.remind_at <= now,
                Reminder.deleted_at.is_(None),
            )
            .order_by(Reminder.remind_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars())

    async def mark_cancelled(self, reminder: Reminder) -> None:
        reminder.status = "cancelled"
        reminder.cancelled_at = datetime.now(UTC)

    async def mark_delivered(self, reminder: Reminder) -> None:
        reminder.status = "delivered"
        reminder.delivery_status = "delivered"
        reminder.delivered_at = datetime.now(UTC)

    async def list_delivered_unnotified(
        self, *, user_id: uuid.UUID, limit: int = 20
    ) -> list[Reminder]:
        result = await self._session.execute(
            select(Reminder)
            .where(
                Reminder.user_id == user_id,
                Reminder.status == "delivered",
                Reminder.notified_at.is_(None),
                Reminder.deleted_at.is_(None),
            )
            .order_by(Reminder.delivered_at.asc())
            .limit(limit)
        )
        return list(result.scalars())

    async def mark_notified(self, reminder: Reminder) -> None:
        reminder.notified_at = datetime.now(UTC)
