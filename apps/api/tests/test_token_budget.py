"""Unit tests for token estimation and budget allocation (no database)."""

from zhiban.core.token_budget import TokenBudget, build_token_budget, estimate_tokens


def test_empty_text_estimates_zero() -> None:
    assert estimate_tokens("") == 0


def test_chinese_estimates_by_character() -> None:
    # CJK chars count ~1 token each.
    assert estimate_tokens("你好") >= 4


def test_english_estimates_by_word() -> None:
    # Latin words count ~1.3 tokens each.
    assert estimate_tokens("hello world") >= 5


def test_longer_text_estimates_more_tokens() -> None:
    short = estimate_tokens("你好")
    long_text = estimate_tokens("你好世界" * 500)
    assert long_text > short


def test_budget_partitions_context_window() -> None:
    budget = build_token_budget(
        32768, output_reserve=4096, summary_budget=1800, tool_results_budget=2200
    )
    assert isinstance(budget, TokenBudget)
    # Total input budget + output reserve must not exceed the window.
    assert budget.total_input_budget + budget.output_reserve <= 32768
    assert budget.recent_window > 0
    assert budget.system > 0
    assert budget.rolling_summary == 1800
    assert budget.tool_results == 2200


def test_budget_rejects_too_small_window() -> None:
    import pytest

    with pytest.raises(ValueError):
        build_token_budget(100, output_reserve=4096, summary_budget=1800, tool_results_budget=2200)
