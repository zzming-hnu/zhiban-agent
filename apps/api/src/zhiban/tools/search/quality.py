"""Search result quality: deduplication and source credibility scoring.

Search engines (especially meta-search) often return the same article from
multiple engines or syndicated copies of the same story. This module provides:

1. ``deduplicate`` — drop near-duplicate results (URL canonicalization + title
   similarity), keeping the first occurrence.
2. ``source_credibility`` — score a result's source domain on a coarse 0..1
   scale so the agent can prefer authoritative sources over low-quality ones.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit

from zhiban.tools.search.base import SearchResult

# Track parameters that do not change the underlying page content.
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "spm", "scm", "from", "source",
}

# Coarse credibility tiers by domain keyword. Higher = more trustworthy.
_HIGH_CREDIBILITY = (
    "gov.cn", "edu.cn", ".gov", ".edu", "wikipedia", "baike",
    "people.com.cn", "xinhuanet", "cctv", "ifeng", "163.com",
    "qq.com", "sina", "sohu", "36kr", "ithome", "csdn", "juejin",
    "zhihu", "github.com", "openai", "deepseek",
)
_MEDIUM_CREDIBILITY = (
    "cnblogs", "segmentfault", "infoq", "oschina", "jianshu",
    "toutiao", "thepaper", "澎湃", "bilibili",
)


def canonical_url(url: str) -> str:
    """Normalize a URL for dedup: lowercase host, drop fragment, strip tracking
    params, and remove a trailing slash."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/")
    query = "&".join(
        f"{k}={v}"
        for k, v in (p.split("=", 1) for p in parts.query.split("&") if p)
        if k not in _TRACKING_PARAMS
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def deduplicate(
    results: list[SearchResult], *, title_threshold: float = 0.85
) -> list[SearchResult]:
    """Drop near-duplicate results, keeping the first occurrence.

    Two results are duplicates when their canonical URLs match, or their
    normalized titles are near-identical (syndicated copies of one article).
    """
    seen_urls: set[str] = set()
    kept: list[SearchResult] = []
    for r in results:
        key = canonical_url(r.url)
        if key in seen_urls:
            continue
        # Title-level dedup against already-kept items.
        if any(_title_similarity(r.title, k.title) >= title_threshold for k in kept):
            continue
        seen_urls.add(key)
        kept.append(r)
    return kept


def source_credibility(source: str) -> float:
    """Score a source (site name or domain) on a coarse 0..1 credibility scale."""
    s = (source or "").lower()
    if not s:
        return 0.5
    if any(k in s for k in _HIGH_CREDIBILITY):
        return 1.0
    if any(k in s for k in _MEDIUM_CREDIBILITY):
        return 0.7
    return 0.4


def rank_by_quality(results: list[SearchResult]) -> list[SearchResult]:
    """Sort results by source credibility (stable), keeping original order for
    ties so higher-quality sources surface first."""
    return sorted(results, key=lambda r: source_credibility(r.source), reverse=True)
