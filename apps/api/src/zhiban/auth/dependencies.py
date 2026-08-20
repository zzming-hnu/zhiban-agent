"""FastAPI dependencies for extracting the authenticated principal."""

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, Request

from zhiban.auth.principal import Principal
from zhiban.auth.repository import SessionRepository
from zhiban.auth.security import hash_token
from zhiban.auth.service import _session_token_expired
from zhiban.core.errors import AppError
from zhiban.db.models import AuthSession
from zhiban.db.session import create_session_factory

SESSION_COOKIE = "zhiban_session"


async def _resolve_session(
    request: Request, session_token: str | None
) -> tuple[uuid.UUID, AuthSession]:
    if not session_token:
        raise AppError(code="unauthorized", message="请先登录", status_code=401)

    resources = request.app.state.resources
    factory = create_session_factory(resources.database)
    async with factory() as session:
        repo = SessionRepository(session)
        record = await repo.get_by_token_hash(hash_token(session_token))
        if record is None or record.revoked_at is not None:
            raise AppError(code="unauthorized", message="登录已过期，请重新登录", status_code=401)
        if _session_token_expired(record):
            raise AppError(code="unauthorized", message="登录已过期，请重新登录", status_code=401)
        return record.user_id, record


async def get_principal(
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Principal:
    user_id, record = await _resolve_session(request, session_token)
    request.state.user_id = user_id
    request.state.session_id = record.id
    return Principal(user_id=user_id, session_id=record.id)


async def get_current_user_id(
    principal: Annotated[Principal, Depends(get_principal)],
) -> uuid.UUID:
    return principal.user_id


PrincipalDep = Annotated[Principal, Depends(get_principal)]
CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
