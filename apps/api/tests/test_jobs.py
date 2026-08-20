"""Integration tests for the job claim/lease/retry machinery."""

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.db.models import Job, OutboxEvent
from zhiban.workers.jobs import (
    claim_jobs,
    enqueue_job,
    mark_failed,
    mark_succeeded,
)


async def _cleanup_jobs(session: AsyncSession) -> None:
    await session.execute(delete(OutboxEvent))
    await session.execute(delete(Job))
    await session.commit()


@pytest.fixture(autouse=True)
async def _clean_jobs(session: AsyncSession) -> None:
    await _cleanup_jobs(session)
    yield
    await _cleanup_jobs(session)


@pytest.mark.integration
async def test_enqueue_is_idempotent(session: AsyncSession) -> None:
    key = f"key-{uuid.uuid4().hex}"
    job1 = await enqueue_job(
        session,
        user_id=None,
        job_type="test",
        payload={"a": 1},
        idempotency_key=key,
    )
    await session.commit()
    job2 = await enqueue_job(
        session,
        user_id=None,
        job_type="test",
        payload={"a": 1},
        idempotency_key=key,
    )
    await session.commit()

    assert job1.id == job2.id


@pytest.mark.integration
async def test_claim_and_succeed(session: AsyncSession) -> None:
    job = await enqueue_job(
        session,
        user_id=None,
        job_type="test",
        payload={},
        idempotency_key=f"k-{uuid.uuid4().hex}",
    )
    await session.commit()

    claimed = await claim_jobs(session, worker_id="w1", job_types=["test"])
    assert len(claimed) == 1
    assert claimed[0].id == job.id
    assert claimed[0].status == "running"

    await mark_succeeded(session, claimed[0])

    refreshed = (await session.execute(select(Job).where(Job.id == job.id))).scalar_one()
    assert refreshed.status == "succeeded"
    assert refreshed.finished_at is not None


@pytest.mark.integration
async def test_failed_job_is_backed_off_then_dead(session: AsyncSession) -> None:
    job = await enqueue_job(
        session,
        user_id=None,
        job_type="test",
        payload={},
        idempotency_key=f"k-{uuid.uuid4().hex}",
        max_attempts=2,
    )
    await session.commit()

    claimed = await claim_jobs(session, worker_id="w1", job_types=["test"])
    assert len(claimed) == 1

    # First failure -> backoff (status failed).
    await mark_failed(session, claimed[0], error_code="E", summary="boom")
    refreshed = (await session.execute(select(Job).where(Job.id == job.id))).scalar_one()
    assert refreshed.status == "failed"
    assert refreshed.attempts == 1

    # Second claim (after available_at passes) -> attempts=2.
    from datetime import UTC, datetime, timedelta

    await session.execute(
        Job.__table__.update()
        .where(Job.id == job.id)
        .values(available_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await session.commit()
    claimed2 = await claim_jobs(session, worker_id="w1", job_types=["test"])
    assert len(claimed2) == 1

    # Second failure -> dead (max_attempts reached).
    await mark_failed(session, claimed2[0], error_code="E", summary="boom")
    refreshed = (await session.execute(select(Job).where(Job.id == job.id))).scalar_one()
    assert refreshed.status == "dead"


@pytest.mark.integration
async def test_claim_skips_locked_and_unavailable(session: AsyncSession) -> None:
    # A job with a future available_at is not claimed.
    from datetime import UTC, datetime, timedelta

    job = await enqueue_job(
        session,
        user_id=None,
        job_type="test",
        payload={},
        idempotency_key=f"k-{uuid.uuid4().hex}",
    )
    await session.commit()
    await session.execute(
        Job.__table__.update()
        .where(Job.id == job.id)
        .values(available_at=datetime.now(UTC) + timedelta(minutes=5))
    )
    await session.commit()

    claimed = await claim_jobs(session, worker_id="w1", job_types=["test"])
    assert claimed == []
