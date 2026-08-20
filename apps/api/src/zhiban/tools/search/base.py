"""Search adapter contract shared by mock and real providers."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = ""
    published_at: str | None = None


@runtime_checkable
class SearchAdapter(Protocol):
    async def search(self, query: str, max_results: int) -> list[SearchResult]: ...
