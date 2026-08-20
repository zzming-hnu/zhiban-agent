from fastapi import FastAPI
from fastapi.testclient import TestClient
from zhiban.core.config import Settings
from zhiban.core.request_context import resolve_request_id
from zhiban.main import create_app


def test_request_id_accepts_safe_value_and_replaces_unsafe_value() -> None:
    assert resolve_request_id("req-client_123") == "req-client_123"

    generated = resolve_request_id("unsafe request id with spaces")

    assert generated.startswith("req_")
    assert " " not in generated


def test_unhandled_error_uses_safe_envelope() -> None:
    app: FastAPI = create_app(Settings(_env_file=None, app_env="test"))

    @app.get("/test-error")
    async def test_error() -> None:
        raise RuntimeError("database password should never be returned")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-error", headers={"x-request-id": "req_error_test"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "服务暂时无法处理该请求",
            "details": [],
            "retryable": False,
        },
        "request_id": "req_error_test",
    }
    assert "password" not in response.text
