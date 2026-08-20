"""Conversation title generation from the first user message."""

from zhiban.llm.base import ChatMessage, LLMAdapter

TITLE_PROMPT = "请用10个字以内总结以下用户消息作为对话标题，只输出标题本身，不要加引号或标点："


async def generate_title(llm: LLMAdapter, user_content: str) -> str:
    """Generate a short conversation title from the first user message.

    Best-effort: any failure returns an empty string so the caller can keep
    the default title without blocking the chat flow.
    """
    try:
        response = await llm.chat(
            [
                ChatMessage(role="system", content=TITLE_PROMPT),
                ChatMessage(role="user", content=user_content),
            ]
        )
    except Exception:  # noqa: BLE001 - title is best-effort
        return ""

    title = response.content.strip()
    for ch in "\"'''「」『』":
        title = title.strip(ch)
    return title[:50] if title else ""
