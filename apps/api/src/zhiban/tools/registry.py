"""Tool registry: register and look up tools by name, reject duplicates."""

from typing import Any

from zhiban.llm.base import LLMAdapter
from zhiban.tools.base import Tool
from zhiban.tools.search.base import SearchAdapter


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool[Any]] = {}

    def register(self, tool: Tool[Any]) -> None:
        name = tool.spec.name
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> Tool[Any] | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def openai_schemas(self) -> list[dict[str, Any]]:
        """Generate OpenAI-compatible function calling schemas.

        DeepSeek (and some other providers) restrict ``function.name`` to the
        pattern ``^[a-zA-Z0-9_-]+$`` — dots are not allowed. Internally we use
        dotted names (``memory.add``, ``todo.create``) so the agent and audit
        logs read naturally. When exporting to the LLM we replace ``.`` with
        ``_``; callers must reverse the mapping via :meth:`resolve_tool_name`
        when receiving tool calls back from the model.
        """
        schemas: list[dict[str, Any]] = []
        for tool in self._tools.values():
            schema = tool.spec.input_model.model_json_schema()
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": _to_provider_name(tool.spec.name),
                        "description": tool.spec.description,
                        "parameters": schema,
                    },
                }
            )
        return schemas

    def resolve_tool_name(self, provider_name: str) -> str | None:
        """Reverse-map a provider-facing tool name back to the internal name."""
        for tool in self._tools.values():
            if _to_provider_name(tool.spec.name) == provider_name:
                return tool.spec.name
        # Already an internal name (defensive fallback).
        if provider_name in self._tools:
            return provider_name
        return None


def _to_provider_name(internal_name: str) -> str:
    """Sanitize an internal tool name for the LLM provider's schema."""
    return internal_name.replace(".", "_")


def create_registry(
    *,
    summary_llm: LLMAdapter | None = None,
    search: SearchAdapter | None = None,
    include_search: bool = True,
) -> ToolRegistry:
    """Create and populate the default tool registry.

    ``summary_llm`` and ``search`` are injectable so tests can use fakes; when
    omitted, the summary tool falls back to a no-op and search uses the mock.

    ``include_search=False`` omits ``web_search`` from the registry — used when
    search is delegated to the SearchAgent instead of the main agent.
    """
    from zhiban.tools.builtin.current_time import CurrentTimeTool
    from zhiban.tools.builtin.summary import SummaryTool
    from zhiban.tools.builtin.web_search import WebSearchTool
    from zhiban.tools.search.mock import MockSearchAdapter

    registry = ToolRegistry()
    registry.register(CurrentTimeTool())

    if include_search:
        search_adapter = search if search is not None else MockSearchAdapter()
        registry.register(WebSearchTool(search_adapter))

    if summary_llm is not None:
        registry.register(SummaryTool(summary_llm))

    return registry
