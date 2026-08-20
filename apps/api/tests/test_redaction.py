"""Unit tests for log redaction (secrets and sensitive content)."""

from zhiban.observability.redaction import redact_event_dict, redact_value


def test_sensitive_fields_are_redacted() -> None:
    assert redact_value("password", "secret123") == "[REDACTED]"
    assert redact_value("token", "abc") == "[REDACTED]"
    assert redact_value("api_key", "xyz") == "[REDACTED]"
    assert redact_value("Authorization", "Bearer xxx") == "[REDACTED]"
    assert redact_value("session_secret", "s") == "[REDACTED]"


def test_content_fields_log_length_only() -> None:
    assert redact_value("content", "hello world") == "[len=11]"
    assert redact_value("message", "长文本") == "[len=3]"
    assert redact_value("query", "search term") == "[len=11]"


def test_non_sensitive_values_pass_through() -> None:
    assert redact_value("tool_name", "web_search") == "web_search"
    assert redact_value("status_code", 200) == 200
    assert redact_value("duration_ms", 12.5) == 12.5
    assert redact_value("ok", True) is True


def test_event_dict_redaction() -> None:
    event = redact_event_dict(
        "logger",
        "method",
        {
            "password": "hunter2",
            "content": "用户消息",
            "tool_name": "web_search",
            "request_id": "req_123",
        },
    )
    assert event["password"] == "[REDACTED]"
    assert event["content"] == "[len=4]"
    assert event["tool_name"] == "web_search"
    assert event["request_id"] == "req_123"
