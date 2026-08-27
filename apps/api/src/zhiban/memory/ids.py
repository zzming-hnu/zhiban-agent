"""Deterministic memory identifiers: fingerprint, conflict_key, candidate key."""

import hashlib
import uuid

from zhiban.memory.normalize import normalize_predicate, normalize_text


def _sha256(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def memory_fingerprint(
    *,
    user_id: uuid.UUID,
    memory_type: str,
    subject: str,
    predicate: str,
    value: str,
    negated: bool = False,
) -> str:
    """Fingerprint of a memory fact (used for active-memory dedupe).

    ``SHA-256(user_id + type + subject + predicate + value + negated)`` with
    normalized components. ``negated`` is included so a fact and its negation
    are distinct memories (not deduped), while still sharing a conflict slot
    (``conflict_key`` excludes ``negated``).
    """
    material = "\x1f".join(
        [
            str(user_id),
            memory_type,
            normalize_text(subject),
            normalize_text(predicate),
            normalize_text(value),
            "1" if negated else "0",
        ]
    )
    return _sha256(material)


def conflict_key(
    *,
    user_id: uuid.UUID,
    memory_type: str,
    subject: str,
    predicate: str,
) -> str:
    """Conflict key for slot-conflict detection (excludes value).

    The predicate is canonicalized (``normalize_predicate``) so that synonym
    predicates ("喜欢吃" vs "喜欢" vs "爱吃") collapse to the same slot. This
    lets near-duplicate memories from different extraction paths (explicit
    memory.add vs implicit flush) be recognized as the same fact and merged.
    """
    material = "\x1f".join(
        [
            str(user_id),
            memory_type,
            normalize_text(subject),
            normalize_predicate(predicate),
        ]
    )
    return _sha256(material)


def fact_fingerprint(*, user_id: uuid.UUID, memory_type: str, fact: str) -> str:
    """Fingerprint of a natural-language fact (used for active-memory dedupe).

    ``SHA-256(user_id + type + normalized fact)``. Exact-text dedupe only: the
    same sentence is deduped, while semantically-similar-but-worded-differently
    facts are handled by the semantic (embedding) merge layer.
    """
    material = "\x1f".join([str(user_id), memory_type, normalize_text(fact)])
    return _sha256(material)


def fact_conflict_key(*, user_id: uuid.UUID, memory_type: str, fact: str) -> str:
    """Conflict key for a natural-language fact.

    Uses ``user_id + memory_type + normalized fact`` so that the exact same fact
    maps to one slot. Semantic evolution ("不喜欢吃辣" -> "喜欢吃辣") is resolved
    by the embedding-similarity merge layer, not this exact-text key.
    """
    material = "\x1f".join([str(user_id), memory_type, normalize_text(fact)])
    return _sha256(material)


def candidate_idempotency_key(
    *,
    user_id: uuid.UUID,
    extractor_version: str,
    source_message_ids: list[uuid.UUID],
    canonical_candidate: str,
) -> str:
    """Idempotency key for a memory candidate (stable across replays)."""
    sorted_ids = "\x1f".join(str(mid) for mid in sorted(source_message_ids))
    material = "\x1f".join([str(user_id), extractor_version, sorted_ids, canonical_candidate])
    return _sha256(material)
