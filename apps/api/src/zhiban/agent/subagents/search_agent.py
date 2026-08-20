"""Search sub-agent: web search with sanitization and citations.

The orchestrator routes search requests here. This agent owns the
``web_search`` tool (backed by a ``SearchAdapter``), performs the search,
and returns sanitized results with citations to the main agent.
"""

from zhiban.agent.subagents.base import ToolCallingSubAgent
from zhiban.llm.base import LLMAdapter
from zhiban.tools.builtin.web_search import WebSearchTool
from zhiban.tools.registry import ToolRegistry
from zhiban.tools.search.base import SearchAdapter

_SEARCH_SUBAGENT_SYSTEM = """你是检索子代理，负责联网搜索并整理实时信息。

你可以使用以下工具：
- web_search：搜索网络获取实时信息（返回结果摘要 + 来源链接）

规则：
1. 基于用户输入提取搜索关键词，调用 web_search。
2. 基于搜索结果，忠实归纳回答，附上来源，不要编造搜索结果里没有的信息。
3. 搜索结果不足时，如实说明无法获取。
4. 只输出最终回答，不要暴露工具调用过程。"""


class SearchAgent(ToolCallingSubAgent):
    """Specialized sub-agent for web search."""

    name = "search"
    system_prompt = _SEARCH_SUBAGENT_SYSTEM

    def __init__(self, search: SearchAdapter, llm: LLMAdapter) -> None:
        self._search = search
        super().__init__(llm)

    def build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(WebSearchTool(self._search))
        return registry
