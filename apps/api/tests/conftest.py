"""Shared pytest fixtures.

Integration tests require a real PostgreSQL (with pgvector) and Redis, matching
the local Docker Compose configuration. They are marked with `@pytest.mark.integration`
so the unit suite can run without those dependencies.

Async tests share a session-scoped event loop so the SQLAlchemy async engine's
connections stay on a single loop (avoiding "Event loop is closed").

Integration tests run against a DEDICATED test database (`zhiban_test`), never
the development database, so real user data is never touched or deleted.
"""

import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import httpx2 as httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zhiban.core.config import Settings
from zhiban.core.resources import AppResources
from zhiban.db.models import (
    AgentRun,
    AuthSession,
    Conversation,
    ConversationSummary,
    IdempotencyRecord,
    Job,
    Memory,
    MemoryCandidate,
    Message,
    OutboxEvent,
    Reminder,
    Todo,
    User,
)
from zhiban.db.session import create_session_factory
from zhiban.main import create_app

# Integration tests use a DEDICATED test database so they never touch the
# development database (which holds real, user-created data). The test database
# is a separate PostgreSQL database (`zhiban_test`), not a table suffix.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://zhiban:zhiban_dev_only@localhost:5432/zhiban_test",
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/0")

ROOT_DIR = Path(__file__).resolve().parents[3]


def _run_migrations() -> None:
    """Run Alembic migrations against the test database (idempotent)."""
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(
        [
            str(ROOT_DIR / ".venv" / "bin" / "alembic"),
            "-c",
            "apps/api/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=ROOT_DIR,
        env=env,
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def migrated_test_database() -> None:
    """Ensure the test database is at the latest migration head."""
    _run_migrations()


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        session_secret="integration-test-secret-with-32-chars!",
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
        llm_provider="mock",
        search_provider="mock",
    )


@pytest.fixture(scope="session")
def settings() -> Settings:
    return make_settings()


@pytest.fixture(scope="session")
def resources(settings: Settings, migrated_test_database: None) -> AppResources:
    return AppResources.from_settings(settings)


@pytest.fixture(scope="session")
def session_factory(resources: AppResources) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(resources.database)


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as db:
        yield db


# All business tables in dependency-safe deletion order.
_ALL_TABLES = (
    MemoryCandidate,
    IdempotencyRecord,
    ConversationSummary,
    AgentRun,
    Message,
    Conversation,
    Memory,
    Reminder,
    Todo,
    AuthSession,
    OutboxEvent,
    Job,
    User,
)


async def clean_all_business_tables(session: AsyncSession) -> None:
    """Delete all business rows in FK-safe order (shared by integration tests)."""
    for model in _ALL_TABLES:
        await session.execute(delete(model))
    await session.commit()


@pytest.fixture
async def clean_database(session: AsyncSession) -> AsyncIterator[None]:
    """Clean the test database before and after an integration test."""
    await clean_all_business_tables(session)
    yield
    await clean_all_business_tables(session)


@pytest.fixture
async def client(settings: Settings, resources: AppResources) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings, resources=resources)
    # Set state directly; the lifespan would normally do this on startup.
    app.state.resources = resources
    app.state.settings = settings
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
