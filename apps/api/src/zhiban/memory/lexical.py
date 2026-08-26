"""Lexical memory retrieval via jieba tokenization + BM25.

Replaces the naive ``content ILIKE %query%`` substring match, which fails for
Chinese because it requires the entire query to appear verbatim inside the
memory content. BM25 scores term overlap after CJK segmentation, so related
phrases (e.g. "喝咖啡偏好" vs "美式咖啡不加糖") can still match.
"""

from __future__ import annotations

import math
from collections import Counter

import jieba

# Tokenize once per process (jieba builds its dict lazily and is expensive on
# the first call; cache helps large memory sets).
_jieba_initialized = False


def _ensure_jieba() -> None:
    global _jieba_initialized
    if not _jieba_initialized:
        jieba.initialize()
        _jieba_initialized = True


def tokenize(text: str) -> list[str]:
    """Segment text into CJK/word tokens, filtering out stop-ish fragments."""
    _ensure_jieba()
    tokens = jieba.lcut(text.lower())
    # Drop pure whitespace/punctuation and single-char non-CJK noise.
    return [t for t in tokens if t.strip() and not _is_noise(t)]


_NOISE = set("的了呢吗啊吧呀哦嗯—-_=+*/\\|,.;:!?()[]{}<>《》\"'。，、；：！？（）")

# High-frequency CJK function words that carry little semantic signal. Dropping
# them prevents spurious matches (e.g. the shared "我" matching every memory).
_STOPWORDS = {
    "我", "你", "他", "她", "它", "我们", "你们", "他们",
    "在", "有", "是", "的", "了", "和", "与", "或", "就", "都",
    "什么", "怎么", "哪家", "哪个", "哪些", "为什么", "如何",
    "一下", "帮", "记", "谁", "呢", "吗", "啊", "吧",
    "一个", "这个", "那个", "最近", "现在", "今天", "明天",
    "自己", "我的", "你的", "他的",
}


def _is_noise(tok: str) -> bool:
    return (
        tok in _NOISE
        or tok in _STOPWORDS
        or (len(tok) == 1 and not ("\u4e00" <= tok <= "\u9fff"))
    )


class BM25LexicalIndex:
    """A tiny BM25 index over a set of documents (memory contents)."""

    def __init__(self, documents: list[str], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._tokenized = [tokenize(d) for d in documents]
        self._doc_len = [len(t) for t in self._tokenized]
        self._avgdl = sum(self._doc_len) / len(self._doc_len) if self._doc_len else 0.0
        self._doc_freq: Counter[str] = Counter()
        for toks in self._tokenized:
            self._doc_freq.update(set(toks))
        self._n = len(self._tokenized)

    def score(self, query: str, doc_index: int) -> float:
        """BM25 score of ``query`` against document at ``doc_index``."""
        if self._n == 0:
            return 0.0
        toks = self._tokenized[doc_index]
        tf = Counter(toks)
        dl = self._doc_len[doc_index]
        score = 0.0
        for term in set(tokenize(query)):
            if term not in tf:
                continue
            df = self._doc_freq.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
            numer = tf[term] * (self.k1 + 1)
            denom = tf[term] + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1.0))
            score += idf * numer / denom
        return score


def lexical_similarity(query: str, content: str) -> float:
    """Normalized lexical relevance in [0, 1] for a single query/content pair.

    Uses jieba token overlap with a light IDF weighting. Returns 1.0 for full
    overlap, ~0 for no shared content terms.
    """
    qtoks = [t for t in tokenize(query)]
    if not qtoks:
        return 0.0
    ctoks = set(tokenize(content))
    if not ctoks:
        return 0.0
    overlap = sum(1 for t in qtoks if t in ctoks)
    # Normalize by query length, so a query that is fully covered scores 1.0.
    return overlap / len(qtoks)
