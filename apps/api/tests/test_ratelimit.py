"""Unit tests for in-process rate limiting fallback (no external services)."""

from zhiban.auth.ratelimit import RateRule, _check_in_process


def test_in_process_limiter_allows_within_limit() -> None:
    rule = RateRule(key="test:within", limit=3, window_seconds=60)
    assert _check_in_process(rule)
    assert _check_in_process(rule)
    assert _check_in_process(rule)
    # 4th request within the window is rejected.
    assert not _check_in_process(rule)


def test_in_process_limiter_uses_distinct_keys() -> None:
    rule_a = RateRule(key="test:a", limit=1, window_seconds=60)
    rule_b = RateRule(key="test:b", limit=1, window_seconds=60)
    assert _check_in_process(rule_a)
    # Different key is unaffected.
    assert _check_in_process(rule_b)
