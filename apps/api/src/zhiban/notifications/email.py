"""Email delivery for reminders via SMTP (best-effort, synchronous).

Uses the standard library ``smtplib`` so we avoid an extra async dependency.
Reminder delivery runs in the worker; SMTP sends are short-lived and wrapped
in ``asyncio.to_thread`` so they never block the event loop.
"""

import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

import structlog
from zhiban.core.config import Settings

logger = structlog.get_logger(__name__)


def _build_message(
    *,
    to: str,
    subject: str,
    body: str,
    sender: str,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def _send_sync(
    *,
    host: str,
    port: int,
    username: str | None,
    password: str,
    use_tls: bool,
    message: EmailMessage,
) -> None:
    # Port 465 = implicit SSL; other ports (e.g. 587) use STARTTLS.
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    elif use_tls:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(message)


class EmailSender:
    """Send reminder emails when SMTP is configured; silent no-op otherwise."""

    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.smtp_enabled
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = (
            settings.smtp_password.get_secret_value() if settings.smtp_password else ""
        )
        self._from = settings.smtp_from
        self._use_tls = settings.smtp_use_tls

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send_reminder(self, *, to: str, title: str, remind_at: str) -> bool:
        """Send a reminder email. Returns True on success (or when disabled)."""
        if not self._enabled:
            return True

        sender = self._from
        if self._username and "@" in self._username:
            sender = formataddr(("知伴", self._username))

        subject = f"⏰ 知伴提醒：{title}"
        body = (
            f"你设置的提醒到时间了：\n\n{title}\n\n"
            f"提醒时间：{remind_at}\n\n—— 知伴 · 你的个人 AI 助理"
        )

        message = _build_message(to=to, subject=subject, body=body, sender=sender)

        try:
            await asyncio.to_thread(
                _send_sync,
                host=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                use_tls=self._use_tls,
                message=message,
            )
            return True
        except Exception as exc:  # noqa: BLE001 - email is best-effort
            await logger.awarning("reminder_email_failed", error=type(exc).__name__)
            return False
