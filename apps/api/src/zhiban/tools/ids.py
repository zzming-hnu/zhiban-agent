"""Deterministic idempotency keys for tool calls."""

import hashlib
import json
import uuid
from typing import Any


def canonical_args(args: dict[str, Any]) -> str:
    """Canonicalize arguments with sorted keys so equivalent dicts match."""
    return json.dumps(args, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def operation_key(
    *, user_id: uuid.UUID, run_id: uuid.UUID, tool_name: str, args: dict[str, Any]
) -> str:
    """Compute a stable operation key for a write tool invocation.

    ``SHA-256(user_id + run_id + tool_name + canonical_args)``, so a retry of
    the same call within the same run produces the same key.
    """
    material = "\x1f".join(
        [
            str(user_id),
            str(run_id),
            tool_name,
            canonical_args(args),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
