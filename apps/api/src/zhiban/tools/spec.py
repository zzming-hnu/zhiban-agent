"""Tool metadata: spec, permission, idempotency, and retry policy."""

from dataclasses import dataclass
from typing import Literal, TypeVar

from pydantic import BaseModel

TInput = TypeVar("TInput", bound=BaseModel)

Permission = Literal["read", "write", "sensitive"]
Idempotency = Literal["none", "optional", "required"]
RetryPolicy = Literal["never", "safe_once"]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Declarative metadata for a tool.

    The executor uses this to enforce timeout, retry, idempotency, permission,
    and result truncation, keeping those concerns out of the tool itself.
    """

    name: str
    description: str
    input_model: type[BaseModel]
    permission: Permission = "read"
    timeout_seconds: float = 10.0
    idempotency: Idempotency = "none"
    retry_policy: RetryPolicy = "never"
    result_token_budget: int = 600
