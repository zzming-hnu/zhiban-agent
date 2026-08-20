"""Background job claim/lease/retry on top of the PostgreSQL `jobs` table."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.db.models import Job

DEFAULT_LEASE_SECONDS = 120
BACKOFF_SECONDS = [1, 5, 30, 120, 600]


@dataclass(slots=True)
class ClaimedJob:
    job: Job


async def claim_jobs(
    session: AsyncSession,
    *,
    worker_id: str,
    job_types: list[str] | None = None,
    limit: int = 20,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> list[Job]:
    """Claim due jobs with FOR UPDATE SKIP LOCKED, atomically setting a lease.

    Time comparisons use the database clock (``func.now()``) rather than the
    Python clock, so claim correctness does not depend on host/DB clock skew.
    """
    conditions = [
        Job.status.in_(("pending", "failed")),
        Job.available_at <= func.now(),
        Job.attempts < Job.max_attempts,
    ]
    if job_types:
        conditions.append(Job.job_type.in_(job_types))

    query = (
        select(Job)
        .where(*conditions)
        .order_by(Job.priority.desc(), Job.available_at, Job.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    result = await session.execute(query)
    jobs = list(result.scalars())
    if not jobs:
        return []

    ids = [j.id for j in jobs]
    await session.execute(
        update(Job)
        .where(Job.id.in_(ids))
        .values(
            status="running",
            lease_owner=worker_id,
            lease_expires_at=func.now() + timedelta(seconds=lease_seconds),
            attempts=Job.attempts + 1,
            updated_at=func.now(),
        )
    )
    await session.commit()
    # Re-read claimed jobs so callers see the updated status.
    refreshed = await session.execute(select(Job).where(Job.id.in_(ids)))
    return list(refreshed.scalars())


async def mark_succeeded(session: AsyncSession, job: Job) -> None:
    job.status = "succeeded"
    job.finished_at = func.now()
    job.lease_owner = None
    job.lease_expires_at = None
    await session.commit()


async def mark_failed(session: AsyncSession, job: Job, *, error_code: str, summary: str) -> None:
    job.last_error_code = error_code
    job.last_error_summary = summary
    job.lease_owner = None
    job.lease_expires_at = None

    if job.attempts >= job.max_attempts:
        job.status = "dead"
        job.finished_at = func.now()
    else:
        job.status = "failed"
        # Exponential backoff before the next claim, using the DB clock.
        backoff = BACKOFF_SECONDS[min(job.attempts, len(BACKOFF_SECONDS) - 1)]
        job.available_at = func.now() + timedelta(seconds=backoff)
    await session.commit()


async def enqueue_job(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    job_type: str,
    payload: dict[str, object],
    idempotency_key: str,
    priority: int = 0,
    max_attempts: int = 5,
) -> Job:
    """Enqueue a job; idempotent on (job_type, idempotency_key)."""
    existing = (
        await session.execute(
            select(Job).where(
                Job.job_type == job_type,
                Job.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    job = Job(
        user_id=user_id,
        job_type=job_type,
        payload=payload,
        idempotency_key=idempotency_key,
        priority=priority,
        max_attempts=max_attempts,
    )
    session.add(job)
    await session.flush()
    return job
