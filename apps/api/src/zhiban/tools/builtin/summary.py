"""Summary tool — generates a structured summary via an LLM."""

from pydantic import BaseModel, Field

from zhiban.llm.base import ChatMessage, LLMAdapter
from zhiban.tools.base import ToolContext, ToolResult
from zhiban.tools.spec import ToolSpec

_SUMMARY_PROMPTS = {
    "brief": "请用简洁的语言概括以下文本的要点，控制在几句话以内：",
    "bullets": "请用要点列表（每行以 - 开头）总结以下文本的核心内容：",
    "actions": "请从以下文本中提取可执行的行动项，用要点列表输出：",
}


class SummaryInput(BaseModel):
    model_config = {"extra": "forbid"}

    text: str = Field(description="需要总结的文本内容", min_length=1, max_length=10000)
    style: str = Field(
        default="brief",
        description="摘要风格：brief=简短概述, bullets=要点列表, actions=行动项",
    )


class SummaryTool:
    spec = ToolSpec(
        name="summary",
        description="对给定文本生成摘要。当用户要求总结、概括或提取要点时使用。",
        input_model=SummaryInput,
        permission="read",
        timeout_seconds=20.0,
        idempotency="optional",
        retry_policy="never",
    )

    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    async def execute(self, ctx: ToolContext, args: SummaryInput) -> ToolResult:
        style = args.style if args.style in _SUMMARY_PROMPTS else "brief"
        prompt = _SUMMARY_PROMPTS[style]
        try:
            response = await self._llm.chat(
                [
                    ChatMessage(
                        role="system",
                        content="你是文本摘要助手，忠实概括原文，不添加原文没有的信息。",
                    ),
                    ChatMessage(role="user", content=f"{prompt}\n\n{args.text}"),
                ]
            )
        except Exception:  # noqa: BLE001 - summary failure is non-fatal
            return ToolResult(
                ok=False,
                summary="摘要生成失败",
                error_code="summary_failed",
                retryable=True,
            )

        summary = response.content.strip()
        return ToolResult(
            ok=True,
            data={
                "summary": summary,
                "original_length": len(args.text),
                "style": style,
            },
            summary=f"已生成{style}格式摘要",
        )
