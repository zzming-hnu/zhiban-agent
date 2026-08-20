"""Repository for users and auth_sessions with explicit user scoping."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.db.models import AuthSession, User

SESSION_TTL_DAYS = 30


def _session_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=SESSION_TTL_DAYS)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, *, email: str, password_hash: str, display_name: str) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=display_name or email.split("@")[0],
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def update_password_hash(self, user_id: uuid.UUID, password_hash: str) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(password_hash=password_hash)
        )


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        refresh_token_hash: str,
        user_agent_hash: str | None,
        ip_prefix: str | None,
    ) -> AuthSession:
        record = AuthSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            user_agent_hash=user_agent_hash,
            ip_prefix=ip_prefix,
            expires_at=_session_expiry(),
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_token_hash(self, refresh_token_hash: str) -> AuthSession | None:
        result = await self._session.execute(
            select(AuthSession).where(AuthSession.refresh_token_hash == refresh_token_hash)
        )
        return result.scalar_one_or_none()

    async def list_active(self, user_id: uuid.UUID) -> list[AuthSession]:
        result = await self._session.execute(
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(UTC),
            )
            .order_by(AuthSession.last_seen_at.desc())
        )
        return list(result.scalars())

    async def revoke(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.id == session_id,
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        return int(result.rowcount) == 1  # type: ignore[attr-defined]

    async def touch_last_seen(self, session_id: uuid.UUID) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id)
            .values(last_seen_at=datetime.now(UTC))
        )
