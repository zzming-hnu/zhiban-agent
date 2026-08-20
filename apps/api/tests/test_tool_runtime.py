"""Unit tests for the tool runtime (spec, registry, executor, idempotency, hooks)."""

import asyncio
import uuid

import pytest
from pydantic import BaseModel, Field
from zhiban.tools.base import ToolContext, ToolResult
from zhiban.tools.executor import ToolExecutor
from zhiban.tools.ids import canonical_args, operation_key
from zhiban.tools.registry import ToolRegistry
from zhiban.tools.spec import ToolSpec


class _Input(BaseModel):
    model_config = {"extra": "forbid"}

    query: str = Field(min_length=1, max_length=100)
    limit: int = Field(default=3, ge=1, le=10)


class _EchoTool:
    def __init__(self, *, delay: float = 0.0, fail: bool = False) -> None:
        self.spec = ToolSpec(
            name="echo",
            description="echo the query",
            input_model=_Input,
            permission="read",
            timeout_seconds=1.0,
            idempotency="none",
            retry_policy="never",
        )
        self._delay = delay
        self._fail = fail

    async def execute(self, ctx: ToolContext, args: _Input) -> ToolResult:
        if self._fail:
            raise RuntimeError("boom")
        if self._delay:
            await asyncio.sleep(self._delay)
        return ToolResult(ok=True, data={"echo": args.query}, summary=args.query)


class _SlowTool(_EchoTool):
    def __init__(self) -> None:
        super().__init__(delay=5.0)
        self.spec = ToolSpec(
            name="slow",
            description="slow tool",
            input_model=_Input,
            permission="read",
            timeout_seconds=0.1,
            idempotency="none",
            retry_policy="never",
        )


def _ctx() -> ToolContext:
    return ToolContext(user_id=uuid.uuid4(), run_id=uuid.uuid4())


# --- spec / registry ---


def test_registry_rejects_duplicate_name() -> None:
    registry = ToolRegistry()
    registry.register(_EchoTool())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_EchoTool())


def test_registry_generates_openai_schema() -> None:
    registry = ToolRegistry()
    registry.register(_EchoTool())
    schemas = registry.openai_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "echo"
    assert "query" in schemas[0]["function"]["parameters"]["properties"]


# --- executor ---


@pytest.mark.asyncio
async def test_executor_validates_and_executes() -> None:
    executor = ToolExecutor()
    result = await executor.execute(_EchoTool(), _ctx(), {"query": "你好"})
    assert result.ok is True
    assert result.data == {"echo": "你好"}


@pytest.mark.asyncio
async def test_executor_rejects_invalid_args() -> None:
    executor = ToolExecutor()
    result = await executor.execute(_EchoTool(), _ctx(), {"query": ""})
    assert result.ok is False
    assert result.error_code == "tool_invalid_argument"


@pytest.mark.asyncio
async def test_executor_times_out() -> None:
    executor = ToolExecutor()
    result = await executor.execute(_SlowTool(), _ctx(), {"query": "x"})
    assert result.ok is False
    assert result.error_code == "tool_timeout"


@pytest.mark.asyncio
async def test_executor_catches_execution_error() -> None:
    executor = ToolExecutor()
    result = await executor.execute(_EchoTool(fail=True), _ctx(), {"query": "x"})
    assert result.ok is False
    assert result.error_code == "execution_error"


@pytest.mark.asyncio
async def test_executor_rejects_sensitive_without_confirmation() -> None:
    tool = _EchoTool()
    tool.spec = ToolSpec(
        name="echo",
        description="echo",
        input_model=_Input,
        permission="sensitive",
    )
    result = await ToolExecutor().execute(tool, _ctx(), {"query": "x"})
    assert result.ok is False
    assert result.error_code == "tool_confirmation_required"


# --- idempotency ---


def test_canonical_args_ignores_key_order() -> None:
    assert canonical_args({"a": 1, "b": 2}) == canonical_args({"b": 2, "a": 1})


def test_operation_key_is_stable_and_scoped() -> None:
    user = uuid.uuid4()
    run = uuid.uuid4()
    k1 = operation_key(user_id=user, run_id=run, tool_name="t", args={"a": 1})
    k2 = operation_key(user_id=user, run_id=run, tool_name="t", args={"a": 1})
    k3 = operation_key(user_id=user, run_id=run, tool_name="t", args={"a": 2})
    assert k1 == k2
    assert k1 != k3


# --- hooks ---


@pytest.mark.asyncio
async def test_hooks_run_in_order_and_isolated() -> None:
    events: list[str] = []

    class Before:
        async def before(self, ctx: ToolContext, tool_name: str, args: BaseModel) -> None:
            events.append(f"before:{tool_name}")

    class After:
        async def after(self, ctx: ToolContext, tool_name: str, result: ToolResult) -> None:
            events.append(f"after:{tool_name}")

    class BrokenBefore:
        async def before(self, ctx: ToolContext, tool_name: str, args: BaseModel) -> None:
            raise RuntimeError("broken")

    executor = ToolExecutor(
        before_hooks=[Before(), BrokenBefore()],
        after_hooks=[After()],
    )
    result = await executor.execute(_EchoTool(), _ctx(), {"query": "x"})
    # The broken hook rejects the call (isolation), so the tool is not executed.
    assert result.ok is False
    assert "before:echo" in events
