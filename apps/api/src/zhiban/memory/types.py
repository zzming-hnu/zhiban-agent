"""Memory domain enums: type, source kind, status, and reject reason."""

from enum import StrEnum


class MemoryType(StrEnum):
    identity = "identity"
    preference = "preference"
    habit = "habit"
    person = "person"
    event = "event"
    task = "task"
    temporary = "temporary"
    communication = "communication"


class MemoryCategory(StrEnum):
    """User-facing memory categories (display + governance grouping)."""

    basic_info = "basic_info"  # 基本信息
    communication_taboo = "communication_taboo"  # 沟通禁忌
    communication_preference = "communication_preference"  # 沟通偏好
    other = "other"  # 其他


# Deterministic memory_type -> category mapping. When the LLM returns a category
# that contradicts this mapping, the deterministic rule wins (per the
# "先确定性、后模型判断" principle). ``None`` means "let the LLM decide".
_MEMORY_TYPE_TO_CATEGORY: dict[str, str | None] = {
    "identity": "basic_info",  # 姓名/职业/身份等稳定背景
    "person": "basic_info",  # 相关人物
    "event": "basic_info",  # 重要事件
    "communication": None,  # 沟通类由 LLM 判断 taboo vs preference
    "preference": None,  # 偏好：可能是沟通偏好或其他
    "habit": "other",
    "task": "other",
    "temporary": "other",
}


def category_for_memory_type(memory_type: str) -> str | None:
    """Return the deterministic category for a memory_type, or None if the LLM decides."""
    return _MEMORY_TYPE_TO_CATEGORY.get(memory_type)


def resolve_category(memory_type: str, llm_category: str) -> str:
    """Resolve the final category: deterministic mapping wins when it exists.

    For types without a deterministic mapping (communication/preference), fall
    back to the LLM-provided category (defaulting to "other" when invalid).
    """
    forced = category_for_memory_type(memory_type)
    if forced is not None:
        return forced
    valid = {"basic_info", "communication_taboo", "communication_preference", "other"}
    return llm_category if llm_category in valid else "other"


class SourceKind(StrEnum):
    explicit = "explicit"
    implicit = "implicit"
    imported = "imported"


class MemoryStatus(StrEnum):
    active = "active"
    superseded = "superseded"
    deleted = "deleted"
    expired = "expired"


class Decision(StrEnum):
    add = "add"
    update = "update"
    delete = "delete"
    ignore = "ignore"


class RejectReason(StrEnum):
    schema_invalid = "schema_invalid"
    unknown_type = "unknown_type"
    empty_value = "empty_value"
    value_too_long = "value_too_long"
    source_missing = "source_missing"
    source_out_of_scope = "source_out_of_scope"
    evidence_not_found = "evidence_not_found"
    assistant_only_evidence = "assistant_only_evidence"
    confidence_too_low = "confidence_too_low"
    sensitive_implicit_memory = "sensitive_implicit_memory"
    ephemeral_not_useful = "ephemeral_not_useful"
    unsupported_third_party_data = "unsupported_third_party_data"
    expired_on_arrival = "expired_on_arrival"
    duplicate = "duplicate"
    conflict_ambiguous = "conflict_ambiguous"
    user_disabled_memory = "user_disabled_memory"
    policy_blocked = "policy_blocked"
    persistence_failed = "persistence_failed"
    malformed_value = "malformed_value"
