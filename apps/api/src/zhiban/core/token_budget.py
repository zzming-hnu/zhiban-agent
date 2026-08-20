"""Conservative token estimation and context budget allocation.

No external tokenizer dependency: Chinese is estimated by character count and
Latin text by word count, multiplied by a safety factor. The estimator is a
deliberate approximation — the spec records this and leaves a hook to swap in a
real tokenizer (e.g. tiktoken) later if needed.
"""

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*")


def estimate_tokens(text: str) -> int:
    """Conservative token estimate for mixed Chinese/English text.

    - CJK characters count as ~1 token each.
    - Latin words count as ~1.3 tokens each.
    - A small per-string overhead is added.
    """
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin_words = len(_WORD_RE.findall(text))
    # Non-CJK, non-word characters (punctuation, whitespace) are cheap.
    others = len(text) - cjk - sum(len(w) for w in _WORD_RE.findall(text))
    return int(cjk + latin_words * 1.3 + others * 0.3 + 4)


@dataclass(frozen=True, slots=True)
class TokenBudget:
    """A per-section token budget derived from the model context window."""

    output_reserve: int
    tool_schema: int
    system: int
    rolling_summary: int
    retrieved_memories: int
    recent_window: int
    current_user: int
    tool_results: int

    @property
    def total_input_budget(self) -> int:
        return (
            self.tool_schema
            + self.system
            + self.rolling_summary
            + self.retrieved_memories
            + self.recent_window
            + self.current_user
            + self.tool_results
        )


def build_token_budget(
    context_window: int,
    *,
    output_reserve: int,
    summary_budget: int,
    tool_results_budget: int,
) -> TokenBudget:
    """Allocate the context window across sections with fixed proportions.

    Mirrors the budget table in 04-memory-context-tool-design.md §7.2.
    """
    remaining = context_window - output_reserve
    if remaining <= 0:
        raise ValueError("context window too small for output reserve")

    return TokenBudget(
        output_reserve=output_reserve,
        tool_schema=int(remaining * 0.09),
        system=int(remaining * 0.067),
        rolling_summary=summary_budget,
        retrieved_memories=int(remaining * 0.024),
        recent_window=int(remaining * 0.488),
        current_user=int(remaining * 0.061),
        tool_results=tool_results_budget,
    )
