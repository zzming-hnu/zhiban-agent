"""Unit and integration tests for todos, reminders, and timezone handling."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.auth.security import hash_password
from zhiban.core.errors import AppError
from zhiban.db.models import User
from zhiban.todos.service import ReminderService, TodoService
from zhiban.todos.timezone import format_absolute, to_utc, validate_timezone


def _future(hours: int = 1) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


# --- timezone unit tests ---


def test_to_utc_converts_local_to_utc() -> None:
    # Asia/Shanghai is UTC+8.
    local = datetime(2026, 8, 20, 9, 0)  # naive
    utc_dt = to_utc(local, "Asia/Shanghai")
    assert utc_dt.hour == 1  # 09:00 +08:00 == 01:00 UTC
    assert utc_dt.tzinfo == UTC


def test_validate_timezone() -> None:
    assert validate_timezone("Asia/Shanghai")
    assert validate_timezone("America/New_York")
    assert not validate_timezone("Not/AZone")


def test_format_absolute_includes_timezone() -> None:
    utc_dt = datetime(2026, 8, 20, 1, 0, tzinfo=UTC)
    text = format_absolute(utc_dt, "Asia/Shanghai")
    assert "09:00" in text
    assert "Asia/Shanghai" in text


# --- service integration tests ---


async def _make_user(session: AsyncSession) -> User:
    user = User(
        email=f"t-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        display_name="x",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.integration
async def test_todo_create_and_complete(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session)
    await session.commit()

    service = TodoService(session)
    todo = await service.create(
        user_id=user.id,
        title="完成演示稿",
        detail="",
        due_at=None,
        timezone="Asia/Shanghai",
        priority=1,
    )
    assert todo.status == "pending"

    completed = await service.complete(user_id=user.id, todo_id=todo.id)
    assert completed.status == "done"
    assert completed.completed_at is not None


@pytest.mark.integration
async def test_todo_progress_counts(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session)
    await session.commit()

    service = TodoService(session)
    t1 = await service.create(
        user_id=user.id, title="a", detail="", due_at=None, timezone="Asia/Shanghai", priority=1
    )
    await service.create(
        user_id=user.id, title="b", detail="", due_at=None, timezone="Asia/Shanghai", priority=1
    )
    await service.complete(user_id=user.id, todo_id=t1.id)

    progress = await service.progress(user_id=user.id)
    assert progress["total"] == 2
    assert progress["done"] == 1
    assert progress["pending"] == 1


@pytest.mark.integration
async def test_reminder_create_and_cancel(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session)
    await session.commit()

    service = ReminderService(session)
    reminder = await service.create(
        user_id=user.id,
        title="交报告",
        remind_at=_future(hours=2),
        timezone="Asia/Shanghai",
    )
    assert reminder.status == "scheduled"

    cancelled = await service.cancel(user_id=user.id, reminder_id=reminder.id)
    assert cancelled.status == "cancelled"


@pytest.mark.integration
async def test_reminder_rejects_past_time(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session)
    await session.commit()

    service = ReminderService(session)
    with pytest.raises(AppError) as exc_info:
        await service.create(
            user_id=user.id,
            title="过去",
            remind_at=datetime.now(UTC) - timedelta(hours=1),
            timezone="Asia/Shanghai",
        )
    assert exc_info.value.code == "past_time"


@pytest.mark.integration
async def test_reminder_dedupe(session: AsyncSession, clean_database: None) -> None:
    user = await _make_user(session)
    await session.commit()

    service = ReminderService(session)
    at = _future(hours=3)
    r1 = await service.create(user_id=user.id, title="提醒", remind_at=at, timezone="Asia/Shanghai")
    # Same user+title+time -> same dedupe key -> idempotent (returns existing).
    r2 = await service.create(user_id=user.id, title="提醒", remind_at=at, timezone="Asia/Shanghai")
    assert r1.id == r2.id
    assert r1.status == "scheduled"
