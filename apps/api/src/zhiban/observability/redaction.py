"""Log redaction: strip secrets and sensitive content from log records."""

import re
from collections.abc import MutableMapping
from typing import Any

# Field names whose values must never be logged in full.
_SENSITIVE_FIELD_PATTERNS = (
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"session", re.IGNORECASE),
)

# Field names that are full user content; log only their length.
_CONTENT_FIELD_PATTERNS = (
    re.compile(r"^content$", re.IGNORECASE),
    re.compile(r"^message$", re.IGNORECASE),
    re.compile(r"^prompt$", re.IGNORECASE),
    re.compile(r"^text$", re.IGNORECASE),
    re.compile(r"^body$", re.IGNORECASE),
    re.compile(r"^query$", re.IGNORECASE),
)

REDACTED = "[REDACTED]"


def _is_sensitive_key(key: str) -> bool:
    return any(p.search(key) for p in _SENSITIVE_FIELD_PATTERNS)


def _is_content_key(key: str) -> bool:
    return any(p.search(key) for p in _CONTENT_FIELD_PATTERNS)


def redact_value(key: str, value: Any) -> Any:
    """Redact a log field value based on its key name."""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if _is_sensitive_key(key):
        return REDACTED
    if _is_content_key(key) and isinstance(value, str):
        return f"[len={len(value)}]"
    return value


def redact_event_dict(
    logger_name: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> dict[str, Any]:
    """structlog processor: redact sensitive values in the event dict."""
    return {key: redact_value(key, value) for key, value in event_dict.items()}
