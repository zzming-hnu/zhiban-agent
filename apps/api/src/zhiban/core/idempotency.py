"""Idempotency-Key support backed by idempotency_records.

A single helper used inside routes that need idempotent writes. It returns a
three-state outcome so the route can either replay, reject, or proceed.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.core.errors import AppError
from zhiban.db.models import IdempotencyRecord

IDEMPOTENCY_HEADER = "Idempotency-Key"
TTL_HOURS = 24


@dataclass(frozen=True, slots=True)
class IdempotencyOutcome:
    action: str  # "replay" | "conflict" | "new"
    record: IdempotencyRecord | None = None


class Idempotency:
    def __init__(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        method: str,
        route: str,
        key: str | None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._method = method
        self._route = route
        self._key = key
        self._request_hash = hashlib.sha256(b"").hexdigest()
        self._record: IdempotencyRecord | None = None

    def set_body(self, body: bytes) -> None:
        self._request_hash = hashlib.sha256(body).hexdigest()

    async def begin(self) -> IdempotencyOutcome:
        if not self._key:
            return IdempotencyOutcome(action="new")

        result = await self._session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == self._user_id,
                IdempotencyRecord.method == self._method,
                IdempotencyRecord.route == self._route,
                IdempotencyRecord.key == self._key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != self._request_hash:
                raise AppError(
                    code="idempotency_key_reused",
                    message="幂等键已被不同请求使用",
                    status_code=409,
                )
            if existing.state == "completed":
                return IdempotencyOutcome(action="replay", record=existing)
            raise AppError(
                code="idempotency_in_flight",
                message="请求正在处理中",
                status_code=409,
            )

        record = IdempotencyRecord(
            user_id=self._user_id,
            method=self._method,
            route=self._route,
            key=self._key,
            request_hash=self._request_hash,
            state="processing",
            expires_at=datetime.now(UTC) + timedelta(hours=TTL_HOURS),
        )
        self._session.add(record)
        self._record = record
        await self._session.flush()
        return IdempotencyOutcome(action="new")

    async def finish(self, status_code: int, body: dict[str, Any]) -> None:
        if self._record is None:
            return
        self._record.response_status = status_code
        self._record.response_body = body
        self._record.state = "completed"
