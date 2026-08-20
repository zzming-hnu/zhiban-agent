"""Async SQLAlchemy session factory, bound to the app's engine."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zhiban.db.database import DatabaseResource


def create_session_factory(database: DatabaseResource) -> async_sessionmaker[AsyncSession]:
    if database._engine is None:
        raise RuntimeError("Cannot create session factory: database not configured")
    return async_sessionmaker(database._engine, expire_on_commit=False)


async def get_db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
