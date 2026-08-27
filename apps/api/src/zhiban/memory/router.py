"""Memory governance REST API."""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.auth.dependencies import PrincipalDep
from zhiban.core.errors import AppError
from zhiban.db.models import Memory
from zhiban.db.session import create_session_factory
from zhiban.memory.schemas import (
    CreateMemoryRequest,
    MemoryPage,
    MemoryView,
    UpdateMemoryRequest,
)
from zhiban.memory.service import MemoryService

router = APIRouter(prefix="/memories", tags=["memories"])


async def _get_session(request: Request) -> AsyncIterator[AsyncSession]:
    resources = request.app.state.resources
    factory = create_session_factory(resources.database)
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(_get_session)]


def _memory_view(memory: Memory) -> MemoryView:
    return MemoryView(
        id=str(memory.id),
        memory_type=memory.memory_type,
        category=memory.category,
        subject=memory.subject,
        predicate=memory.predicate,
        value=memory.value,
        negated=memory.negated,
        content=memory.content,
        source_kind=memory.source_kind,
        status=memory.status,
        confidence=memory.confidence,
        importance=memory.importance,
        evidence_quote=memory.evidence_quote,
        expires_at=memory.expires_at,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        version=memory.version,
    )


@router.get("", response_model=MemoryPage)
async def list_memories(
    principal: PrincipalDep,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> MemoryPage:
    service = MemoryService(session)
    memories = await service.list_memories(user_id=principal.user_id, limit=limit)
    return MemoryPage(data=[_memory_view(m) for m in memories], has_more=False)


@router.post("", response_model=MemoryView, status_code=201)
async def create_memory(
    body: CreateMemoryRequest,
    principal: PrincipalDep,
    session: DbSession,
) -> MemoryView:
    """Explicitly create a memory (user-initiated, confidence=1.0)."""
    from zhiban.memory.ids import conflict_key, memory_fingerprint
    from zhiban.memory.normalize import normalize_text
    from zhiban.memory.types import MemoryStatus, SourceKind

    fingerprint = memory_fingerprint(
        user_id=principal.user_id,
        memory_type=body.memory_type,
        subject=body.subject,
        predicate=body.predicate,
        value=body.value,
        negated=body.negated,
    )
    ckey = conflict_key(
        user_id=principal.user_id,
        memory_type=body.memory_type,
        subject=body.subject,
        predicate=body.predicate,
    )
    predicate = normalize_text(body.predicate)
    if body.negated and not predicate.startswith("不"):
        predicate = f"不{predicate}"
    memory = Memory(
        user_id=principal.user_id,
        memory_type=body.memory_type,
        category=body.category,
        subject=normalize_text(body.subject),
        predicate=normalize_text(body.predicate),
        value=normalize_text(body.value),
        negated=body.negated,
        content=f"{body.subject} {predicate} {body.value}".strip(),
        source_kind=SourceKind.explicit,
        status=MemoryStatus.active,
        confidence=1.0,
        importance=0.5,
        fingerprint=fingerprint,
        conflict_key=ckey,
        source_message_ids=[],
        evidence_quote="",
    )
    await MemoryService(session).repo.add(memory)
    await session.commit()
    return _memory_view(memory)


@router.get("/{memory_id}", response_model=MemoryView)
async def get_memory(
    memory_id: uuid.UUID,
    principal: PrincipalDep,
    session: DbSession,
) -> MemoryView:
    service = MemoryService(session)
    memory = await service.get_memory(user_id=principal.user_id, memory_id=memory_id)
    if memory is None:
        raise AppError(code="not_found", message="记忆不存在", status_code=404)
    return _memory_view(memory)


@router.patch("/{memory_id}", response_model=MemoryView)
async def update_memory(
    memory_id: uuid.UUID,
    body: UpdateMemoryRequest,
    principal: PrincipalDep,
    session: DbSession,
) -> MemoryView:
    service = MemoryService(session)
    memory = await service.update_value(
        user_id=principal.user_id,
        memory_id=memory_id,
        value=body.value,
        category=body.category,
        importance=body.importance,
    )
    if memory is None:
        raise AppError(code="not_found", message="记忆不存在", status_code=404)
    return _memory_view(memory)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: uuid.UUID,
    principal: PrincipalDep,
    session: DbSession,
) -> Response:
    service = MemoryService(session)
    deleted = await service.soft_delete(user_id=principal.user_id, memory_id=memory_id)
    if not deleted:
        raise AppError(code="not_found", message="记忆不存在", status_code=404)
    return Response(status_code=204)
