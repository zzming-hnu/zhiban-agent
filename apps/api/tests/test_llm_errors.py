"""Unit tests for LLM error classification (no network)."""

from zhiban.llm.errors import ErrorKind, LLMError, classify_http_error


def test_rate_limit_classified_as_retryable() -> None:
    error = classify_http_error(429, "rate limit exceeded")
    assert error.kind == ErrorKind.rate_limit
    assert error.retryable


def test_5xx_classified_as_transient() -> None:
    error = classify_http_error(503, "service unavailable")
    assert error.kind == ErrorKind.dependency_transient
    assert error.retryable


def test_4xx_classified_as_not_retryable() -> None:
    error = classify_http_error(401, "unauthorized")
    assert error.kind == ErrorKind.auth
    assert not error.retryable


def test_timeout_classified_as_transient() -> None:
    error = classify_http_error(408, "timeout")
    assert error.kind == ErrorKind.dependency_transient


def test_other_4xx_classified_as_validation() -> None:
    error = classify_http_error(418, "teapot")
    assert error.kind == ErrorKind.validation
    assert not error.retryable


def test_llm_error_carries_kind() -> None:
    error = LLMError(ErrorKind.model_invalid, "空回复", retryable=True)
    assert error.kind == ErrorKind.model_invalid
    assert error.retryable
    assert "空回复" in str(error)
