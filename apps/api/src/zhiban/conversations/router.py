"""Conversation and message CRUD endpoints."""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.auth.dependencies import PrincipalDep
from zhiban.conversations.schemas import (
    ConversationPage,
    ConversationView,
    CreateConversationRequest,
    CreateMessageRequest,
    MessagePage,
    MessageView,
    RunAccepted,
    UpdateConversationRequest,
)
from zhiban.conversations.service import ConversationService
from zhiban.core.config import Settings, get_settings
from zhiban.core.idempotency import IDEMPOTENCY_HEADER, Idempotency
from zhiban.core.pagination import decode_cursor, encode_cursor
from zhiban.db.models import Conversation, Message
from zhiban.db.session import create_session_factory
from zhiban.llm.factory import available_models

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _get_session(request: Request) -> AsyncIterator[AsyncSession]:
    resources = request.app.state.resources
    factory = create_session_factory(resources.database)
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(_get_session)]


def _conv_view(conv: Conversation) -> ConversationView:
    return ConversationView(
        id=str(conv.id),
        title=conv.title,
        status=conv.status,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


def _msg_view(msg: Message) -> MessageView:
    return MessageView(
        id=str(msg.id),
        role=msg.role,
        content=msg.content,
        status=msg.status,
        created_at=msg.created_at.isoformat(),
    )


@router.post("", response_model=ConversationView, status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    principal: PrincipalDep,
    session: DbSession,
    request: Request,
) -> ConversationView:
    idem = Idempotency(
        session,
        user_id=principal.user_id,
        method="POST",
        route="/conversations",
        key=request.headers.get(IDEMPOTENCY_HEADER),
    )
    idem.set_body(await request.body())
    outcome = await idem.begin()
    if outcome.action == "replay" and outcome.record is not None:
        cached = outcome.record.response_body
        if cached is not None:
            return ConversationView(**cached)

    service = ConversationService(session)
    conv = await service.create(user_id=principal.user_id, title=body.title)
    view = _conv_view(conv)
    await idem.finish(201, view.model_dump())
    await session.commit()
    return view


@router.get("", response_model=ConversationPage)
async def list_conversations(
    principal: PrincipalDep,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> ConversationPage:
    decoded = decode_cursor(cursor, settings.session_secret.get_secret_value()) if cursor else None
    service = ConversationService(session)
    items, has_more = await service.list_conversations(
        user_id=principal.user_id, cursor=decoded, limit=limit
    )
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(
            last.updated_at, last.id, settings.session_secret.get_secret_value()
        )
    return ConversationPage(
        data=[_conv_view(c) for c in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{conversation_id}", response_model=ConversationView)
async def get_conversation(
    conversation_id: uuid.UUID,
    principal: PrincipalDep,
    session: DbSession,
) -> ConversationView:
    service = ConversationService(session)
    conv = await service.get_or_404(user_id=principal.user_id, conversation_id=conversation_id)
    return _conv_view(conv)


@router.patch("/{conversation_id}", response_model=ConversationView)
async def rename_conversation(
    conversation_id: uuid.UUID,
    body: UpdateConversationRequest,
    principal: PrincipalDep,
    session: DbSession,
) -> ConversationView:
    service = ConversationService(session)
    conv = await service.rename(
        user_id=principal.user_id, conversation_id=conversation_id, title=body.title
    )
    await session.commit()
    return _conv_view(conv)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    principal: PrincipalDep,
    session: DbSession,
) -> Response:
    service = ConversationService(session)
    await service.delete(user_id=principal.user_id, conversation_id=conversation_id)
    await session.commit()
    return Response(status_code=204)


@router.get("/{conversation_id}/messages", response_model=MessagePage)
async def list_messages(
    conversation_id: uuid.UUID,
    principal: PrincipalDep,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> MessagePage:
    decoded = decode_cursor(cursor, settings.session_secret.get_secret_value()) if cursor else None
    service = ConversationService(session)
    items, has_more = await service.list_messages(
        user_id=principal.user_id,
        conversation_id=conversation_id,
        cursor=decoded,
        limit=limit,
    )
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(
            last.created_at, last.id, settings.session_secret.get_secret_value()
        )
    return MessagePage(
        data=[_msg_view(m) for m in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=RunAccepted,
    status_code=202,
)
async def create_message(
    conversation_id: uuid.UUID,
    body: CreateMessageRequest,
    principal: PrincipalDep,
    session: DbSession,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RunAccepted:
    idem = Idempotency(
        session,
        user_id=principal.user_id,
        method="POST",
        route=f"/conversations/{conversation_id}/messages",
        key=request.headers.get(IDEMPOTENCY_HEADER),
    )
    idem.set_body(await request.body())
    outcome = await idem.begin()
    if outcome.action == "replay" and outcome.record is not None:
        cached = outcome.record.response_body
        if cached is not None:
            return RunAccepted(**cached)

    service = ConversationService(session)
    # Resolve the requested model against the configured allow-list; fall back
    # to the default model when the client omits it or requests an unknown one.
    model = body.model
    if model is None or model not in available_models(settings):
        model = settings.llm_model
    user_msg, assistant_msg, run = await service.start_run(
        user_id=principal.user_id,
        conversation_id=conversation_id,
        content=body.content,
        client_message_id=body.client_message_id,
        model=model,
    )
    await session.commit()

    view = RunAccepted(
        message_id=str(user_msg.id),
        assistant_message_id=str(assistant_msg.id),
        run_id=str(run.id),
        status=run.status,
        stream_url=f"/runs/{run.id}/stream",
    )
    await idem.finish(202, view.model_dump())
    await session.commit()
    return view
