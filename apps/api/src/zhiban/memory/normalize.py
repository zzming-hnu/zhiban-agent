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
