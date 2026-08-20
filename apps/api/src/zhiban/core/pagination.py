"""Cursor pagination: encode/decode a signed sort key."""

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime
from typing import Any

from zhiban.core.config import Settings
from zhiban.core.errors import AppError


def _sign(data: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()


def encode_cursor(updated_at: datetime, resource_id: uuid.UUID, secret: str) -> str:
    payload = json.dumps(
        {"t": updated_at.isoformat(), "id": str(resource_id)},
        separators=(",", ":"),
    )
    raw = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{raw}.{_sign(raw, secret)}"


def decode_cursor(cursor: str, secret: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw, signature = cursor.rsplit(".", 1)
        if not hmac.compare_digest(_sign(raw, secret), signature):
            raise ValueError("bad signature")
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8"))
        return datetime.fromisoformat(payload["t"]), uuid.UUID(payload["id"])
    except (ValueError, KeyError, TypeError) as error:
        raise AppError(code="invalid_cursor", message="分页游标无效", status_code=400) from error


def cursor_secret(settings: Settings) -> str:
    return settings.session_secret.get_secret_value()


def page_result(
    items: list[Any],
    limit: int,
    has_more_key: Any = None,
) -> tuple[list[Any], bool]:
    """Split a `limit + 1` result set into a page and a has-more flag."""
    has_more = len(items) > limit
    return items[:limit], has_more
