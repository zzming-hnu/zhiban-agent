"""Unit tests for memory normalization, ids, and validation (no database)."""

import uuid

from zhiban.memory.ids import candidate_idempotency_key, conflict_key, memory_fingerprint
from zhiban.memory.normalize import normalize_text
from zhiban.memory.schemas import MemoryCandidatePayload
from zhiban.memory.types import RejectReason
from zhiban.memory.validator import validate_candidate


def test_normalize_nfkc_and_collapse_whitespace() -> None:
    assert normalize_text("  你好　世界  ") == "你好 世界"
    # Full-width characters are NFKC-normalized.
    assert normalize_text("ＡＢＣ") == "ABC"


def test_fingerprint_is_stable_and_value_sensitive() -> None:
    uid = uuid.uuid4()
    f1 = memory_fingerprint(
        user_id=uid, memory_type="preference", subject="self", predicate="喜欢", value="少糖"
    )
    f2 = memory_fingerprint(
        user_id=uid, memory_type="preference", subject="self", predicate="喜欢", value="少糖"
    )
    f3 = memory_fingerprint(
        user_id=uid, memory_type="preference", subject="self", predicate="喜欢", value="多糖"
    )
    assert f1 == f2
    assert f1 != f3


def test_fingerprint_is_user_scoped() -> None:
    a = uuid.uuid4()
    b = uuid.uuid4()
    fa = memory_fingerprint(
        user_id=a, memory_type="preference", subject="s", predicate="p", value="v"
    )
    fb = memory_fingerprint(
        user_id=b, memory_type="preference", subject="s", predicate="p", value="v"
    )
    assert fa != fb


def test_conflict_key_excludes_value() -> None:
    uid = uuid.uuid4()
    k1 = conflict_key(user_id=uid, memory_type="preference", subject="self", predicate="喜欢")
    k2 = conflict_key(user_id=uid, memory_type="preference", subject="self", predicate="喜欢")
    assert k1 == k2


def test_candidate_idempotency_key_stable_across_source_order() -> None:
    uid = uuid.uuid4()
    m1 = uuid.uuid4()
    m2 = uuid.uuid4()
    k1 = candidate_idempotency_key(
        user_id=uid, extractor_version="v1", source_message_ids=[m1, m2], canonical_candidate="{}"
    )
    k2 = candidate_idempotency_key(
        user_id=uid, extractor_version="v1", source_message_ids=[m2, m1], canonical_candidate="{}"
    )
    assert k1 == k2


def _candidate(**overrides: object) -> MemoryCandidatePayload:
    base = dict(
        memory_type="preference",
        subject="self",
        predicate="喜欢",
        value="少糖咖啡",
        source_message_ids=[uuid.uuid4()],
        evidence_quote="我喜欢少糖咖啡",
        confidence=0.9,
        importance=0.7,
    )
    base.update(overrides)
    return MemoryCandidatePayload(**base)


def test_validator_accepts_valid_explicit_candidate() -> None:
    mid = uuid.uuid4()
    cand = _candidate(source_message_ids=[mid], evidence_quote="我喜欢少糖咖啡")
    result = validate_candidate(
        cand,
        source_kind="explicit",
        available_message_ids={mid},
        available_message_texts={mid: "我喜欢少糖咖啡"},
    )
    assert result.ok is True


def test_validator_rejects_out_of_scope_source() -> None:
    cand = _candidate(source_message_ids=[uuid.uuid4()])
    result = validate_candidate(
        cand, source_kind="explicit", available_message_ids=set(), available_message_texts={}
    )
    assert result.ok is False
    assert result.reason == RejectReason.source_out_of_scope


def test_validator_rejects_missing_evidence() -> None:
    mid = uuid.uuid4()
    cand = _candidate(source_message_ids=[mid], evidence_quote="不存在的证据")
    result = validate_candidate(
        cand,
        source_kind="explicit",
        available_message_ids={mid},
        available_message_texts={mid: "实际的消息内容"},
    )
    assert result.ok is False
    assert result.reason == RejectReason.evidence_not_found


def test_validator_rejects_sensitive_implicit() -> None:
    mid = uuid.uuid4()
    cand = _candidate(
        source_message_ids=[mid],
        evidence_quote="我的密码是123456",
        value="我的密码是123456",
    )
    result = validate_candidate(
        cand,
        source_kind="implicit",
        available_message_ids={mid},
        available_message_texts={mid: "我的密码是123456"},
    )
    assert result.ok is False
    assert result.reason == RejectReason.sensitive_implicit_memory


def test_validator_rejects_low_confidence_implicit() -> None:
    mid = uuid.uuid4()
    cand = _candidate(source_message_ids=[mid], confidence=0.3, evidence_quote="我喜欢少糖咖啡")
    result = validate_candidate(
        cand,
        source_kind="implicit",
        available_message_ids={mid},
        available_message_texts={mid: "我喜欢少糖咖啡"},
    )
    assert result.ok is False
    assert result.reason == RejectReason.confidence_too_low


def test_validator_rejects_value_that_duplicates_subject_predicate() -> None:
    """Models sometimes emit value="subject predicate X" by mistake.

    The validator must reject this so the rendered content does not
    duplicate the subject/predicate prefixes.
    """
    mid = uuid.uuid4()
    cand = MemoryCandidatePayload(
        memory_type="communication",
        category="communication_preference",
        subject="称呼",
        predicate="要求被称呼为",
        value="称呼 要求被称呼为zymonzhang",  # duplicated prefix
        source_message_ids=[mid],
        evidence_quote="叫我zymonzhang",
        confidence=0.9,
        importance=0.7,
    )
    result = validate_candidate(
        cand,
        source_kind="explicit",
        available_message_ids={mid},
        available_message_texts={mid: "叫我zymonzhang"},
    )
    assert result.ok is False
    assert result.reason == RejectReason.malformed_value


def test_validator_rejects_value_that_is_only_subject_predicate() -> None:
    """If value is exactly subject+predicate (no real value), reject."""
    mid = uuid.uuid4()
    cand = MemoryCandidatePayload(
        memory_type="communication",
        category="communication_preference",
        subject="称呼",
        predicate="要求被称呼为",
        value="称呼 要求被称呼为",
        source_message_ids=[mid],
        evidence_quote="叫我zymonzhang",
        confidence=0.9,
        importance=0.7,
    )
    result = validate_candidate(
        cand,
        source_kind="explicit",
        available_message_ids={mid},
        available_message_texts={mid: "叫我zymonzhang"},
    )
    assert result.ok is False
    assert result.reason == RejectReason.malformed_value


def test_validator_accepts_pure_value_with_no_subject_overlap() -> None:
    """A clean value that does not duplicate subject/predicate must pass."""
    mid = uuid.uuid4()
    cand = MemoryCandidatePayload(
        memory_type="communication",
        category="communication_preference",
        subject="称呼",
        predicate="要求被称呼为",
        value="zymonzhang",
        source_message_ids=[mid],
        evidence_quote="叫我zymonzhang",
        confidence=0.9,
        importance=0.7,
    )
    result = validate_candidate(
        cand,
        source_kind="explicit",
        available_message_ids={mid},
        available_message_texts={mid: "叫我zymonzhang"},
    )
    assert result.ok is True


def test_resolve_category_forces_identity_to_basic_info() -> None:
    from zhiban.memory.types import resolve_category

    # LLM wrongly guessed "other" for an identity fact; deterministic rule wins.
    assert resolve_category("identity", "other") == "basic_info"
    assert resolve_category("person", "other") == "basic_info"
    assert resolve_category("event", "communication_preference") == "basic_info"


def test_resolve_category_lets_llm_decide_for_ambiguous_types() -> None:
    from zhiban.memory.types import resolve_category

    # communication / preference have no deterministic mapping -> LLM decides.
    assert resolve_category("communication", "communication_taboo") == "communication_taboo"
    assert resolve_category("preference", "communication_preference") == "communication_preference"
    # Invalid LLM category falls back to "other".
    assert resolve_category("preference", "bogus") == "other"


def test_add_memory_input_rejects_category_value_as_memory_type() -> None:
    """The LLM sometimes fills memory_type with a category value (e.g.
    'communication_preference'). The tool schema must reject it via Literal."""
    import pytest
    from pydantic import ValidationError
    from zhiban.memory.tools import AddMemoryInput

    with pytest.raises(ValidationError):
        AddMemoryInput(
            memory_type="communication_preference",  # category value, not a valid type
            category="communication_preference",
            subject="用户",
            predicate="偏好",
            value="简洁回答",
        )

    # Valid memory_type passes.
    ok = AddMemoryInput(
        memory_type="communication",
        category="communication_preference",
        subject="用户",
        predicate="偏好",
        value="简洁回答",
    )
    assert ok.memory_type == "communication"
