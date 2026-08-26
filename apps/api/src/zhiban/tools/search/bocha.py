"""Bocha web search adapter (hosted search API, CN-reachable)."""

from typing import Any

import httpx2 as httpx

from zhiban.tools.search.base import SearchResult

_BOCHA_ENDPOINT = "https://api.bochaai.com/v1/web-search"


class BochaAdapter:
    """Query the Bocha Web Search API for real web results.

    Bocha returns structured results (title/url/snippet/summary) and is
    reachable from CN networks, making it a more reliable fallback than
    self-hosted SearXNG when upstream meta-search engines time out.
    """

    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=timeout)

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "query": query,
            "count": max_results,
            "summary": True,
        }
        try:
            response = await self._client.post(_BOCHA_ENDPOINT, json=payload, headers=headers)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        except Exception:  # noqa: BLE001 - search failure is non-fatal
            return []

        results: list[SearchResult] = []
        # Bocha wraps the search payload under {"code": 200, "data": {...}}.
        payload = data.get("data") if isinstance(data, dict) else data
        web_pages = (payload or {}).get("webPages", {}) or {}
        for item in (web_pages.get("value", []) or [])[:max_results]:
            snippet = item.get("summary") or item.get("snippet") or ""
            results.append(
                SearchResult(
                    title=item.get("name") or item.get("title") or "",
                    url=item.get("url") or "",
                    snippet=(snippet or "")[:500],
                    source=item.get("siteName") or item.get("provider") or "web",
                    published_at=item.get("datePublished"),
                )
            )
        return [r for r in results if r.title and r.url]

    async def aclose(self) -> None:
        await self._client.aclose()
