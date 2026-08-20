from pathlib import Path

from zhiban.core.resources import migration_head


def test_alembic_has_single_head() -> None:
    head = migration_head("apps/api/alembic.ini")
    assert head is not None
    assert head  # non-empty single head identifier


def test_initial_migration_enables_vector_without_dropping_shared_extension() -> None:
    migration = Path("apps/api/migrations/versions/20260817_0001_enable_pgvector.py").read_text(
        encoding="utf-8"
    )

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "DROP EXTENSION" not in migration
