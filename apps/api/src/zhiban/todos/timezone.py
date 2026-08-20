"""Timezone handling for todos/reminders: UTC storage, IANA display."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def to_utc(local_dt: datetime, timezone: str) -> datetime:
    """Convert a naive local datetime to UTC using the given IANA timezone.

    Raises ValueError if the timezone is invalid.
    """
    tz = ZoneInfo(timezone)
    if local_dt.tzinfo is not None:
        return local_dt.astimezone(UTC)
    return local_dt.replace(tzinfo=tz).astimezone(UTC)


def to_local(utc_dt: datetime, timezone: str) -> datetime:
    """Convert a UTC datetime to the given IANA timezone."""
    tz = ZoneInfo(timezone)
    return utc_dt.astimezone(tz)


def format_absolute(utc_dt: datetime, timezone: str) -> str:
    """Format an absolute time for display: '2026-08-19 09:00 (Asia/Shanghai)'."""
    local = to_local(utc_dt, timezone)
    return f"{local.strftime('%Y-%m-%d %H:%M')} ({timezone})"


def validate_timezone(timezone: str) -> bool:
    """Return True if the timezone is a valid IANA name."""
    try:
        ZoneInfo(timezone)
        return True
    except Exception:  # noqa: BLE001 - ZoneInfo raises for invalid names
        return False
