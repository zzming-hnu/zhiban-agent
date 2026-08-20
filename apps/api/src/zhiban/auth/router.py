"""Auth API: register, login, refresh, logout, sessions."""

import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.auth.csrf import CSRF_COOKIE, generate_csrf_token, verify_csrf
from zhiban.auth.dependencies import SESSION_COOKIE, PrincipalDep, get_principal
from zhiban.auth.ratelimit import RateRule, enforce
from zhiban.auth.repository import SessionRepository
from zhiban.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    SessionView,
    UserView,
)
from zhiban.auth.security import hash_token
from zhiban.auth.service import AuthService
from zhiban.core.config import Settings, get_settings
from zhiban.core.errors import AppError
from zhiban.db.models import AuthSession, User
from zhiban.db.session import create_session_factory

router = APIRouter(prefix="/auth", tags=["auth"])


async def _get_session(request: Request) -> AsyncIterator[AsyncSession]:
    resources = request.app.state.resources
    factory = create_session_factory(resources.database)
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(_get_session)]


def _user_agent_hash(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    if not ua:
        return None
    return hashlib.sha256(ua.encode("utf-8")).hexdigest()


def _ip_prefix(request: Request) -> str | None:
    ip = request.client.host if request.client else None
    if not ip:
        return None
    # Keep only a coarse prefix for privacy.
    return ".".join(ip.split(".")[:2]) if "." in ip else ip


def _set_auth_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
        path="/",
    )


def _user_view(user: User) -> UserView:
    return UserView(id=str(user.id), email=user.email, display_name=user.display_name)


def _session_view(session: AuthSession) -> SessionView:
    return SessionView(
        id=str(session.id),
        created_at=session.created_at.isoformat(),
        last_seen_at=session.last_seen_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
        user_agent_hash=session.user_agent_hash,
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: DbSession,
) -> AuthResponse:
    service = AuthService(session)
    result = await service.register(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        user_agent_hash=_user_agent_hash(request),
        ip_prefix=_ip_prefix(request),
    )
    await session.commit()

    csrf_token = generate_csrf_token()
    _set_auth_cookies(response, result.session_token, csrf_token)
    return AuthResponse(user=_user_view(result.user), session=_session_view(result.session))


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: DbSession,
) -> AuthResponse:
    ip = _ip_prefix(request) or "anon"
    await enforce(RateRule(key=f"login:ip:{ip}", limit=5, window_seconds=60), request)
    await enforce(RateRule(key=f"login:ip:{ip}", limit=30, window_seconds=3600), request)

    service = AuthService(session)
    result = await service.login(
        email=body.email,
        password=body.password,
        user_agent_hash=_user_agent_hash(request),
        ip_prefix=_ip_prefix(request),
    )
    await session.commit()

    csrf_token = generate_csrf_token()
    _set_auth_cookies(response, result.session_token, csrf_token)
    return AuthResponse(user=_user_view(result.user), session=_session_view(result.session))


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    verify_csrf(request, settings.web_origin)
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        raise AppError(code="unauthorized", message="请先登录", status_code=401)

    service = AuthService(session)
    result = await service.rotate(
        refresh_token_hash=hash_token(session_token),
        user_agent_hash=_user_agent_hash(request),
        ip_prefix=_ip_prefix(request),
    )
    await session.commit()

    csrf_token = generate_csrf_token()
    _set_auth_cookies(response, result.session_token, csrf_token)
    return AuthResponse(user=_user_view(result.user), session=_session_view(result.session))


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    verify_csrf(request, settings.web_origin)
    principal = await get_principal(request, request.cookies.get(SESSION_COOKIE))
    service = AuthService(session)
    await service.logout(user_id=principal.user_id, session_id=principal.session_id)
    await session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.get("/me", response_model=UserView)
async def me(principal: PrincipalDep, session: DbSession) -> UserView:
    result = await session.execute(select(User).where(User.id == principal.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError(code="not_found", message="用户不存在", status_code=404)
    return _user_view(user)


@router.get("/sessions", response_model=list[SessionView])
async def list_sessions(principal: PrincipalDep, session: DbSession) -> list[SessionView]:
    repo = SessionRepository(session)
    records = await repo.list_active(principal.user_id)
    return [_session_view(r) for r in records]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: uuid.UUID,
    principal: PrincipalDep,
    session: DbSession,
) -> None:
    service = AuthService(session)
    await service.revoke_session(user_id=principal.user_id, session_id=session_id)
    await session.commit()
