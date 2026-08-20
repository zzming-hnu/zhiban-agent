import asyncio
from dataclasses import dataclass
from typing import Literal

import structlog

from zhiban.core.resources import AppResources

logger = structlog.get_logger(__name__)

CheckState = Literal["ok", "not_configured", "unavailable", "migration_pending"]


@dataclass(frozen=True, slots=True)
class ReadinessSnapshot:
    ready: bool
    checks: dict[str, CheckState]


async def _database_checks(
    resources: AppResources, timeout_seconds: float
) -> dict[str, CheckState]:
    if not resources.database.configured:
        return {
            "database": "not_configured",
            "migrations": "not_configured",
        }

    try:
        async with asyncio.timeout(timeout_seconds):
            await resources.database.ping()
    except Exception as error:
        await logger.awarning("database_readiness_failed", error_type=type(error).__name__)
        return {
            "database": "unavailable",
            "migrations": "unavailable",
        }

    try:
        async with asyncio.timeout(timeout_seconds):
            current_revision = await resources.database.current_revision()
    except Exception as error:
        await logger.awarning("migration_readiness_failed", error_type=type(error).__name__)
        return {
            "database": "ok",
            "migrations": "migration_pending",
        }

    migration_state: CheckState = (
        "ok" if current_revision == resources.migration_head else "migration_pending"
    )
    return {
        "database": "ok",
        "migrations": migration_state,
    }


async def _redis_check(resources: AppResources, timeout_seconds: float) -> CheckState:
    if not resources.redis.configured:
        return "not_configured"
    try:
        async with asyncio.timeout(timeout_seconds):
            await resources.redis.ping()
    except Exception as error:
        await logger.awarning("redis_readiness_failed", error_type=type(error).__name__)
        return "unavailable"
    return "ok"


async def evaluate_readiness(
    resources: AppResources, *, timeout_seconds: float
) -> ReadinessSnapshot:
    database_checks, redis_state = await asyncio.gather(
        _database_checks(resources, timeout_seconds),
        _redis_check(resources, timeout_seconds),
    )
    checks: dict[str, CheckState] = {
        "configuration": "ok",
        **database_checks,
        "redis": redis_state,
    }
    return ReadinessSnapshot(
        ready=all(state == "ok" for state in checks.values()),
        checks=checks,
    )
