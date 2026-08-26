# ruff: noqa: E501  # router prompt text intentionally uses long lines
"""Main-agent routing: decide (via the LLM) whether and where to delegate.

The orchestrator owns the ReAct lifecycle. At the start of each turn it asks
the router whether the current user request should be delegated to a
sub-agent. The router makes this decision with a single lightweight LLM call,
returning a structured target (or ``none`` when the orchestrator should
answer directly).

Only the decision is surfaced to the orchestrator; the sub-agent's internal
reasoning never enters the main context.
"""

from dataclasses import dataclass

from zhiban.llm.base import ChatMessage, LLMAdapter

# Known sub-agent names the router may select. Adding a new sub-agent means
# appending its name here and its entry to ROUTER_PROMPT.
KNOWN_TARGETS = ("memory", "task", "search", "general")


_ROUTER_SYSTEM = """你是路由决策器。判断当前用户请求是否应委派给某个子代理处理。

可用子代理：
- memory：记忆子代理。负责记忆的召回、增加、修改、删除。当用户要求记住/忘记/修改某件事，或需要检索用户的历史记忆来回答时，路由到它。
- task：任务子代理。负责待办与提醒的创建、完成、取消。当用户要求「记个待办」「明天9点提醒我」「我的待办」时，路由到它。
- search：检索子代理。负责联网搜索、查实时信息、查最新事实、查外部知识。当用户要求「搜一下」「查一下」「介绍一下最近/最新」「现在什么新闻」「有什么新动态/新进展」等，需要获取网络上实时或时效性信息时，路由到它。
- general：通用子代理。负责普通闲聊、解释、改写等不需要专业能力、也不需要实时信息的请求。

规则：
1. 只输出一个 JSON 对象，形如 {"target": "memory" | "task" | "search" | "general" | "none", "reason": "..."}。
2. target 为 "none" 表示不需要委派，由主代理直接回答。
3. 涉及记忆（记住/忘记/改主意/查看记忆/回忆）必须路由到 memory。
4. 涉及待办/提醒必须路由到 task。
5. 涉及联网搜索、实时/最新信息、或需要核实外部事实（如某产品、开源项目、新闻事件的最新情况）时必须路由到 search。即使用户没有明确说"搜一下"，只要问题涉及"最近、最新、现在、新动态、新进展、有哪些、有没有"等时效性或事实核查诉求，也应路由到 search。
6. 只有纯粹的闲聊、概念解释、常识问答等不依赖实时信息的问题，才路由到 general 或 none。
7. 只输出 JSON，不要任何其它文字。"""


@dataclass(frozen=True, slots=True)
class RouteDecision:
    target: str  # "memory" | "general" | "none"
    reason: str


def _parse_decision(raw: str) -> RouteDecision:
    import json

    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return RouteDecision(target="none", reason="parse error")
    target = parsed.get("target", "none") if isinstance(parsed, dict) else "none"
    if target not in KNOWN_TARGETS and target != "none":
        target = "none"
    reason = parsed.get("reason", "") if isinstance(parsed, dict) else ""
    return RouteDecision(target=target, reason=str(reason)[:200])


async def route(llm: LLMAdapter, user_input: str) -> RouteDecision:
    """Decide the target sub-agent (or none) for a user request."""
    try:
        response = await llm.chat(
            [
                ChatMessage(role="system", content=_ROUTER_SYSTEM),
                ChatMessage(role="user", content=user_input),
            ]
        )
    except Exception:  # noqa: BLE001 - routing is best-effort; fall back to none
        return RouteDecision(target="none", reason="router unavailable")
    return _parse_decision(response.content)
