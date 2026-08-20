"""Domain event model shared by the agent loop, SSE, and event buffer."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# Stable SSE event types (SPEC-AG-001).
RUN_STARTED = "run.started"
RUN_SNAPSHOT = "run.snapshot"
RUN_COMPLETED = "run.completed"
RUN_FAILED = "run.failed"
RUN_CANCELLED = "run.cancelled"
AGENT_THINKING = "agent.thinking"
MESSAGE_DELTA = "message.delta"
MESSAGE_COMPLETED = "message.completed"
TOOL_CALL_STARTED = "tool.call.started"
TOOL_CALL_COMPLETED = "tool.call.completed"
TOOL_CALL_FAILED = "tool.call.failed"
WARNING_DEGRADED = "warning.degraded"
PING = "ping"

_TERMINAL_TYPES = {RUN_COMPLETED, RUN_FAILED, RUN_CANCELLED}


@dataclass(slots=True)
class AgentEvent:
    type: str
    seq: int
    run_id: uuid.UUID
    data: dict[str, Any] = field(default_factory=dict)
    message_id: uuid.UUID | None = None
    tool_call_id: str | None = None
    error: dict[str, Any] | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex}")

    @property
    def is_terminal(self) -> bool:
        return self.type in _TERMINAL_TYPES

    def sse_id(self) -> str:
        return f"{self.run_id}:{self.seq}"

    def to_sse_data(self) -> str:
        import json

        payload: dict[str, Any] = {
            "seq": self.seq,
            "run_id": str(self.run_id),
            "event_id": self.event_id,
            "occurred_at": self.occurred_at.isoformat(),
            "data": self.data,
        }
        if self.message_id is not None:
            payload["message_id"] = str(self.message_id)
        if self.tool_call_id is not None:
            payload["tool_call_id"] = self.tool_call_id
        if self.error is not None:
            payload["error"] = self.error
        return json.dumps(payload, ensure_ascii=False)


class EventSequencer:
    """Assigns monotonically increasing seq numbers within a single run."""

    def __init__(self) -> None:
        self._next = 0

    def next(self) -> int:
        self._next += 1
        return self._next

    @property
    def current(self) -> int:
        return self._next
