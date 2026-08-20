"""Auth domain logic: register, login, rotate, logout, revoke."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.auth.repository import SessionRepository, UserRepository
from zhiban.auth.security import (
    generate_session_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from zhiban.core.errors import AppError
from zhiban.db.models import AuthSession, User


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: User
    session: AuthSession
    session_token: str


def _session_token_expired(record: AuthSession) -> bool:
    return record.expires_at <= datetime.now(UTC)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)

    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        user_agent_hash: str | None = None,
        ip_prefix: str | None = None,
    ) -> AuthResult:
        existing = await self.users.get_by_email(email)
        if existing is not None:
            raise AppError(code="email_taken", message="该邮箱已注册", status_code=409)

        user = await self.users.create(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
        )
        return await self._issue_session(
            user=user,
            user_agent_hash=user_agent_hash,
            ip_prefix=ip_prefix,
        )

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent_hash: str | None = None,
        ip_prefix: str | None = None,
    ) -> AuthResult:
        user = await self.users.get_by_email(email)
        # Unified failure: do not reveal whether the email exists.
        if user is None or not verify_password(password, user.password_hash):
            raise AppError(code="invalid_credentials", message="邮箱或密码错误", status_code=401)

        # Lazy re-hash legacy bcrypt hashes to Argon2id on successful login.
        if needs_rehash(user.password_hash):
            await self.users.update_password_hash(user.id, hash_password(password))

        return await self._issue_session(
            user=user,
            user_agent_hash=user_agent_hash,
            ip_prefix=ip_prefix,
        )

    async def rotate(
        self,
        *,
        refresh_token_hash: str,
        user_agent_hash: str | None = None,
        ip_prefix: str | None = None,
    ) -> AuthResult:
        record = await self.sessions.get_by_token_hash(refresh_token_hash)
        if record is None or record.revoked_at is not None:
            raise AppError(
                code="invalid_session", message="会话已失效，请重新登录", status_code=401
            )
        if _session_token_expired(record):
            raise AppError(
                code="invalid_session", message="会话已过期，请重新登录", status_code=401
            )

        user = await self.users.get_by_id(record.user_id)
        if user is None:
            raise AppError(
                code="invalid_session", message="会话已失效，请重新登录", status_code=401
            )

        # Rotation: revoke the old session and issue a fresh one.
        await self.sessions.revoke(record.id, record.user_id)
        return await self._issue_session(
            user=user,
            user_agent_hash=user_agent_hash,
            ip_prefix=ip_prefix,
        )

    async def logout(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        await self.sessions.revoke(session_id, user_id)

    async def revoke_session(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        revoked = await self.sessions.revoke(session_id, user_id)
        if not revoked:
            raise AppError(code="not_found", message="会话不存在", status_code=404)

    async def _issue_session(
        self,
        *,
        user: User,
        user_agent_hash: str | None,
        ip_prefix: str | None,
    ) -> AuthResult:
        token = generate_session_token()
        record = await self.sessions.create(
            user_id=user.id,
            refresh_token_hash=hash_token(token),
            user_agent_hash=user_agent_hash,
            ip_prefix=ip_prefix,
        )
        return AuthResult(user=user, session=record, session_token=token)
