"""Worker consumption loop with job-type dispatch."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zhiban.db.models import Job
from zhiban.workers.jobs import claim_jobs, mark_failed, mark_succeeded

logger = structlog.get_logger(__name__)

JobHandler = Callable[[AsyncSession, Job], Awaitable[None]]


class JobDispatcher:
    """Maps job_type strings to handler functions."""

    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        if job_type in self._handlers:
            raise ValueError(f"Job handler already registered: {job_type}")
        self._handlers[job_type] = handler

    def handles(self, job_type: str) -> bool:
        return job_type in self._handlers

    def job_types(self) -> list[str]:
        return list(self._handlers.keys())

    async def dispatch(self, session: AsyncSession, job: Job) -> None:
        handler = self._handlers.get(job.job_type)
        if handler is None:
            raise ValueError(f"No handler for job type: {job.job_type}")
        await handler(session, job)


async def consume_once(
    session_factory: async_sessionmaker[AsyncSession],
    dispatcher: JobDispatcher,
    *,
    worker_id: str,
    poll_interval_seconds: float = 1.0,
    lease_seconds: int = 120,
) -> bool:
    """Claim and process one batch of jobs; return True if any were processed."""
    worker = f"worker-{uuid.uuid4().hex[:8]}" if worker_id is None else worker_id
    processed = False

    async with session_factory() as session:
        jobs = await claim_jobs(
            session,
            worker_id=worker,
            job_types=dispatcher.job_types(),
            lease_seconds=lease_seconds,
        )

    for job in jobs:
        processed = True
        try:
            async with session_factory() as session:
                # Re-fetch the job inside a fresh session for a clean identity map.
                from sqlalchemy import select

                refreshed = (
                    await session.execute(select(Job).where(Job.id == job.id))
                ).scalar_one_or_none()
                if refreshed is None:
                    continue
                await dispatcher.dispatch(session, refreshed)
                await mark_succeeded(session, refreshed)
        except Exception as exc:  # noqa: BLE001 - job boundary
            await logger.aexception(
                "job_failed",
                job_type=job.job_type,
                job_id=str(job.id),
                error_type=type(exc).__name__,
            )
            async with session_factory() as session:
                refreshed = (
                    await session.execute(select(Job).where(Job.id == job.id))
                ).scalar_one_or_none()
                if refreshed is not None:
                    await mark_failed(
                        session, refreshed, error_code=type(exc).__name__, summary=str(exc)[:500]
                    )

    return processed


async def run_loop(
    session_factory: async_sessionmaker[AsyncSession],
    dispatcher: JobDispatcher,
    *,
    worker_id: str,
    stop_event: asyncio.Event,
    poll_interval_seconds: float = 1.0,
) -> None:
    """Run the consumption loop until stop_event is set."""
    await logger.ainfo("worker_loop_started", worker_id=worker_id)
    while not stop_event.is_set():
        try:
            processed = await consume_once(session_factory, dispatcher, worker_id=worker_id)
            if not processed:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)
        except TimeoutError:
            continue
        except Exception as exc:  # noqa: BLE001 - keep the loop alive
            await logger.aexception("worker_loop_error", error_type=type(exc).__name__)
            await asyncio.sleep(poll_interval_seconds)
    await logger.ainfo("worker_loop_stopped", worker_id=worker_id)
