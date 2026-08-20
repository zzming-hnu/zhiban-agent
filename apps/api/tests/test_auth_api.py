"""Integration tests for the auth API (register/login/logout/sessions/me)."""

import uuid

import httpx2 as httpx
import pytest


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.integration
async def test_register_login_me_logout_flow(client: httpx.AsyncClient) -> None:
    email = _email("flow")
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Flow"},
    )
    assert reg.status_code == 201
    assert reg.json()["user"]["email"] == email
    assert "session" in reg.json()

    assert "zhiban_session" in client.cookies

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email

    csrf = client.cookies.get("zhiban_csrf")
    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf or "", "Origin": "http://localhost:3000"},
    )
    assert logout.status_code == 204

    me_after = await client.get("/api/v1/auth/me")
    assert me_after.status_code == 401


@pytest.mark.integration
async def test_login_unified_error_hides_account_existence(client: httpx.AsyncClient) -> None:
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": _email("nobody"), "password": "x"}
    )
    assert unknown.status_code == 401
    assert unknown.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.integration
async def test_sessions_list_and_revoke(client: httpx.AsyncClient) -> None:
    email = _email("sessions")
    reg = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert reg.status_code == 201
    session_id = reg.json()["session"]["id"]

    listing = await client.get("/api/v1/auth/sessions")
    assert listing.status_code == 200
    ids = [s["id"] for s in listing.json()]
    assert session_id in ids

    revoke = await client.delete(
        f"/api/v1/auth/sessions/{session_id}",
        headers={"Origin": "http://localhost:3000"},
    )
    assert revoke.status_code == 204

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


@pytest.mark.integration
async def test_csrf_origin_mismatch_rejected(client: httpx.AsyncClient) -> None:
    email = _email("csrf")
    reg = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert reg.status_code == 201
    csrf = client.cookies.get("zhiban_csrf")

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf or "", "Origin": "https://evil.example.com"},
    )
    assert logout.status_code == 403
