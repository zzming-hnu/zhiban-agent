"""Deterministic validation rules for memory candidates."""

import uuid

from zhiban.memory.normalize import normalize_text
from zhiban.memory.schemas import MemoryCandidatePayload
from zhiban.memory.types import RejectReason

# Sensitive content that must never become implicit long-term memory.
_SENSITIVE_MARKERS = (
    "密码",
    "password",
    "token",
    "令牌",
    "验证码",
    "api key",
    "apikey",
    "secret",
    "密钥",
)

# Implicit confidence thresholds (per memory type).
_IMPLICIT_MIN_CONFIDENCE = 0.65
_HABIT_MIN_CONFIDENCE = 0.80


class ValidationResult:
    def __init__(self, *, ok: bool, reason: RejectReason | None = None) -> None:
        self.ok = ok
        self.reason = reason


def validate_candidate(
    candidate: MemoryCandidatePayload,
    *,
    source_kind: str,
    available_message_ids: set[uuid.UUID],
    available_message_texts: dict[uuid.UUID, str],
) -> ValidationResult:
    """Validate a candidate against deterministic rules.

    Returns a ValidationResult; ``ok=False`` carries a reject reason.
    """
    # Evidence must come from the allowed batch.
    if not candidate.source_message_ids:
        return ValidationResult(ok=False, reason=RejectReason.source_missing)
    for mid in candidate.source_message_ids:
        if mid not in available_message_ids:
            return ValidationResult(ok=False, reason=RejectReason.source_out_of_scope)

    # Evidence quote must appear in one of the source messages.
    quote = normalize_text(candidate.evidence_quote)
    if quote:
        found = any(
            quote in normalize_text(available_message_texts.get(mid, ""))
            for mid in candidate.source_message_ids
        )
        if not found:
            return ValidationResult(ok=False, reason=RejectReason.evidence_not_found)

    # Sensitive content must never be an implicit memory.
    value = normalize_text(candidate.value)
    if source_kind == "implicit":
        lowered = value.lower()
        if any(marker.lower() in lowered for marker in _SENSITIVE_MARKERS):
            return ValidationResult(ok=False, reason=RejectReason.sensitive_implicit_memory)

        # Confidence thresholds.
        threshold = (
            _HABIT_MIN_CONFIDENCE if candidate.memory_type == "habit" else _IMPLICIT_MIN_CONFIDENCE
        )
        if candidate.confidence < threshold:
            return ValidationResult(ok=False, reason=RejectReason.confidence_too_low)

    # Defensive check: ``value`` must be a pure value, not a template that
    # re-includes ``subject`` / ``predicate``. Some models emit
    #   {subject: "称呼", predicate: "要求被称呼为", value: "称呼 要求被称呼为 zymonzhang"}
    # which then renders as the duplicated string
    #   "称呼 要求被称呼为 称呼 要求被称呼为 zymonzhang".
    # We reject whenever ``value`` starts with the concatenation of
    # ``subject`` + ``predicate`` (the only way a well-formed fact could
    # legitimately begin that way is by coincidence, which is rare and
    # confusing to read anyway).
    if value_looks_malformed(
        value=value, subject=candidate.subject, predicate=candidate.predicate
    ):
        return ValidationResult(ok=False, reason=RejectReason.malformed_value)

    return ValidationResult(ok=True)


def value_looks_malformed(*, value: str, subject: str, predicate: str) -> bool:
    """Return True when ``value`` duplicates the ``subject`` + ``predicate``
    concatenation. Used by both the implicit extractor validator and the
    explicit ``memory.add`` tool path so neither can sneak past it.
    """
    normalized = normalize_text(value)
    if not normalized:
        return False
    sub = normalize_text(subject)
    pred = normalize_text(predicate)
    full_prefix = f"{sub} {pred}".strip()
    if not full_prefix or len(full_prefix) < 2:
        return False
    return normalized.startswith(full_prefix)
