from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class DatabaseResource:
    """Lazy async SQLAlchemy engine; construction performs no network I/O."""

    def __init__(self, url: str | None) -> None:
        self._engine: AsyncEngine | None = None
        if url:
            self._engine = create_async_engine(
                url,
                pool_pre_ping=True,
                pool_recycle=1800,
            )

    @property
    def configured(self) -> bool:
        return self._engine is not None

    async def ping(self) -> None:
        if self._engine is None:
            raise RuntimeError("database is not configured")
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def current_revision(self) -> str | None:
        if self._engine is None:
            raise RuntimeError("database is not configured")
        async with self._engine.connect() as connection:
            result = await connection.execute(text("SELECT version_num FROM alembic_version"))
            return result.scalar_one_or_none()

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
