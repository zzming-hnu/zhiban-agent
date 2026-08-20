"""Agent prompt composition: base rules, tool rules, and memory rules."""

from zhiban.agent.prompts.base import BASE_PROMPT
from zhiban.agent.prompts.memory_rules import MEMORY_RULES
from zhiban.agent.prompts.tool_use import TOOL_USE

__all__ = ["BASE_PROMPT", "TOOL_USE", "MEMORY_RULES", "compose_system_prompt"]


def compose_system_prompt() -> str:
    """Compose the full system prompt from the three rule layers."""
    return "\n\n".join([BASE_PROMPT, TOOL_USE, MEMORY_RULES])
