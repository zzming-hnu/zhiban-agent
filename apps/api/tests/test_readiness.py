from types import SimpleNamespace
from typing import Any, cast

import pytest
from zhiban.core.readiness import evaluate_readiness
from zhiban.core.resources import AppResources


@pytest.mark.asyncio
async def test_unavailable_dependencies_fail_closed() -> None:
    class UnavailableDatabase:
        configured = True

        async def ping(self) -> None:
            raise TimeoutError

    class UnavailableRedis:
        configured = True

        async def ping(self) -> None:
            raise ConnectionError

    resources = cast(
        AppResources,
        cast(
            Any,
            SimpleNamespace(
                database=UnavailableDatabase(),
                redis=UnavailableRedis(),
                migration_head="expected",
            ),
        ),
    )

    snapshot = await evaluate_readiness(resources, timeout_seconds=0.1)

    assert snapshot.ready is False
    assert snapshot.checks == {
        "configuration": "ok",
        "database": "unavailable",
        "migrations": "unavailable",
        "redis": "unavailable",
    }


@pytest.mark.asyncio
async def test_revision_mismatch_reports_migration_pending() -> None:
    class MigratedDatabase:
        configured = True

        async def ping(self) -> None:
            return None

        async def current_revision(self) -> str:
            return "old_revision"

    class HealthyRedis:
        configured = True

        async def ping(self) -> None:
            return None

    resources = cast(
        AppResources,
        cast(
            Any,
            SimpleNamespace(
                database=MigratedDatabase(),
                redis=HealthyRedis(),
                migration_head="expected_revision",
            ),
        ),
    )

    snapshot = await evaluate_readiness(resources, timeout_seconds=0.1)

    assert snapshot.ready is False
    assert snapshot.checks["database"] == "ok"
    assert snapshot.checks["migrations"] == "migration_pending"
    assert snapshot.checks["redis"] == "ok"
