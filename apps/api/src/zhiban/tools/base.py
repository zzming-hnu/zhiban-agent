"""Tool protocol, execution context, and result envelope."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from zhiban.tools.spec import ToolSpec

# TInput appears only in a contravariant position (execute's argument), so it
# must be contravariant for the Protocol to be a valid structural type.
TInput = TypeVar("TInput", bound=BaseModel, contravariant=True)


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Request-scoped identity and run context injected by the executor.

    ``user_id`` comes from the authenticated principal, never from model args.
    """

    user_id: uuid.UUID
    run_id: uuid.UUID
    conversation_id: uuid.UUID | None = None


@dataclass(slots=True)
class ToolResult:
    ok: bool
    data: dict[str, Any] | list[Any] | None = None
    summary: str = ""
    error_code: str | None = None
    retryable: bool = False
    citations: list[str] = field(default_factory=list)
    truncated: bool = False


@runtime_checkable
class Tool(Protocol[TInput]):
    spec: ToolSpec

    async def execute(self, ctx: ToolContext, args: TInput) -> ToolResult: ...
