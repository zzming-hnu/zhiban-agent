import asyncio
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import SecretStr

from zhiban.core.config import Settings
from zhiban.db.database import DatabaseResource
from zhiban.db.redis import RedisResource


def reveal(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def migration_head(config_path: str) -> str:
    path = Path(config_path)
    if not path.is_file():
        raise RuntimeError(f"Alembic config does not exist: {config_path}")
    config = Config(str(path))
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    if head is None:
        raise RuntimeError("Alembic has no migration head")
    return head


@dataclass(slots=True)
class AppResources:
    database: DatabaseResource
    redis: RedisResource
    migration_head: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "AppResources":
        return cls(
            database=DatabaseResource(reveal(settings.database_url)),
            redis=RedisResource(reveal(settings.redis_url)),
            migration_head=migration_head(settings.alembic_config_path),
        )

    async def close(self) -> None:
        await asyncio.gather(
            self.database.close(),
            self.redis.close(),
        )
