"""Mock LLM adapter for development and demo mode."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from zhiban.llm.base import ChatMessage, LLMChunk, LLMResponse

MOCK_RESPONSES: dict[str, str] = {
    "你好": "你好！我是知伴，你的个人 AI 助理。有什么可以帮助你的吗？",
    "记住": "好的，我已经记住了！下次对话中我会参考这个信息。",
    "搜索": (
        "我找到了一些相关信息：\n\n"
        "1. AI Agent 工程化最佳实践\n"
        "2. 个人 AI 助理的设计与实现\n"
        "3. PostgreSQL pgvector 语义检索指南\n\n"
        "你可以让我对其中某条内容做更详细的总结。"
    ),
    "总结": (
        "以下是文本的要点总结：\n\n"
        "- 第一条要点\n"
        "- 第二条要点\n"
        "- 第三条要点\n\n"
        "如需更详细的总结，请提供更多文本。"
    ),
    "时间": ("当前时间是 2026年8月18日，具体时间请使用时间工具获取更精确的信息。"),
}

DEFAULT_RESPONSE = (
    "你好！我是知伴，一个具备记忆能力的个人 AI 助理。"
    "我可以帮你管理待办事项、检索信息、生成摘要，还能记住你的偏好和习惯。"
    "有什么想聊的吗？"
)


class MockLLMAdapter:
    model: str = "mock"

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        response_text = self._generate(messages)
        return LLMResponse(content=response_text)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        response_text = self._generate(messages)
        words = list(response_text)
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            chunk = "".join(words[i : i + chunk_size])
            yield LLMChunk(delta=chunk)
            await asyncio.sleep(0.03)
        yield LLMChunk(delta="", finish_reason="stop")

    def _generate(self, messages: list[ChatMessage]) -> str:
        if not messages:
            return DEFAULT_RESPONSE
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_user_msg = msg.content
                break

        for keyword, response in MOCK_RESPONSES.items():
            if keyword in last_user_msg:
                return response

        if "tool" in last_user_msg.lower() or "工具" in last_user_msg:
            return (
                "我目前支持以下工具：\n"
                "- web_search：搜索网络信息\n"
                "- summary：生成文本摘要\n"
                "- current_time：获取当前时间\n\n"
                "你可以直接告诉我你想做什么，我会自动选择合适的工具。"
            )

        return (
            f"收到你的消息：「{last_user_msg[:100]}」\n\n"
            "作为知伴，我会基于对话上下文和记忆为你提供个性化的回答。"
            "你可以尝试：\n"
            "- 让我搜索一些信息\n"
            "- 让我总结一段文字\n"
            "- 问我当前时间\n"
            "- 聊聊任何话题"
        )
