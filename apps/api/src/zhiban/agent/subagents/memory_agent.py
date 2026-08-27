"""Memory sub-agent: recall + CRUD of user memories.

The orchestrator routes memory-related requests here. This agent reuses the
existing ``MemoryService`` and memory tools (add/list/update/delete), owns the
memory operation lifecycle, and returns a structured summary to the main agent.
"""

from zhiban.agent.subagents.base import ToolCallingSubAgent
from zhiban.llm.base import LLMAdapter
from zhiban.memory.service import MemoryService
from zhiban.memory.tools import (
    MemoryAddTool,
    MemoryConsolidateTool,
    MemoryDeleteTool,
    MemoryListTool,
    MemoryUpdateTool,
)
from zhiban.tools.registry import ToolRegistry

_MEMORY_SUBAGENT_SYSTEM = """你是记忆子代理，负责用户记忆的召回与增删改查。

你可以使用以下工具：
- memory.list：列出用户记忆（每项含 id/type/category/content）
- memory.add：新增一条记忆
- memory.update：修改记忆（需先 list 拿到 id）
- memory.delete：删除记忆（需先 list 拿到 id）
- memory.consolidate：整理记忆（去除冗余、消解矛盾）

规则：
1. 基于用户输入判断要做什么：查看、新增、修改、删除、整理，或检索记忆来回答。
2. 需要先拿到记忆 id 的操作（update/delete），先调用 memory.list。
3. 用户说「整理记忆」「记忆太乱」等时，调用 memory.consolidate。
4. 完成操作后，用一句话总结「你做了什么、结果是什么」。
5. 只输出最终总结，不要暴露工具调用过程。"""


class MemoryAgent(ToolCallingSubAgent):
    """Specialized sub-agent for memory recall and CRUD."""

    name = "memory"
    system_prompt = _MEMORY_SUBAGENT_SYSTEM

    def __init__(self, service: MemoryService, llm: LLMAdapter) -> None:
        self._service = service
        super().__init__(llm)

    def build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(MemoryListTool(self._service))
        registry.register(MemoryAddTool(self._service, self._llm))
        registry.register(MemoryUpdateTool(self._service))
        registry.register(MemoryDeleteTool(self._service))
        registry.register(MemoryConsolidateTool(self._service))
        return registry
