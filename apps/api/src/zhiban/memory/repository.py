"""Memory repository with enforced user scoping and SQL-level TTL filtering."""

import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.db.models import Memory, MemoryCandidate


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _active_scope(self, user_id: uuid.UUID) -> tuple[ColumnElement[bool], ...]:
        """Return the mandatory active-memory filter (user + status + TTL)."""
        return (
            Memory.user_id == user_id,
            Memory.status == "active",
            Memory.deleted_at.is_(None),
            (Memory.expires_at.is_(None)) | (Memory.expires_at > func.now()),
        )

    async def get(self, *, user_id: uuid.UUID, memory_id: uuid.UUID) -> Memory | None:
        result = await self._session.execute(
            select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_fingerprint(
        self, *, user_id: uuid.UUID, fingerprint: str
    ) -> Memory | None:
        result = await self._session.execute(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.fingerprint == fingerprint,
                Memory.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_conflict_key(
        self, *, user_id: uuid.UUID, conflict_key: str
    ) -> list[Memory]:
        result = await self._session.execute(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.conflict_key == conflict_key,
                Memory.status == "active",
            )
        )
        return list(result.scalars())

    async def list_active(self, *, user_id: uuid.UUID, limit: int = 100) -> list[Memory]:
        result = await self._session.execute(
            select(Memory)
            .where(*self._active_scope(user_id))
            .order_by(Memory.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def add(self, memory: Memory) -> Memory:
        self._session.add(memory)
        await self._session.flush()
        return memory

    async def upsert_candidate(self, candidate: MemoryCandidate) -> MemoryCandidate:
        self._session.add(candidate)
        await self._session.flush()
        return candidate

    async def get_candidate_by_idempotency_key(
        self, *, user_id: uuid.UUID, idempotency_key: str
    ) -> MemoryCandidate | None:
        result = await self._session.execute(
            select(MemoryCandidate).where(
                MemoryCandidate.user_id == user_id,
                MemoryCandidate.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()
