"""Worker entrypoint: consume background jobs (memory extraction, etc.)."""

import asyncio
import signal
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zhiban.core.config import get_settings
from zhiban.core.resources import AppResources
from zhiban.db.session import create_session_factory
from zhiban.observability.logging import configure_logging
from zhiban.workers.memory_jobs import handle_memory_consolidate, handle_memory_extract
from zhiban.workers.reminder_jobs import handle_reminder_deliver, handle_reminder_scan
from zhiban.workers.runner import JobDispatcher, run_loop

logger = structlog.get_logger(__name__)


def build_dispatcher() -> JobDispatcher:
    dispatcher = JobDispatcher()
    dispatcher.register("memory.extract", handle_memory_extract)
    dispatcher.register("memory.consolidate", handle_memory_consolidate)
    dispatcher.register("reminder.scan", handle_reminder_scan)
    dispatcher.register("reminder.deliver", handle_reminder_deliver)
    return dispatcher


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(
        log_level=settings.log_level,
        service="worker",
        environment=settings.app_env,
        version=settings.app_version,
    )

    resources = AppResources.from_settings(settings)
    session_factory = create_session_factory(resources.database)
    dispatcher = build_dispatcher()
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop_event.set)
        except NotImplementedError:
            pass

    await logger.ainfo("worker_started", worker_id=worker_id, demo_mode=settings.demo_mode)

    try:
        await asyncio.gather(
            run_loop(session_factory, dispatcher, worker_id=worker_id, stop_event=stop_event),
            reminder_scan_loop(session_factory, stop_event=stop_event),
        )
    finally:
        await resources.close()

    await logger.ainfo("worker_stopped", worker_id=worker_id)


async def reminder_scan_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stop_event: asyncio.Event,
    interval_seconds: float = 30.0,
) -> None:
    """Periodically scan and deliver due reminders."""
    from zhiban.workers.reminder_jobs import scan_and_deliver

    await logger.ainfo("reminder_scan_loop_started")
    while not stop_event.is_set():
        try:
            async with session_factory() as session:
                await scan_and_deliver(session)
        except Exception as exc:  # noqa: BLE001 - keep the scan loop alive
            await logger.aexception("reminder_scan_error", error_type=type(exc).__name__)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue
    await logger.ainfo("reminder_scan_loop_stopped")


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
