"""Memory candidate extraction via LLM (strict JSON output)."""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from zhiban.llm.base import ChatMessage, LLMAdapter

EXTRACTOR_VERSION = "v1"


class ExtractedCandidate(BaseModel):
    """LLM extractor output.

    ``source_message_ids`` uses the integer indices emitted by the LLM (0-based
    within the extraction batch); the caller maps them back to real message
    UUIDs before persisting.
    """

    model_config = ConfigDict(extra="forbid")

    memory_type: Literal[
        "identity", "preference", "habit", "person", "event", "task", "temporary", "communication"
    ]
    category: Literal["basic_info", "communication_taboo", "communication_preference", "other"] = (
        "other"
    )
    # The primary fact, a single natural-language statement (e.g. "用户不喜欢吃辣").
    # This replaces the fragile subject/predicate/value triple split.
    fact: str = Field(min_length=1, max_length=500)
    # Legacy structured fields, kept optional for backward compatibility.
    # The extractor no longer needs to fill them; they default to empty.
    subject: str = Field(default="", max_length=80)
    predicate: str = Field(default="", max_length=80)
    value: str = Field(default="", max_length=500)
    negated: bool = False
    source_message_ids: list[int] = Field(min_length=1, max_length=8)
    evidence_quote: str = Field(min_length=1, max_length=240)
    confidence: float = Field(ge=0, le=1)
    importance: float = Field(ge=0, le=1)
    valid_until: str | None = None


_EXTRACTION_SYSTEM = (
    "你是记忆候选提取器。从用户消息中识别值得长期保存的稳定信息，输出严格 JSON 数组。\n"
    "\n"
    "允许的记忆类型：identity（身份）、preference（偏好）、habit（习惯）、person（人物）、\n"
    "event（事件）、task（任务）、temporary（临时）、communication（交互规则）。\n"
    "\n"
    "每条候选还必须给出面向用户的 category 分类，取值如下：\n"
    "- basic_info（基本信息）：身份、职业、相关人物、重要事件等稳定背景信息。\n"
    "- communication_taboo（沟通禁忌）：用户不希望/禁止的沟通方式\n"
    "（如「不要用 emoji」「别叫我老师」）。\n"
    "- communication_preference（沟通偏好）：用户希望/喜欢的沟通方式\n"
    "（如「回答简洁」「用通俗语言」）。\n"
    "- other（其他）：不属于以上三类的信息。\n"
    "\n"
    "字段说明：\n"
    "- memory_type：记忆的技术类型，**只能取上面列出的 8 个英文值之一**\n"
    "（identity/preference/habit/person/event/task/temporary/communication）。\n"
    "  **严禁把 category 的值（如 basic_info、communication_preference）填到这里**。\n"
    "- category：面向用户的分类，只能取 basic_info / communication_taboo /\n"
    "  communication_preference / other 之一。\n"
    "- fact：**一条完整、自然、通顺的事实陈述**（这是核心字段，务必填好）。\n"
    "  用一句话说清楚这条记忆，主语固定用「用户」，不要拆成碎片、不要套用旧记忆原文。\n"
    "  示例：\n"
    "  - 「我不吃辣」→ fact=\"用户不喜欢吃辣\"\n"
    "  - 「我爱喝咖啡」→ fact=\"用户喜欢喝咖啡\"\n"
    "  - 「我住在北京」→ fact=\"用户住在北京\"\n"
    "  ❌ 错误：fact=\"用户 喜欢 吃辣\"（不要用空格拆字段，写一句通顺的话）\n"
    "  ❌ 错误：fact=\"用户 喜欢吃 用户 不喜欢吃 辣\"（不要嵌套、不要重复主语）\n"
    "\n"
    "规则：\n"
    "1. 只从「用户」说的话提取，不要把助手说的话当作用户记忆。\n"
    "2. 一次性问题、寒暄、验证码、密码、令牌、敏感凭据一律不提取。\n"
    "3. 每条候选必须有 fact、memory_type、category、evidence_quote（原文证据，\n"
    "必须能在用户消息中找到）、confidence（0~1）、importance（0~1）。\n"
    "4. source_message_ids 用消息在输入中的编号（从 0 开始）。\n"
    "5. 同一个语义只提取一条，不要拆成多条。\n"
    "6. 没有值得保存的信息时输出空数组 []。\n"
    "7. 只输出 JSON 数组，不要任何其它文字。"
)


def _extraction_user_prompt(messages: list[tuple[int, str]]) -> str:
    lines = ["以下是本轮的用户消息（编号从 0 开始）："]
    for idx, content in messages:
        lines.append(f"[{idx}] {content}")
    lines.append("请提取值得长期保存的记忆候选，输出 JSON 数组。")
    return "\n".join(lines)


def _parse_candidates(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


async def extract_candidates(
    llm: LLMAdapter, messages: list[tuple[int, str]]
) -> list[ExtractedCandidate]:
    """Extract memory candidates from user messages via the LLM.

    The returned candidates keep the LLM's integer ``source_message_ids``
    (batch-local indices); the caller maps them to real message UUIDs.
    """
    try:
        response = await llm.chat(
            [
                ChatMessage(role="system", content=_EXTRACTION_SYSTEM),
                ChatMessage(role="user", content=_extraction_user_prompt(messages)),
            ]
        )
    except Exception:  # noqa: BLE001 - extraction is best-effort
        return []

    candidates: list[ExtractedCandidate] = []
    for item in _parse_candidates(response.content):
        try:
            candidates.append(ExtractedCandidate.model_validate(item))
        except Exception:  # noqa: BLE001 - skip invalid candidates
            continue
    return candidates


def detect_explicit_request(user_content: str) -> bool:
    """Detect an explicit "remember this" request in the user message."""
    markers = ("记住", "记一下", "请记得", "以后按", "别忘了", "帮我记", "请记录", "记下来")
    return any(marker in user_content for marker in markers)
