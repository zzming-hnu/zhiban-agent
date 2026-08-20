"""LLM error classification and retry policy."""

from dataclasses import dataclass
from enum import StrEnum


class ErrorKind(StrEnum):
    """Stable error categories, matching the architecture's error table."""

    validation = "validation"
    auth = "auth"
    permission = "permission"
    conflict = "conflict"
    rate_limit = "rate_limit"
    dependency_transient = "dependency_transient"
    tool_timeout = "tool_timeout"
    model_invalid = "model_invalid"
    safety = "safety"
    internal = "internal"


# HTTP status codes that are safe to retry before any text has been emitted.
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class LLMError(Exception):
    """An error raised by an LLM adapter with a stable classification."""

    kind: ErrorKind
    message: str
    status_code: int | None = None
    retryable: bool = False


def classify_http_error(status_code: int, body: str = "") -> LLMError:
    """Map an HTTP status code from an LLM provider to a stable error kind."""
    if status_code == 401:
        return LLMError(ErrorKind.auth, "模型鉴权失败", status_code, retryable=False)
    if status_code == 403:
        return LLMError(ErrorKind.permission, "模型访问被拒绝", status_code, retryable=False)
    if status_code == 429:
        return LLMError(ErrorKind.rate_limit, "模型请求过于频繁", status_code, retryable=True)
    if status_code == 400:
        return LLMError(ErrorKind.validation, "模型请求参数不合法", status_code, retryable=False)
    if status_code == 404:
        return LLMError(ErrorKind.validation, "模型不存在", status_code, retryable=False)
    if status_code in _RETRYABLE_STATUS:
        return LLMError(
            ErrorKind.dependency_transient,
            "模型服务暂时不可用",
            status_code,
            retryable=True,
        )
    if 400 <= status_code < 500:
        return LLMError(ErrorKind.validation, "模型请求被拒绝", status_code, retryable=False)
    return LLMError(ErrorKind.internal, "模型服务异常", status_code, retryable=False)


def is_retryable(error: LLMError) -> bool:
    return error.retryable
