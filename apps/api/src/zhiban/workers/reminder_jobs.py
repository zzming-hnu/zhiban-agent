"""Worker handlers for reminder scheduling and idempotent delivery."""

import hashlib
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.core.config import Settings, get_settings
from zhiban.db.models import Job, Reminder, User
from zhiban.notifications.email import EmailSender
from zhiban.todos.repository import ReminderRepository
from zhiban.todos.service import next_occurrence

logger = structlog.get_logger(__name__)


def _recurring_dedupe_key(reminder: Reminder, next_at: datetime) -> str:
    """Compute a fresh dedupe key for the next occurrence (same scheme as service)."""
    material = "\x1f".join([str(reminder.user_id), reminder.title, next_at.isoformat()])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def _schedule_next_occurrence(repo: ReminderRepository, reminder: Reminder) -> None:
    """Create the next occurrence of a recurring reminder (if any)."""
    if reminder.recurrence == "none":
        return

    next_at = next_occurrence(reminder.remind_at, reminder.recurrence)
    if reminder.recurrence_end_at is not None and next_at > reminder.recurrence_end_at:
        return  # Reached the end of the recurrence window.

    # New occurrence inherits title/timezone/recurrence; fresh idempotency key
    # so the previous delivery does not dedupe it away.
    await repo.create(
        user_id=reminder.user_id,
        todo_id=reminder.todo_id,
        title=reminder.title,
        remind_at=next_at,
        timezone=reminder.timezone,
        dedupe_key=_recurring_dedupe_key(reminder, next_at),
        recurrence=reminder.recurrence,
        recurrence_end_at=reminder.recurrence_end_at,
    )
    await logger.ainfo(
        "reminder_next_scheduled",
        reminder_id=str(reminder.id),
        next_at=next_at.isoformat(),
    )


async def scan_and_deliver(session: AsyncSession) -> int:
    """Scan due reminders and mark them delivered (idempotent by status).

    Returns the number of reminders delivered.
    """
    repo = ReminderRepository(session)
    due = await repo.list_due(now=datetime.now(UTC), limit=50)

    settings: Settings = get_settings()
    sender = EmailSender(settings)

    delivered_count = 0
    for reminder in due:
        await repo.mark_delivered(reminder)

        # Schedule the next occurrence before email so recurring reminders
        # never miss a beat (email is best-effort).
        await _schedule_next_occurrence(repo, reminder)

        # Best-effort email delivery to the reminder owner.
        if sender.enabled:
            try:
                user = (
                    await session.execute(select(User).where(User.id == reminder.user_id))
                ).scalar_one_or_none()
                if user is not None:
                    await sender.send_reminder(
                        to=user.email,
                        title=reminder.title,
                        remind_at=reminder.remind_at.isoformat(),
                    )
            except Exception:  # noqa: BLE001 - email is best-effort
                await logger.aexception("reminder_email_send_error")

        delivered_count += 1

    if delivered_count:
        await session.commit()
    await logger.ainfo(
        "reminder_scan_done",
        delivered=delivered_count,
        scanned=len(due),
    )
    return delivered_count


async def handle_reminder_scan(session: AsyncSession, job: Job) -> None:
    """Job handler: scan due reminders (used by the dispatcher)."""
    await scan_and_deliver(session)


async def handle_reminder_deliver(session: AsyncSession, job: Job) -> None:
    """Deliver a single reminder (called via outbox/job, idempotent by status)."""
    payload = job.payload
    reminder_id = payload.get("reminder_id")
    if reminder_id is None:
        raise ValueError("reminder.deliver job missing reminder_id")

    result = await session.execute(
        select(Reminder).where(Reminder.id == reminder_id, Reminder.status == "scheduled")
    )
    reminder = result.scalar_one_or_none()
    if reminder is None:
        # Already delivered/cancelled -> idempotent no-op.
        return

    repo = ReminderRepository(session)
    await repo.mark_delivered(reminder)
    await session.commit()
