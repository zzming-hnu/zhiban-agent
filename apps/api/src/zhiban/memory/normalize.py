"""Deterministic text normalization for memory facts."""

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize text: strip, Unicode NFKC, collapse whitespace.

    Does NOT do semantic synonym rewriting (which could change meaning).
    """
    text = unicodedata.normalize("NFKC", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


# Canonical predicate forms for slot-conflict detection. The LLM extracts
# predicates loosely ("喜欢吃" vs "喜欢" vs "爱吃"), which would otherwise
# defeat conflict_key (type+subject+predicate) and leave near-duplicate
# memories unmerged. These maps collapse common synonym predicates to a stable
# canonical form ONLY for conflict-key computation — the stored predicate and
# rendered content are left untouched.
_PREDICATE_SYNONYMS: dict[str, str] = {
    "喜欢吃": "喜欢",
    "不爱吃": "不喜欢",
    "爱吃": "喜欢",
    "喜好": "喜欢",
    "偏好": "喜欢",
    "喜欢喝": "喜欢",
    "不喜欢喝": "不喜欢",
    "爱好": "喜欢",
    "讨厌": "不喜欢",
    "不喜欢吃": "不喜欢",
}


def normalize_predicate(predicate: str) -> str:
    """Canonicalize a predicate for conflict-key computation.

    Only maps known synonym predicates to their canonical form; unknown
    predicates are returned as-is (after basic text normalization), so the
    mapping is conservative and never rewrites meaning.
    """
    normalized = normalize_text(predicate)
    return _PREDICATE_SYNONYMS.get(normalized, normalized)
