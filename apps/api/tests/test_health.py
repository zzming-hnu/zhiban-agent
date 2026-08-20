from types import SimpleNamespace
from typing import Any, cast

from fastapi.testclient import TestClient
from zhiban.core.config import Settings
from zhiban.core.resources import AppResources
from zhiban.main import create_app


def test_live_reports_process_identity() -> None:
    app = create_app(Settings(_env_file=None, app_env="test", app_version="test-version"))

    with TestClient(app) as client:
        response = client.get("/api/v1/health/live", headers={"x-request-id": "req_test"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "version": "test-version",
    }
    assert response.headers["x-request-id"] == "req_test"


def test_ready_is_honest_before_database_and_redis_are_connected() -> None:
    app = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url=None,
            redis_url=None,
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"] == {
        "configuration": "ok",
        "database": "not_configured",
        "migrations": "not_configured",
        "redis": "not_configured",
    }


def test_ready_reports_ok_when_all_checks_succeed() -> None:
    class HealthyDatabase:
        configured = True

        async def ping(self) -> None:
            return None

        async def current_revision(self) -> str:
            return "test_head"

    class HealthyRedis:
        configured = True

        async def ping(self) -> None:
            return None

    resources = cast(
        AppResources,
        cast(
            Any,
            SimpleNamespace(
                database=HealthyDatabase(),
                redis=HealthyRedis(),
                migration_head="test_head",
            ),
        ),
    )
    app = create_app(Settings(_env_file=None, app_env="test"), resources=resources)

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "configuration": "ok",
            "database": "ok",
            "migrations": "ok",
            "redis": "ok",
        },
    }
