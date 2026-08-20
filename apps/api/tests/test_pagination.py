"""Unit tests for cursor pagination primitives (no database)."""

import uuid
from datetime import UTC, datetime

import pytest
from zhiban.core.errors import AppError
from zhiban.core.pagination import decode_cursor, encode_cursor

SECRET = "test-secret-for-cursor-signing-32chars"


def test_cursor_roundtrip() -> None:
    ts = datetime(2026, 8, 18, 0, 0, tzinfo=UTC)
    rid = uuid.uuid4()
    encoded = encode_cursor(ts, rid, SECRET)
    decoded_ts, decoded_id = decode_cursor(encoded, SECRET)
    assert decoded_ts == ts
    assert decoded_id == rid


def test_cursor_rejects_tampered_payload() -> None:
    ts = datetime(2026, 8, 18, tzinfo=UTC)
    encoded = encode_cursor(ts, uuid.uuid4(), SECRET)
    # Tamper with the signature.
    tampered = encoded[:-1] + ("0" if encoded[-1] != "0" else "1")
    with pytest.raises(AppError) as exc_info:
        decode_cursor(tampered, SECRET)
    assert exc_info.value.status_code == 400


def test_cursor_rejects_wrong_secret() -> None:
    ts = datetime(2026, 8, 18, tzinfo=UTC)
    encoded = encode_cursor(ts, uuid.uuid4(), SECRET)
    with pytest.raises(AppError) as exc_info:
        decode_cursor(encoded, "different-secret-value")
    assert exc_info.value.status_code == 400


def test_cursor_rejects_garbage() -> None:
    with pytest.raises(AppError):
        decode_cursor("not-a-valid-cursor", SECRET)
