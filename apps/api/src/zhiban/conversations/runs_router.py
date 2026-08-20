"""SSE run stream endpoint (two-phase chat's second step)."""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.agent.compaction import build_context_with_compaction
from zhiban.agent.context import ContextManager
from zhiban.agent.events import RUN_SNAPSHOT, AgentEvent
from zhiban.agent.orchestrator import run_agent_stream
from zhiban.agent.router import route
from zhiban.agent.subagent import SubAgentContext
from zhiban.agent.subagents.memory_agent import MemoryAgent
from zhiban.agent.subagents.search_agent import SearchAgent
from zhiban.agent.subagents.task_agent import TaskAgent
from zhiban.agent.title import generate_title
from zhiban.auth.dependencies import PrincipalDep
from zhiban.conversations.runs import EventBuffer, RunRepository, build_snapshot
from zhiban.conversations.stream import sse_event
from zhiban.core.config import Settings, get_settings
from zhiban.core.token_budget import build_token_budget
from zhiban.db.models import AgentRun, Conversation, Message
from zhiban.db.session import create_session_factory
from zhiban.llm.base import ChatMessage, LLMAdapter
from zhiban.llm.embedding import EmbeddingAdapter
from zhiban.llm.factory import create_embedding_adapter, create_llm_adapter, create_summary_adapter
from zhiban.tools.executor import ToolExecutor
from zhiban.tools.registry import ToolRegistry, create_registry
from zhiban.tools.search import create_search_adapter

router = APIRouter(prefix="/runs", tags=["runs"])


async def _get_session(request: Request) -> AsyncIterator[AsyncSession]:
    resources = request.app.state.resources
    factory = create_session_factory(resources.database)
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(_get_session)]


def _parse_last_event_id(header: str | None) -> tuple[uuid.UUID | None, int]:
    """Parse `{run_id}:{seq}` from the Last-Event-ID header."""
    if not header:
        return None, 0
    if ":" in header:
        run_part, seq_part = header.rsplit(":", 1)
        try:
            run_id = uuid.UUID(run_part)
            seq = int(seq_part)
            return run_id, seq
        except (ValueError, TypeError):
            return None, 0
    return None, 0


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: uuid.UUID,
    principal: PrincipalDep,
    request: Request,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    run_repo = RunRepository(session)
    run = await run_repo.get_or_404(user_id=principal.user_id, run_id=run_id)

    resources = request.app.state.resources
    redis_client = resources.redis.client if resources.redis.configured else None
    buffer = EventBuffer(redis_client)

    last_event_id = request.headers.get("last-event-id")
    _, after_seq = _parse_last_event_id(last_event_id)

    async def event_generator() -> AsyncIterator[str]:
        # Reconnect: replay buffered events after the client's last seen seq.
        if after_seq > 0:
            buffered = await buffer.events_after(run_id, after_seq)
            if buffered:
                for event in buffered:
                    yield sse_event(event)
                if buffered[-1].is_terminal:
                    return
            else:
                # Buffer missing -> return a snapshot, never replay side effects.
                snapshot = await build_snapshot(session, user_id=principal.user_id, run_id=run_id)
                yield sse_event(
                    AgentEvent(
                        type=RUN_SNAPSHOT,
                        seq=after_seq + 1,
                        run_id=run_id,
                        data={
                            "status": snapshot.status,
                            "assistant_content": snapshot.assistant_content,
                            "error_code": snapshot.error_code,
                        },
                    )
                )
                return

        # If the run is already terminal, return its snapshot state.
        if run.status in ("completed", "failed", "cancelled"):
            snapshot = await build_snapshot(session, user_id=principal.user_id, run_id=run_id)
            yield sse_event(
                AgentEvent(
                    type=RUN_SNAPSHOT,
                    seq=after_seq + 1,
                    run_id=run_id,
                    data={
                        "status": snapshot.status,
                        "assistant_content": snapshot.assistant_content,
                        "error_code": snapshot.error_code,
                    },
                )
            )
            return

        # Otherwise execute the agent and stream events.
        llm = create_llm_adapter(settings, model=run.model)
        summary_llm = create_summary_adapter(settings, model=run.model)
        embedding = create_embedding_adapter(settings)
        search = create_search_adapter(settings)
        # When sub-agent routing is enabled, the main agent keeps only lightweight
        # read-only tools (current_time, summary). Memory/task/search tools are
        # owned by their respective sub-agents, achieving responsibility separation.
        registry = create_registry(
            summary_llm=summary_llm,
            search=search,
            include_search=not settings.agent_use_subagent,
        )
        # Build the memory service (shared by main agent injection and MemoryAgent).
        memory_service = _build_memory_service(session, principal.user_id, embedding)
        if not settings.agent_use_subagent:
            # Legacy mode: main agent owns all tools directly.
            _register_todo_tools(registry, session)
            _register_memory_tools(registry, session, principal.user_id, embedding)
        executor = ToolExecutor()
        budget = build_token_budget(
            settings.model_context_window,
            output_reserve=settings.output_reserve_tokens,
            summary_budget=settings.summary_budget_tokens,
            tool_results_budget=settings.tool_results_budget_tokens,
        )
        context_manager = ContextManager(budget)

        compacted = await build_context_with_compaction(
            session,
            user_id=principal.user_id,
            conversation_id=run.conversation_id,
            current_user_message_id=run.user_message_id,
            settings=settings,
            summary_llm=summary_llm,
            context_manager=context_manager,
        )
        messages = compacted.messages

        # Inject retrieved memories after the system prompt.
        messages = await _inject_retrieved_memories(
            session, messages, principal.user_id, run.user_message_id, embedding
        )

        # Fetch the current user message content (for routing + delegation).
        user_content = await _load_user_content(session, run.user_message_id)

        await run_repo.mark_running(run)
        await session.commit()

        full_text = ""
        try:
            # Route: the main agent decides whether to delegate to a sub-agent.
            delegated = False
            if settings.agent_use_subagent:
                decision = await route(llm, user_content)
                sub_agent = _build_subagent(
                    decision.target,
                    llm=llm,
                    session=session,
                    user_id=principal.user_id,
                    memory_service=memory_service,
                    search=search,
                )
                if sub_agent is not None:
                    delegated = True
                    sub_result = await sub_agent.run(
                        SubAgentContext(
                            user_id=principal.user_id,
                            conversation_id=run.conversation_id,
                            run_id=run_id,
                            user_input=user_content,
                        )
                    )
                    # Stream a final answer composed from the sub-agent's summary.
                    async for event in _stream_subagent_answer(
                        llm, settings, run_id, user_content, sub_result
                    ):
                        if event.type == "message.delta":
                            full_text += event.data.get("delta", "")
                        elif event.type == "message.completed":
                            full_text = event.data.get("content", full_text)
                        await buffer.append(run_id, event)
                        yield sse_event(event)

            if not delegated:
                async for event in run_agent_stream(
                    llm,
                    settings,
                    registry,
                    executor,
                    context_manager,
                    run_id=run_id,
                    user_id=principal.user_id,
                    conversation_id=run.conversation_id,
                    messages=messages,
                ):
                    if event.type == "message.delta":
                        full_text += event.data.get("delta", "")
                    elif event.type == "message.completed":
                        full_text = event.data.get("content", full_text)
                    await buffer.append(run_id, event)
                    yield sse_event(event)

            # Persist final assistant message content and terminal run state.
            await _finalize_run(session, run_repo, run, full_text)

            # Auto-generate the conversation title from the first user message.
            await _maybe_generate_title(
                session, llm, run.conversation_id, principal.user_id, run.user_message_id
            )

            # Enqueue an async memory-extraction job for this run.
            await _enqueue_memory_extraction(
                session, run.conversation_id, principal.user_id, run.user_message_id
            )
        except Exception as exc:  # noqa: BLE001 - boundary
            await run_repo.mark_failed(run, type(exc).__name__)
            await session.commit()
            # Emit a terminal failure event so the client does not hang.
            failed_event = AgentEvent(
                type="run.failed",
                seq=after_seq + 1,
                run_id=run_id,
                error={"code": type(exc).__name__, "message": "生成回复时遇到问题，请重试"},
            )
            await buffer.append(run_id, failed_event)
            yield sse_event(failed_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _inject_retrieved_memories(
    session: AsyncSession,
    messages: list[ChatMessage],
    user_id: uuid.UUID,
    user_message_id: uuid.UUID,
    embedding: EmbeddingAdapter | None = None,
) -> list[ChatMessage]:
    """Inject memories into the context.

    Two layers, mirroring the source_kind split:

    - **Explicit memories** (user explicitly asked to remember) are the user's
      stable "core memories" and are injected on EVERY query (like Xiao Q's
      ``user.core_memories``), so the agent always knows basic info/preferences.
    - **Implicit memories** (auto-extracted) are retrieved on demand by
      relevance to the current query.
    """
    from zhiban.memory.search import search_memories

    user_msg = (
        await session.execute(select(Message).where(Message.id == user_message_id))
    ).scalar_one_or_none()
    if user_msg is None:
        return messages

    # Layer 1: explicit core memories, always injected.
    core_lines = await _load_explicit_memories(session, user_id)

    # Layer 2: implicit memories, retrieved by relevance (semantic if embedding
    # is available, otherwise lexical fallback).
    retrieved_lines: list[str] = []
    try:
        query_embedding = None
        if embedding is not None:
            try:
                query_embedding = await embedding.embed(user_msg.content)
            except Exception:  # noqa: BLE001 - embedding is best-effort
                query_embedding = None
        results = await search_memories(
            session, user_id=user_id, query=user_msg.content, embedding=query_embedding
        )
        # Filter out explicit memories (already injected as core) to avoid dupes.
        for scored in results:
            if scored.memory.source_kind == "explicit":
                continue
            retrieved_lines.append(f"- {scored.memory.content}")
    except Exception:  # noqa: BLE001 - memory retrieval is best-effort
        pass

    if not core_lines and not retrieved_lines:
        return messages

    # Build injected messages.
    injected_msgs: list[ChatMessage] = []
    if core_lines:
        core_msg = ChatMessage(
            role="system",
            content="\n".join(["[用户的核心信息与偏好（务必遵循）]"] + core_lines),
        )
        injected_msgs.append(core_msg)
    if retrieved_lines:
        recalled_msg = ChatMessage(
            role="system",
            content="\n".join(["[与当前问题相关的用户记忆（仅供参考）]"] + retrieved_lines),
        )
        injected_msgs.append(recalled_msg)

    # Insert after the first system message.
    injected: list[ChatMessage] = []
    inserted = False
    for msg in messages:
        injected.append(msg)
        if not inserted and msg.role == "system":
            for mem_msg in injected_msgs:
                injected.append(mem_msg)
            inserted = True
    if not inserted:
        injected = injected_msgs + injected
    return injected


async def _load_explicit_memories(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Load the user's explicit (core) memories for always-on injection."""
    from zhiban.db.models import Memory

    result = await session.execute(
        select(Memory).where(
            Memory.user_id == user_id,
            Memory.source_kind == "explicit",
            Memory.status == "active",
            Memory.deleted_at.is_(None),
        )
    )
    lines: list[str] = []
    for memory in result.scalars():
        lines.append(f"- {memory.content}")
    return lines


async def _finalize_run(
    session: AsyncSession,
    run_repo: RunRepository,
    run: AgentRun,
    full_text: str,
) -> None:
    """Persist the assistant message content and mark the run completed."""
    result = await session.execute(select(Message).where(Message.id == run.assistant_message_id))
    assistant_msg = result.scalar_one_or_none()
    if assistant_msg is not None:
        assistant_msg.content = full_text
        assistant_msg.status = "completed"
    await run_repo.mark_completed(run)
    await session.commit()


async def _maybe_generate_title(
    session: AsyncSession,
    llm: LLMAdapter,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    user_message_id: uuid.UUID,
) -> None:
    """Generate a title for a conversation's first user message, best-effort.

    Only runs when this is the conversation's first user message and the
    title is still the default, so it never overwrites a user-edited title.
    """
    conv = (
        await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.status != "deleted",
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        return
    if conv.title not in ("", "新对话"):
        return

    # Count user messages in this conversation.
    user_msg_count = (
        await session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.user_id == user_id,
                Message.role == "user",
                Message.deleted_at.is_(None),
            )
        )
    ).scalars()
    if sum(1 for _ in user_msg_count) > 1:
        return

    # Fetch the first user message content.
    user_msg = (
        await session.execute(select(Message).where(Message.id == user_message_id))
    ).scalar_one_or_none()
    if user_msg is None:
        return

    title = await generate_title(llm, user_msg.content)
    if title:
        conv.title = title
        await session.commit()


def _build_memory_service(
    session: AsyncSession, user_id: uuid.UUID, embedding: EmbeddingAdapter | None = None
) -> Any:
    """Build a MemoryService bound to this user's session."""
    from zhiban.memory.service import MemoryService

    return MemoryService(session, embedding=embedding)


def _build_subagent(
    target: str,
    *,
    llm: LLMAdapter,
    session: AsyncSession,
    user_id: uuid.UUID,
    memory_service: Any,
    search: Any,
) -> Any | None:
    """Build the sub-agent for a route target, or None when not delegating.

    Returns None for ``none`` and ``general`` (general is the main agent's own
    direct-answer path) so the orchestrator answers directly.
    """
    if target == "memory":
        return MemoryAgent(memory_service, llm)
    if target == "task":
        from zhiban.todos.service import ReminderService, TodoService

        return TaskAgent(TodoService(session), ReminderService(session), llm)
    if target == "search":
        return SearchAgent(search, llm)
    return None


async def _load_user_content(session: AsyncSession, user_message_id: uuid.UUID) -> str:
    """Load the current user message content (empty string if missing)."""
    result = await session.execute(select(Message).where(Message.id == user_message_id))
    msg = result.scalar_one_or_none()
    return msg.content if msg is not None else ""


async def _stream_subagent_answer(
    llm: LLMAdapter,
    settings: Settings,
    run_id: uuid.UUID,
    user_input: str,
    sub_result: Any,
) -> AsyncIterator[AgentEvent]:
    """Compose a final streamed answer from a sub-agent's structured result."""
    from zhiban.agent.events import (
        MESSAGE_COMPLETED,
        MESSAGE_DELTA,
        RUN_COMPLETED,
        RUN_STARTED,
    )

    yield AgentEvent(
        type=RUN_STARTED,
        seq=0,
        run_id=run_id,
        data={"model": llm.model, "delegated": True},
    )
    summary = sub_result.summary if sub_result is not None else "（子代理无结果）"
    compose_prompt = (
        "你是知伴主代理。下面是你委派的子代理完成的结果摘要。\n"
        "请基于这个摘要，结合用户的原始请求，生成一段自然、简洁的中文回复。\n"
        "不要提及「子代理」「路由」等内部概念，直接回答用户。\n\n"
        f"用户请求：{user_input}\n\n子代理结果摘要：{summary}"
    )
    text = ""
    async for chunk in llm.chat_stream([ChatMessage(role="user", content=compose_prompt)]):
        if chunk.delta:
            text += chunk.delta
            yield AgentEvent(
                type=MESSAGE_DELTA,
                seq=0,
                run_id=run_id,
                data={"delta": chunk.delta},
            )
    yield AgentEvent(
        type=MESSAGE_COMPLETED,
        seq=0,
        run_id=run_id,
        data={"content": text},
    )
    yield AgentEvent(
        type=RUN_COMPLETED,
        seq=0,
        run_id=run_id,
        data={"finish_reason": "stop"},
    )


def _register_memory_tools(
    registry: ToolRegistry,
    session: AsyncSession,
    user_id: uuid.UUID,
    embedding: EmbeddingAdapter | None = None,
) -> None:
    """Register memory read/write tools with a service bound to this user."""
    from zhiban.memory.service import MemoryService
    from zhiban.memory.tools import (
        MemoryAddTool,
        MemoryDeleteTool,
        MemoryListTool,
        MemoryUpdateTool,
    )

    service = MemoryService(session, embedding=embedding)
    registry.register(MemoryAddTool(service))
    registry.register(MemoryListTool(service))
    registry.register(MemoryUpdateTool(service))
    registry.register(MemoryDeleteTool(service))


def _register_todo_tools(registry: ToolRegistry, session: AsyncSession) -> None:
    """Register todo and reminder tools bound to the request session."""
    from zhiban.todos.service import ReminderService, TodoService
    from zhiban.todos.tools import (
        ReminderCancelTool,
        ReminderCreateTool,
        TodoCompleteTool,
        TodoCreateTool,
    )

    todo_service = TodoService(session)
    reminder_service = ReminderService(session)
    registry.register(TodoCreateTool(todo_service))
    registry.register(TodoCompleteTool(todo_service))
    registry.register(ReminderCreateTool(reminder_service))
    registry.register(ReminderCancelTool(reminder_service))


async def _enqueue_memory_extraction(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    user_message_id: uuid.UUID,
) -> None:
    """Enqueue an async memory-extraction job for the just-finished run."""
    from zhiban.workers.jobs import enqueue_job

    await enqueue_job(
        session,
        user_id=user_id,
        job_type="memory.extract",
        payload={
            "conversation_id": str(conversation_id),
            "user_message_id": str(user_message_id),
        },
        idempotency_key=f"memextract:{user_message_id}",
    )
    await session.commit()
