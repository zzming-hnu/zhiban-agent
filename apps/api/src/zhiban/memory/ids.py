"""Deterministic memory identifiers: fingerprint, conflict_key, candidate key."""

import hashlib
import uuid

from zhiban.memory.normalize import normalize_text


def _sha256(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def memory_fingerprint(
    *,
    user_id: uuid.UUID,
    memory_type: str,
    subject: str,
    predicate: str,
    value: str,
) -> str:
    """Fingerprint of a memory fact (used for active-memory dedupe).

    ``SHA-256(user_id + type + subject + predicate + value)`` with normalized
    components. Version-invariant: does not include extractor/model version.
    """
    material = "\x1f".join(
        [
            str(user_id),
            memory_type,
            normalize_text(subject),
            normalize_text(predicate),
            normalize_text(value),
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
    """Conflict key for slot-conflict detection (excludes value)."""
    material = "\x1f".join(
        [
            str(user_id),
            memory_type,
            normalize_text(subject),
            normalize_text(predicate),
        ]
    )
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
