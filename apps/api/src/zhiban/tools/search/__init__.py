"""Search adapters and the provider factory."""

from zhiban.core.config import Settings
from zhiban.tools.search.base import SearchAdapter
from zhiban.tools.search.bocha import BochaAdapter
from zhiban.tools.search.mock import MockSearchAdapter
from zhiban.tools.search.searxng import SearXNGAdapter


def create_search_adapter(settings: Settings) -> SearchAdapter:
    """Create the search adapter based on SEARCH_PROVIDER."""
    if settings.search_provider == "bocha":
        api_key = settings.search_api_key.get_secret_value() if settings.search_api_key else ""
        if not api_key:
            raise ValueError("SEARCH_API_KEY is required for the Bocha search provider")
        return BochaAdapter(api_key=api_key)
    if settings.search_provider == "searxng":
        base_url = getattr(settings, "search_base_url", None) or "http://localhost:8888"
        return SearXNGAdapter(base_url=base_url)
    return MockSearchAdapter()
