"""Task sub-agent: todo + reminder lifecycle.

The orchestrator routes task/reminder requests here. This agent owns the
todo/reminder tools (create/complete/cancel), executes the write operations,
and returns a structured summary to the main agent.
"""

from zhiban.agent.subagents.base import ToolCallingSubAgent
from zhiban.llm.base import LLMAdapter
from zhiban.todos.service import ReminderService, TodoService
from zhiban.todos.tools import (
    ReminderCancelTool,
    ReminderCreateTool,
    TodoCompleteTool,
    TodoCreateTool,
)
from zhiban.tools.registry import ToolRegistry

# ruff: noqa: E501  # task-agent prompt text intentionally uses long lines
_TASK_SUBAGENT_SYSTEM = """你是任务子代理，负责用户的待办与提醒管理。

你可以使用以下工具：
- todo.create：创建待办（可选 due_at 截止时间 + timezone）
- todo.complete：标记待办完成
- reminder.create：创建提醒（必须指定 remind_at 具体时间 + timezone，可选 recurrence 重复规则）
- reminder.cancel：取消提醒

## 铁律：工具未成功执行，不得声称已完成
「已创建」「已设置好」「已提醒」等完成态描述，**只能**在工具返回 ok=True 后才能说。
如果工具调用失败或没调用，严禁任何完成态描述，直接告诉用户「需要你提供更明确的信息」。

## 关于截止时间 / 提醒时间
1. 用户没说具体时间时，**不要**假设或编造时间，也不要硬塞当前时间。
2. 如果用户意图是「创建待办」但没说具体时间：回问「请告诉我希望的截止时间」，不要无截止时间建待办（除非用户明确不关心）。
3. 如果用户意图是「创建提醒」但没说具体时间：同样回问时间。
4. 推断相对时间时（如「明天9点」「下午3点」），按用户时区（默认 Asia/Shanghai）推断为具体时间。
5. **重要**：如果用户说的「每天/每周 X 点」里的 X 点，在今天已经过去了，就设为**明天的 X 点**（比如现在已过早上7点，用户说「每天早上7点」，第一次提醒应设为「明天早上7点」，recurrence="daily"）。

## 周期提醒（recurrence 参数）
1. 用户说「每天早上7点」「每天提醒我」→ recurrence="daily"。
2. 用户说「每周一上午」「每周提醒」→ recurrence="weekly"。
3. 用户没说周期，只说一次具体时间 → recurrence="none"（单次）。
4. 如果用户说「每天提醒我，持续一周」之类 → 同时给出 recurrence_end_at（ISO 8601）。

## 输出规则
1. 完成后用一句话总结「你做了什么、结果是什么」，并说明重复规则（如「已创建每天 7 点的提醒」）。
2. 工具未调用成功时，明确告诉用户需要补什么信息。
3. 只输出最终总结，不要暴露工具调用过程。"""


class TaskAgent(ToolCallingSubAgent):
    """Specialized sub-agent for todo and reminder management."""

    name = "task"
    system_prompt = _TASK_SUBAGENT_SYSTEM

    def __init__(
        self, todo_service: TodoService, reminder_service: ReminderService, llm: LLMAdapter
    ) -> None:
        self._todo_service = todo_service
        self._reminder_service = reminder_service
        super().__init__(llm)

    def build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(TodoCreateTool(self._todo_service))
        registry.register(TodoCompleteTool(self._todo_service))
        registry.register(ReminderCreateTool(self._reminder_service))
        registry.register(ReminderCancelTool(self._reminder_service))
        return registry
