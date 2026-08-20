"""Tests for user-facing memory categories."""

import uuid

import httpx2 as httpx
import pytest


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.integration
async def test_create_memory_with_category(client: httpx.AsyncClient, clean_database: None) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": _email("cat"), "password": "password123"},
    )
    assert r.status_code == 201

    created = await client.post(
        "/api/v1/memories",
        json={
            "memory_type": "communication",
            "category": "communication_taboo",
            "subject": "self",
            "predicate": "不要",
            "value": "使用 emoji",
        },
    )
    assert created.status_code == 201
    assert created.json()["category"] == "communication_taboo"

    # Listing returns the category.
    listing = await client.get("/api/v1/memories")
    data = listing.json()["data"]
    assert any(m["category"] == "communication_taboo" for m in data)


@pytest.mark.integration
async def test_update_memory_category(client: httpx.AsyncClient, clean_database: None) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": _email("cat"), "password": "password123"},
    )
    assert r.status_code == 201

    created = await client.post(
        "/api/v1/memories",
        json={
            "memory_type": "preference",
            "category": "other",
            "subject": "self",
            "predicate": "喜欢",
            "value": "少糖",
        },
    )
    mem_id = created.json()["id"]

    patched = await client.patch(
        f"/api/v1/memories/{mem_id}",
        json={"category": "communication_preference"},
    )
    assert patched.status_code == 200
    assert patched.json()["category"] == "communication_preference"


def test_category_enum_values() -> None:
    from zhiban.memory.types import MemoryCategory

    assert set(MemoryCategory) == {
        "basic_info",
        "communication_taboo",
        "communication_preference",
        "other",
    }
