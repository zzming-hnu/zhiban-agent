"""Sub-agent protocol: uniform contract for specialized agents.

The main (orchestrator) agent owns routing and the ReAct lifecycle. It may
delegate concrete work to a ``SubAgent``, which returns a structured summary
(not raw conversation) so the main agent can compose the final answer without
inheriting the sub-agent's internal reasoning.

``SubAgentResult`` mirrors ``ToolResult`` so the orchestrator can consume both
uniformly.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class SubAgentContext:
    """Request-scoped identity and conversation context for a sub-agent."""

    user_id: uuid.UUID
    conversation_id: uuid.UUID
    run_id: uuid.UUID
    user_input: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SubAgentResult:
    """Structured result returned by a sub-agent to the orchestrator."""

    ok: bool
    summary: str
    data: dict[str, Any] | list[Any] | None = None
    citations: list[str] = field(default_factory=list)
    error_code: str | None = None


@runtime_checkable
class SubAgent(Protocol):
    """A specialized agent the orchestrator can delegate to."""

    name: str

    async def run(self, ctx: SubAgentContext) -> SubAgentResult: ...
