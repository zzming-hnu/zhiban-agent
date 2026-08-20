"""Search result sanitization: strip markup and mark content as untrusted data."""

import re

from zhiban.tools.search.base import SearchResult

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_snippet(snippet: str, *, max_chars: int = 500) -> str:
    """Strip HTML tags and collapse whitespace; cap length."""
    text = _HTML_TAG_RE.sub("", snippet)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text


def sanitize_result(result: SearchResult) -> SearchResult:
    """Return a sanitized copy of a search result.

    Search content is untrusted data: it must never change tool permissions,
    read secrets, or trigger high-risk actions. Sanitization is a first-line
    defense; the agent still treats every snippet as untrusted user data.
    """
    return SearchResult(
        title=sanitize_snippet(result.title, max_chars=120),
        url=result.url,
        snippet=sanitize_snippet(result.snippet),
        source=result.source,
        published_at=result.published_at,
    )
