"""Integration tests for conversation/message CRUD, pagination, and idempotency."""

import uuid

import httpx2 as httpx
import pytest


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: httpx.AsyncClient, prefix: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": _email(prefix), "password": "password123"},
    )
    assert resp.status_code == 201


@pytest.mark.integration
async def test_conversation_crud_and_pagination(client: httpx.AsyncClient) -> None:
    await _register(client, "conv")

    ids = []
    for i in range(5):
        resp = await client.post("/api/v1/conversations", json={"title": f"会话 {i}"})
        assert resp.status_code == 201
        ids.append(resp.json()["id"])

    page1 = await client.get("/api/v1/conversations?limit=2")
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["data"]) == 2
    assert body1["has_more"] is True
    assert body1["next_cursor"] is not None

    page2 = await client.get(f"/api/v1/conversations?limit=2&cursor={body1['next_cursor']}")
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["data"]) == 2

    page1_ids = {c["id"] for c in body1["data"]}
    page2_ids = {c["id"] for c in body2["data"]}
    assert page1_ids.isdisjoint(page2_ids)

    target = ids[0]
    renamed = await client.patch(f"/api/v1/conversations/{target}", json={"title": "改过名"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "改过名"

    deleted = await client.delete(f"/api/v1/conversations/{target}")
    assert deleted.status_code == 204
    remaining = (await client.get("/api/v1/conversations?limit=100")).json()["data"]
    assert target not in {c["id"] for c in remaining}


@pytest.mark.integration
async def test_message_create_list_and_client_dedupe(client: httpx.AsyncClient) -> None:
    await _register(client, "msg")

    conv = await client.post("/api/v1/conversations", json={"title": "测试"})
    conv_id = conv.json()["id"]

    created = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "你好", "client_message_id": "client-1"},
    )
    assert created.status_code == 202
    body = created.json()
    msg_id = body["message_id"]
    run_id = body["run_id"]
    assert body["stream_url"] == f"/runs/{run_id}/stream"

    duplicate = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "你好", "client_message_id": "client-1"},
    )
    assert duplicate.status_code == 409

    listing = await client.get(f"/api/v1/conversations/{conv_id}/messages")
    assert listing.status_code == 200
    data = listing.json()["data"]
    # Two messages: the user message and the assistant placeholder.
    assert len(data) == 2
    assert {m["id"] for m in data} == {msg_id, body["assistant_message_id"]}


@pytest.mark.integration
async def test_idempotency_key_replay_and_conflict(client: httpx.AsyncClient) -> None:
    await _register(client, "idem")

    headers = {"Idempotency-Key": f"key-{uuid.uuid4().hex[:8]}"}
    first = await client.post("/api/v1/conversations", json={"title": "幂等"}, headers=headers)
    assert first.status_code == 201
    conv_id = first.json()["id"]

    replay = await client.post("/api/v1/conversations", json={"title": "幂等"}, headers=headers)
    assert replay.status_code == 201
    assert replay.json()["id"] == conv_id

    conflict = await client.post("/api/v1/conversations", json={"title": "不同"}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_key_reused"


@pytest.mark.integration
async def test_message_validation_rejects_empty_and_oversize(client: httpx.AsyncClient) -> None:
    await _register(client, "val")

    conv = await client.post("/api/v1/conversations", json={"title": "验证"})
    conv_id = conv.json()["id"]

    empty = await client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": ""})
    assert empty.status_code == 422

    oversized = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "x" * 20001},
    )
    assert oversized.status_code == 422
