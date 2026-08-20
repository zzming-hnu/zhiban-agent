"""Tests for reminder scheduling and idempotent delivery."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.auth.security import hash_password
from zhiban.db.models import Reminder, User
from zhiban.todos.service import ReminderService
from zhiban.workers.reminder_jobs import scan_and_deliver


async def _make_user(session: AsyncSession) -> User:
    user = User(
        email=f"r-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        display_name="x",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_due_reminder(session: AsyncSession, user: User) -> Reminder:
    # Create a reminder that is already due (past remind_at).
    service = ReminderService(session)
    # Directly create a due reminder by manipulating time (bypass past-time check).
    reminder = await service.create(
        user_id=user.id,
        title="到期提醒",
        remind_at=datetime.now(UTC) + timedelta(seconds=1),
        timezone="Asia/Shanghai",
    )
    await session.commit()
    # Force it to be due.
    await session.execute(
        Reminder.__table__.update()
        .where(Reminder.id == reminder.id)
        .values(remind_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await session.commit()
    return reminder


@pytest.mark.integration
async def test_scan_delivers_due_reminder(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session)
    await session.commit()
    reminder = await _create_due_reminder(session, user)

    delivered = await scan_and_deliver(session)
    assert delivered == 1

    # Reminder is now delivered.
    refreshed = (
        await session.execute(select(Reminder).where(Reminder.id == reminder.id))
    ).scalar_one()
    assert refreshed.status == "delivered"
    assert refreshed.delivered_at is not None


@pytest.mark.integration
async def test_scan_is_idempotent(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session)
    await session.commit()
    reminder = await _create_due_reminder(session, user)

    # First scan delivers it.
    assert await scan_and_deliver(session) == 1
    # Second scan finds nothing new (already delivered).
    assert await scan_and_deliver(session) == 0

    refreshed = (
        await session.execute(select(Reminder).where(Reminder.id == reminder.id))
    ).scalar_one()
    assert refreshed.status == "delivered"


@pytest.mark.integration
async def test_scan_skips_future_and_cancelled(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session)
    await session.commit()

    service = ReminderService(session)
    # Future reminder (not due).
    await service.create(
        user_id=user.id,
        title="未来提醒",
        remind_at=datetime.now(UTC) + timedelta(hours=2),
        timezone="Asia/Shanghai",
    )
    # Cancelled reminder.
    cancelled = await service.create(
        user_id=user.id,
        title="已取消",
        remind_at=datetime.now(UTC) + timedelta(seconds=1),
        timezone="Asia/Shanghai",
    )
    await service.cancel(user_id=user.id, reminder_id=cancelled.id)

    # Only due reminders delivered (none here).
    assert await scan_and_deliver(session) == 0


def test_next_occurrence_daily_weekly_none() -> None:
    from zhiban.todos.service import next_occurrence

    base = datetime(2026, 8, 20, 7, 0, tzinfo=UTC)
    assert next_occurrence(base, "daily") == base + timedelta(days=1)
    assert next_occurrence(base, "weekly") == base + timedelta(weeks=1)
    assert next_occurrence(base, "none") == base


@pytest.mark.integration
async def test_recurring_reminder_schedules_next(
    session: AsyncSession, clean_database: None
) -> None:
    user = await _make_user(session)
    await session.commit()

    service = ReminderService(session)
    reminder = await service.create(
        user_id=user.id,
        title="每天喝水",
        remind_at=datetime.now(UTC) + timedelta(seconds=1),
        timezone="Asia/Shanghai",
        recurrence="daily",
    )
    await session.commit()

    # Force it due.
    await session.execute(
        Reminder.__table__.update()
        .where(Reminder.id == reminder.id)
        .values(remind_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await session.commit()

    delivered = await scan_and_deliver(session)
    assert delivered == 1

    # Original delivered.
    refreshed = (
        await session.execute(select(Reminder).where(Reminder.id == reminder.id))
    ).scalar_one()
    assert refreshed.status == "delivered"

    # A new scheduled occurrence was created (daily +1 day).
    next_one = (
        await session.execute(
            select(Reminder).where(
                Reminder.user_id == user.id,
                Reminder.status == "scheduled",
                Reminder.recurrence == "daily",
            )
        )
    ).scalar_one()
    assert next_one.id != reminder.id
    assert next_one.remind_at > refreshed.remind_at
