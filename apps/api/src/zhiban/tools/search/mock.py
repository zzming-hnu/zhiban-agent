"""Mock search adapter: deterministic, versioned fixed corpus."""

from zhiban.tools.search.base import SearchResult

# Fixed, traceable corpus for demo/test mode. Clearly not a live search.
_CORPUS: list[SearchResult] = [
    SearchResult(
        title="AI Agent 工程化最佳实践",
        url="https://example.com/ai-agent-best-practices",
        snippet=(
            "本文总结了 AI Agent 在生产环境中的工程化要点，"
            "包括记忆管理、工具调用稳定性和上下文控制。"
        ),
        source="技术博客",
    ),
    SearchResult(
        title="个人 AI 助理的设计与实现",
        url="https://example.com/personal-ai-assistant",
        snippet="从零开始构建一个具备记忆能力的个人 AI 助理，涵盖前后端架构、数据模型和部署方案。",
        source="技术博客",
    ),
    SearchResult(
        title="PostgreSQL pgvector 语义检索指南",
        url="https://example.com/pgvector-guide",
        snippet="使用 PostgreSQL 的 pgvector 扩展实现高效的语义向量检索，适合中小规模应用。",
        source="数据库文档",
    ),
    SearchResult(
        title="大语言模型工具调用（Function Calling）机制",
        url="https://example.com/llm-function-calling",
        snippet="解释大语言模型如何通过结构化工具调用完成检索、计算与外部动作，并讨论其稳定性边界。",
        source="技术博客",
    ),
    SearchResult(
        title="多轮对话的上下文管理策略",
        url="https://example.com/context-management",
        snippet="介绍滚动摘要、Token 预算与记忆检索如何协同控制长对话的上下文规模。",
        source="技术博客",
    ),
]


class MockSearchAdapter:
    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        # Keyword-based selection for a deterministic, demo-friendly result.
        lowered = query.lower()
        if "pgvector" in lowered or "向量" in query or "语义" in query:
            ordered = [_C for _C in _CORPUS if "pgvector" in _C.title]
        elif "上下文" in query or "context" in lowered:
            ordered = [_C for _C in _CORPUS if "上下文" in _C.title]
        else:
            ordered = list(_CORPUS)
        return ordered[: max(1, min(max_results, len(ordered)))]
