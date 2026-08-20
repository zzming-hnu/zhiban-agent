"""Tool execution hooks: before / after / on_error.

Hooks may only observe the request context, reject a call, or normalize
args/results. They must not mutate cross-request global state.
"""

from typing import Protocol

from pydantic import BaseModel

from zhiban.tools.base import ToolContext, ToolResult


class BeforeToolHook(Protocol):
    async def before(self, ctx: ToolContext, tool_name: str, args: BaseModel) -> None:
        """Observe or reject a call before execution (raise to reject)."""
        ...


class AfterToolHook(Protocol):
    async def after(self, ctx: ToolContext, tool_name: str, result: ToolResult) -> None:
        """Observe a completed call."""
        ...


class ToolErrorHook(Protocol):
    async def on_error(self, ctx: ToolContext, tool_name: str, error: Exception) -> None:
        """Observe a failed call."""
        ...
