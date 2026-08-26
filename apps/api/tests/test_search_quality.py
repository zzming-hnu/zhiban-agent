"""Unit tests for search quality (dedup + credibility) and lexical retrieval."""

from zhiban.memory.lexical import BM25LexicalIndex, lexical_similarity, tokenize
from zhiban.tools.search.base import SearchResult
from zhiban.tools.search.quality import (
    canonical_url,
    deduplicate,
    rank_by_quality,
    source_credibility,
)

# --- canonical_url ---


def test_canonical_url_strips_tracking_params() -> None:
    a = "https://www.Example.com/c/abc?utm_source=x&id=1#section"
    b = "https://example.com/c/abc?id=1"
    assert canonical_url(a) == canonical_url(b)


# --- deduplicate ---


def test_deduplicate_removes_duplicate_urls() -> None:
    # Same canonical URL (differing only by tracking param) -> dedup to 1.
    results = [
        SearchResult(
            title="DeepSeek开源Harness",
            url="https://news.ifeng.com/c/a?utm_source=x",
            snippet="s",
            source="ifeng",
        ),
        SearchResult(
            title="DeepSeek开源Harness",
            url="https://news.ifeng.com/c/a?utm_medium=y",
            snippet="s",
            source="ifeng",
        ),
        SearchResult(
            title="个人博客聊聊harness",
            url="https://myblog.example.com/p1",
            snippet="s",
            source="blog",
        ),
    ]
    deduped = deduplicate(results)
    assert len(deduped) == 2


def test_deduplicate_removes_near_identical_titles() -> None:
    # Same title text (syndicated copies) on different URLs -> dedup to 1.
    results = [
        SearchResult(
            title="DeepSeek开源Harness框架正式发布",
            url="https://a.com/1",
            snippet="s",
            source="ifeng",
        ),
        SearchResult(
            title="DeepSeek开源Harness框架正式发布",
            url="https://b.com/2",
            snippet="s",
            source="163",
        ),
    ]
    deduped = deduplicate(results)
    assert len(deduped) == 1


# --- source credibility ---


def test_source_credibility_ranks_authoritative_higher() -> None:
    assert source_credibility("github.com") == 1.0
    assert source_credibility("ifeng") == 1.0
    assert source_credibility("blog") == 0.4
    assert source_credibility("") == 0.5


def test_rank_by_quality_sorts_desc() -> None:
    results = [
        SearchResult(title="b", url="https://blog.example.com/b", snippet="", source="blog"),
        SearchResult(title="a", url="https://github.com/x/a", snippet="", source="github.com"),
    ]
    ranked = rank_by_quality(results)
    assert ranked[0].source == "github.com"


# --- lexical tokenization ---


def test_tokenize_filters_stopwords() -> None:
    toks = tokenize("我喝咖啡有什么偏好")
    # "我"/"什么" are stopwords and should be dropped.
    assert "我" not in toks
    assert "什么" not in toks
    assert any("咖啡" in t for t in toks)


def test_lexical_similarity_overlap() -> None:
    # "少糖咖啡" should overlap "美式咖啡不加糖" through "咖啡".
    s = lexical_similarity("少糖咖啡", "self 喜欢 美式咖啡不加糖")
    assert s > 0.0
    # Totally unrelated text yields zero overlap.
    assert lexical_similarity("今天天气怎么样", "self 喜欢 美式咖啡不加糖") == 0.0


def test_bm25_scores_matching_doc_higher() -> None:
    docs = ["self 喜欢 美式咖啡不加糖", "self 习惯 每天早上跑步"]
    bm25 = BM25LexicalIndex(docs)
    assert bm25.score("少糖咖啡", 0) > bm25.score("少糖咖啡", 1)
