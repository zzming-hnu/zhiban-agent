from redis.asyncio import Redis


class RedisResource:
    """Lazy Redis client; construction performs no network I/O."""

    def __init__(self, url: str | None) -> None:
        self._client: Redis | None = None
        if url:
            self._client = Redis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )

    @property
    def configured(self) -> bool:
        return self._client is not None

    @property
    def client(self) -> Redis | None:
        return self._client

    async def ping(self) -> None:
        if self._client is None:
            raise RuntimeError("redis is not configured")
        await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
