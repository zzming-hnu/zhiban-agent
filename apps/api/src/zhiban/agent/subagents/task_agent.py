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
from zhiban.tools.builtin.current_time import CurrentTimeTool
from zhiban.tools.registry import ToolRegistry

# ruff: noqa: E501  # task-agent prompt text intentionally uses long lines
_TASK_SUBAGENT_SYSTEM = """你是任务子代理，负责用户的待办与提醒管理。

你可以使用以下工具：
- current_time：获取当前精确时间（返回 ISO 8601 格式，含日期、星期、时区）
- todo.create：创建待办（可选 due_at 截止时间 + timezone）
- todo.complete：标记待办完成
- reminder.create：创建提醒（必须指定 remind_at 具体时间 + timezone，可选 recurrence 重复规则）
- reminder.cancel：取消提醒

## 铁律：工具未成功执行，不得声称已完成
「已创建」「已设置好」「已提醒」等完成态描述，**只能**在工具返回 ok=True 后才能说。
如果工具调用失败或没调用，严禁任何完成态描述，直接告诉用户「需要你提供更明确的信息」。

## 关于截止时间 / 提醒时间
1. **用户用相对时间表达时，必须先调用 current_time 获取当前精确时间，再据此推算具体 remind_at/due_at，严禁回问用户「当前大概时间」。** 例如：「三分钟后」「半小时后」「一小时后」→ 先拿当前时间，再加对应时长，得到具体时刻。
2. **用户用「今天/明天/后天/下周X」等相对日期时，也要先调用 current_time 确定「今天」是几号、星期几，再推算目标日期**，不要凭模型自身知识猜（模型的日期知识可能过时）。
3. 用户完全没说任何时间信息时，**不要**假设或编造时间，也不要硬塞当前时间；此时回问「请告诉我希望的（截止/提醒）时间」。
4. 推断模糊时间（如「下午3点」「明天9点」）时，按用户时区（默认 Asia/Shanghai）推断为具体时间（ISO 8601 带时区）。
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
        registry.register(CurrentTimeTool())
        registry.register(TodoCreateTool(self._todo_service))
        registry.register(TodoCompleteTool(self._todo_service))
        registry.register(ReminderCreateTool(self._reminder_service))
        registry.register(ReminderCancelTool(self._reminder_service))
        return registry
