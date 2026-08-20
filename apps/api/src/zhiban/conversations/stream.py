"""SSE encoding helpers for the run stream endpoint."""

from zhiban.agent.events import PING, AgentEvent


def sse_event(event: AgentEvent) -> str:
    """Serialize an agent event as an SSE frame (id + event + data)."""
    id_part = event.sse_id()
    return f"id: {id_part}\nevent: {event.type}\ndata: {event.to_sse_data()}\n\n"


def sse_ping() -> str:
    return f"event: {PING}\ndata: {{}}\n\n"
