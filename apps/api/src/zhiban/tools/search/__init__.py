"""Search adapters and the provider factory."""

from zhiban.core.config import Settings
from zhiban.tools.search.base import SearchAdapter
from zhiban.tools.search.mock import MockSearchAdapter
from zhiban.tools.search.searxng import SearXNGAdapter


def create_search_adapter(settings: Settings) -> SearchAdapter:
    """Create the search adapter based on SEARCH_PROVIDER."""
    if settings.search_provider == "searxng":
        base_url = getattr(settings, "search_base_url", None) or "http://localhost:8888"
        return SearXNGAdapter(base_url=base_url)
    return MockSearchAdapter()
