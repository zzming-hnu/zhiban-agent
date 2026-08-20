"""Unit tests for the agent event model and SSE framing (no database)."""

import uuid

from zhiban.agent.events import (
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_STARTED,
    AgentEvent,
    EventSequencer,
)
from zhiban.conversations.stream import sse_event


def test_sequencer_is_monotonically_increasing() -> None:
    seq = EventSequencer()
    values = [seq.next() for _ in range(5)]
    assert values == [1, 2, 3, 4, 5]


def test_event_sse_id_contains_run_and_seq() -> None:
    run_id = uuid.uuid4()
    event = AgentEvent(type=RUN_STARTED, seq=7, run_id=run_id)
    assert event.sse_id() == f"{run_id}:7"


def test_terminal_events_are_flagged() -> None:
    run_id = uuid.uuid4()
    completed = AgentEvent(type=RUN_COMPLETED, seq=1, run_id=run_id)
    failed = AgentEvent(type=RUN_FAILED, seq=2, run_id=run_id)
    started = AgentEvent(type=RUN_STARTED, seq=3, run_id=run_id)

    assert completed.is_terminal
    assert failed.is_terminal
    assert not started.is_terminal


def test_sse_framing_contains_event_and_data() -> None:
    run_id = uuid.uuid4()
    event = AgentEvent(type=RUN_STARTED, seq=1, run_id=run_id, data={"model": "kimi-k2.5"})
    frame = sse_event(event)

    assert frame.startswith(f"id: {run_id}:1\n")
    assert "event: run.started\n" in frame
    assert "data: " in frame
    assert "kimi-k2.5" in frame
    assert frame.endswith("\n\n")
