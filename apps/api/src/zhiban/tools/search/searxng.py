"""SearXNG search adapter (self-hosted meta-search engine)."""

from typing import Any

import httpx2 as httpx

from zhiban.tools.search.base import SearchResult


class SearXNGAdapter:
    """Query a SearXNG instance's JSON API for real web results."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            response = await self._client.get(
                f"{self.base_url}/search",
                params={"q": query, "format": "json"},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        except Exception:  # noqa: BLE001 - search failure is non-fatal
            return []

        results: list[SearchResult] = []
        for item in data.get("results", [])[:max_results]:
            results.append(
                SearchResult(
                    title=item.get("title", "") or "",
                    url=item.get("url", "") or "",
                    snippet=(item.get("content", "") or "")[:500],
                    source=item.get("engine", "") or "web",
                )
            )
        return [r for r in results if r.title and r.url]

    async def aclose(self) -> None:
        await self._client.aclose()
