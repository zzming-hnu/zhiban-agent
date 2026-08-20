"""Integration tests for the memory governance API."""

import uuid

import httpx2 as httpx
import pytest


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: httpx.AsyncClient, prefix: str) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": _email(prefix), "password": "password123"},
    )
    assert r.status_code == 201


@pytest.mark.integration
async def test_memory_crud_and_isolation(client: httpx.AsyncClient, clean_database: None) -> None:
    await _register(client, "mema")

    # Create a memory explicitly.
    created = await client.post(
        "/api/v1/memories",
        json={
            "memory_type": "preference",
            "subject": "self",
            "predicate": "喜欢",
            "value": "少糖咖啡",
        },
    )
    assert created.status_code == 201
    mem_id = created.json()["id"]

    # List includes it.
    listing = await client.get("/api/v1/memories")
    assert listing.status_code == 200
    data = listing.json()["data"]
    assert any(m["id"] == mem_id for m in data)

    # Get by id.
    got = await client.get(f"/api/v1/memories/{mem_id}")
    assert got.status_code == 200
    assert got.json()["value"] == "少糖咖啡"

    # Update value.
    patched = await client.patch(f"/api/v1/memories/{mem_id}", json={"value": "多糖咖啡"})
    assert patched.status_code == 200
    assert patched.json()["value"] == "多糖咖啡"

    # Delete.
    deleted = await client.delete(f"/api/v1/memories/{mem_id}")
    assert deleted.status_code == 204

    # Gone from list.
    after = await client.get("/api/v1/memories")
    assert all(m["id"] != mem_id for m in after.json()["data"])


@pytest.mark.integration
async def test_cross_user_memory_isolation(client: httpx.AsyncClient, clean_database: None) -> None:
    await _register(client, "mema")
    created = await client.post(
        "/api/v1/memories",
        json={
            "memory_type": "preference",
            "subject": "self",
            "predicate": "喜欢",
            "value": "少糖咖啡",
        },
    )
    mem_id = created.json()["id"]

    # Log out A, register B.
    csrf = client.cookies.get("zhiban_csrf")
    await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf or "", "Origin": "http://localhost:3000"},
    )
    await _register(client, "memb")

    # B cannot access A's memory (404).
    assert (await client.get(f"/api/v1/memories/{mem_id}")).status_code == 404
    assert (
        await client.patch(f"/api/v1/memories/{mem_id}", json={"value": "hack"})
    ).status_code == 404
    assert (await client.delete(f"/api/v1/memories/{mem_id}")).status_code == 404
