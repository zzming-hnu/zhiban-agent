"""Agent run lifecycle: create, status transitions, and event buffering."""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.agent.events import AgentEvent
from zhiban.core.errors import AppError
from zhiban.db.models import AgentRun, Message

ACTIVE_RUN_STATUSES = ("queued", "running", "waiting_confirmation")
TERMINAL_RUN_STATUSES = ("completed", "failed", "cancelled")


@dataclass(slots=True)
class RunSnapshot:
    run_id: uuid.UUID
    status: str
    assistant_message_id: uuid.UUID | None
    assistant_content: str
    error_code: str | None


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
        assistant_message_id: uuid.UUID,
        model: str | None,
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            status="queued",
            model=model,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get(self, *, user_id: uuid.UUID, run_id: uuid.UUID) -> AgentRun | None:
        result = await self._session.execute(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, *, user_id: uuid.UUID, run_id: uuid.UUID) -> AgentRun:
        run = await self.get(user_id=user_id, run_id=run_id)
        if run is None:
            raise AppError(code="not_found", message="运行不存在", status_code=404)
        return run

    async def mark_running(self, run: AgentRun) -> None:
        run.status = "running"
        run.started_at = datetime.now(UTC)

    async def mark_completed(self, run: AgentRun) -> None:
        run.status = "completed"
        run.finished_at = datetime.now(UTC)

    async def mark_failed(self, run: AgentRun, error_code: str | None) -> None:
        run.status = "failed"
        run.error_code = error_code
        run.finished_at = datetime.now(UTC)

    async def mark_cancelled(self, run: AgentRun) -> None:
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)

    async def cancel_active_for_conversation(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> None:
        """Cancel any active run in the conversation (interrupted runs)."""
        result = await self._session.execute(
            select(AgentRun).where(
                AgentRun.user_id == user_id,
                AgentRun.conversation_id == conversation_id,
                AgentRun.status.in_(ACTIVE_RUN_STATUSES),
            )
        )
        for run in result.scalars():
            run.status = "cancelled"
            run.finished_at = datetime.now(UTC)


class EventBuffer:
    """Short-lived per-run event buffer backed by Redis, with DB fallback."""

    def __init__(self, redis: Any | None) -> None:
        self._redis = redis

    def _key(self, run_id: uuid.UUID) -> str:
        return f"sse:events:{run_id}"

    async def append(self, run_id: uuid.UUID, event: AgentEvent) -> None:
        if self._redis is None:
            return
        payload = json.dumps(
            {
                "type": event.type,
                "seq": event.seq,
                "data": event.data,
                "error": event.error,
            },
            ensure_ascii=False,
        )
        try:
            await self._redis.rpush(self._key(run_id), payload)
            await self._redis.expire(self._key(run_id), 15 * 60)
        except Exception:  # noqa: BLE001 - Redis is best-effort
            return

    async def events_after(self, run_id: uuid.UUID, after_seq: int) -> list[AgentEvent]:
        if self._redis is None:
            return []
        try:
            raw = await self._redis.lrange(self._key(run_id), 0, -1)
        except Exception:  # noqa: BLE001
            return []
        events: list[AgentEvent] = []
        for item in raw:
            payload = json.loads(item)
            if payload["seq"] > after_seq:
                events.append(
                    AgentEvent(
                        type=payload["type"],
                        seq=payload["seq"],
                        run_id=run_id,
                        data=payload.get("data", {}),
                        error=payload.get("error"),
                    )
                )
        return events


async def build_snapshot(
    session: AsyncSession, *, user_id: uuid.UUID, run_id: uuid.UUID
) -> RunSnapshot:
    """Build a run snapshot from persisted state (used when buffer is missing)."""
    run = await RunRepository(session).get(user_id=user_id, run_id=run_id)
    if run is None:
        raise AppError(code="not_found", message="运行不存在", status_code=404)

    assistant_content = ""
    if run.assistant_message_id is not None:
        result = await session.execute(
            select(Message).where(Message.id == run.assistant_message_id)
        )
        msg = result.scalar_one_or_none()
        if msg is not None:
            assistant_content = msg.content

    return RunSnapshot(
        run_id=run_id,
        status=run.status,
        assistant_message_id=run.assistant_message_id,
        assistant_content=assistant_content,
        error_code=run.error_code,
    )
