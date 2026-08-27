"""Memory tools exposed to the agent (add / list / update / delete)."""

from typing import Literal

from pydantic import BaseModel, Field
from zhiban.memory.service import MemoryService
from zhiban.memory.types import resolve_category
from zhiban.memory.validator import value_looks_malformed
from zhiban.tools.base import ToolContext, ToolResult
from zhiban.tools.spec import ToolSpec


class AddMemoryInput(BaseModel):
    model_config = {"extra": "forbid"}

    memory_type: Literal[
        "identity", "preference", "habit", "person", "event", "task", "temporary", "communication"
    ] = Field(
        description=(
            "记忆类型（注意：这不是 category，不要填 basic_info/communication_* 这类值）："
            "identity/preference/habit/person/event/task/temporary/communication"
        )
    )
    category: Literal[
        "basic_info", "communication_taboo", "communication_preference", "other"
    ] = Field(
        default="other",
        description="用户分类：basic_info/communication_taboo/communication_preference/other",
    )
    subject: str = Field(min_length=1, max_length=80)
    predicate: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)


class ListMemoryInput(BaseModel):
    model_config = {"extra": "forbid"}

    limit: int = Field(default=20, ge=1, le=100)


class UpdateMemoryInput(BaseModel):
    model_config = {"extra": "forbid"}

    memory_id: str = Field(min_length=1, max_length=64)
    value: str | None = Field(default=None, max_length=500)
    category: str | None = Field(
        default=None,
        description="用户分类：basic_info/communication_taboo/communication_preference/other",
    )


class DeleteMemoryInput(BaseModel):
    model_config = {"extra": "forbid"}

    memory_id: str = Field(min_length=1, max_length=64)


class MemoryAddTool:
    spec = ToolSpec(
        name="memory.add",
        description=(
            "保存一条用户记忆。当用户明确要求记住某件事时直接调用本工具，"
            "不要询问确认、不要口头承诺。"
        ),
        input_model=AddMemoryInput,
        permission="write",
        timeout_seconds=5.0,
        idempotency="required",
        retry_policy="never",
    )

    def __init__(self, service: MemoryService) -> None:
        self._service = service

    async def execute(self, ctx: ToolContext, args: AddMemoryInput) -> ToolResult:
        from zhiban.db.models import Memory
        from zhiban.memory.ids import conflict_key, memory_fingerprint
        from zhiban.memory.normalize import normalize_text
        from zhiban.memory.types import MemoryStatus, SourceKind

        # Reject malformed values early — same check the implicit extractor
        # path uses, so explicit tool calls cannot bypass it.
        if value_looks_malformed(
            value=args.value, subject=args.subject, predicate=args.predicate
        ):
            return ToolResult(
                ok=False,
                summary="value 不能包含 subject 或 predicate 的重复拼接，请只填纯值",
                error_code="malformed_value",
            )

        fingerprint = memory_fingerprint(
            user_id=ctx.user_id,
            memory_type=args.memory_type,
            subject=args.subject,
            predicate=args.predicate,
            value=args.value,
        )
        ckey = conflict_key(
            user_id=ctx.user_id,
            memory_type=args.memory_type,
            subject=args.subject,
            predicate=args.predicate,
        )
        # Deterministic category resolution (identity/person/event -> basic_info).
        category = resolve_category(args.memory_type, args.category)
        content = f"{args.subject} {args.predicate} {args.value}".strip()
        memory = Memory(
            user_id=ctx.user_id,
            memory_type=args.memory_type,
            category=category,
            subject=normalize_text(args.subject),
            predicate=normalize_text(args.predicate),
            value=normalize_text(args.value),
            content=content,
            source_kind=SourceKind.explicit,
            status=MemoryStatus.active,
            confidence=1.0,
            importance=0.5,
            fingerprint=fingerprint,
            conflict_key=ckey,
            embedding=await self._service._embed(content),
            source_message_ids=[],
            evidence_quote="",
        )
        await self._service.repo.add(memory)
        await self._service._session.commit()
        return ToolResult(
            ok=True,
            data={"memory_id": str(memory.id)},
            summary=f"已记住：{memory.content}",
        )


class MemoryListTool:
    spec = ToolSpec(
        name="memory.list",
        description=(
            "列出用户已保存的记忆，每条返回 id（用于后续 update/delete）、type、category、content。"
        ),
        input_model=ListMemoryInput,
        permission="read",
        timeout_seconds=5.0,
        idempotency="optional",
        retry_policy="never",
    )

    def __init__(self, service: MemoryService) -> None:
        self._service = service

    async def execute(self, ctx: ToolContext, args: ListMemoryInput) -> ToolResult:
        memories = await self._service.list_memories(user_id=ctx.user_id, limit=args.limit)
        data = [
            {"id": str(m.id), "type": m.memory_type, "category": m.category, "content": m.content}
            for m in memories
        ]
        return ToolResult(
            ok=True,
            data=data,
            summary=f"共有 {len(data)} 条记忆",
        )


class MemoryUpdateTool:
    spec = ToolSpec(
        name="memory.update",
        description=(
            "修改一条用户记忆的内容或分类。当用户纠正或修改已保存的记忆时，"
            "先用 memory.list 找到对应记忆的 id，再直接调用本工具，不要询问确认。"
        ),
        input_model=UpdateMemoryInput,
        permission="write",
        timeout_seconds=5.0,
        idempotency="required",
        retry_policy="never",
    )

    def __init__(self, service: MemoryService) -> None:
        self._service = service

    async def execute(self, ctx: ToolContext, args: UpdateMemoryInput) -> ToolResult:
        try:
            memory_id = __import__("uuid").UUID(args.memory_id)
        except ValueError:
            return ToolResult(
                ok=False, summary="记忆 ID 不合法", error_code="tool_invalid_argument"
            )
        memory = await self._service.update_value(
            user_id=ctx.user_id,
            memory_id=memory_id,
            value=args.value,
            category=args.category,
            importance=None,
        )
        if memory is None:
            return ToolResult(ok=False, summary="记忆不存在", error_code="not_found")
        return ToolResult(ok=True, summary=f"已更新记忆：{memory.content}")


class MemoryDeleteTool:
    spec = ToolSpec(
        name="memory.delete",
        description=(
            "删除一条用户记忆。当用户明确要求忘记、删除某件事时，"
            "先用 memory.list 找到对应记忆的 id，再直接调用本工具，不要询问确认。"
            "用户要求删除全部/所有记忆时，先 memory.list 再逐条删除。"
        ),
        input_model=DeleteMemoryInput,
        permission="write",
        timeout_seconds=5.0,
        idempotency="required",
        retry_policy="never",
    )

    def __init__(self, service: MemoryService) -> None:
        self._service = service

    async def execute(self, ctx: ToolContext, args: DeleteMemoryInput) -> ToolResult:
        try:
            memory_id = __import__("uuid").UUID(args.memory_id)
        except ValueError:
            return ToolResult(
                ok=False, summary="记忆 ID 不合法", error_code="tool_invalid_argument"
            )
        deleted = await self._service.soft_delete(user_id=ctx.user_id, memory_id=memory_id)
        if not deleted:
            return ToolResult(ok=False, summary="记忆不存在", error_code="not_found")
        return ToolResult(ok=True, summary="已删除记忆")


class ConsolidateMemoryInput(BaseModel):
    model_config = {"extra": "forbid"}


class MemoryConsolidateTool:
    """User-initiated memory consolidation: dedupe + resolve conflicts.

    Enqueues a background ``memory.consolidate`` job (the same path the
    auto-trigger uses), so the interaction stays fast while the worker tidies
    up in the background.
    """

    spec = ToolSpec(
        name="memory.consolidate",
        description=(
            "整理用户记忆：识别并去除冗余、消解矛盾的记忆。"
            "当用户说「整理一下我的记忆」「记忆太乱了帮我整理」等时调用。"
        ),
        input_model=ConsolidateMemoryInput,
        permission="write",
        timeout_seconds=5.0,
        idempotency="optional",
        retry_policy="never",
    )

    def __init__(self, service: MemoryService) -> None:
        self._service = service

    async def execute(self, ctx: ToolContext, args: ConsolidateMemoryInput) -> ToolResult:
        from zhiban.workers.jobs import enqueue_job

        await enqueue_job(
            self._service._session,
            user_id=ctx.user_id,
            job_type="memory.consolidate",
            payload={},
            idempotency_key=f"memconsolidate:{ctx.user_id}",
        )
        await self._service._session.commit()
        return ToolResult(ok=True, summary="已开始整理记忆，稍后完成")
