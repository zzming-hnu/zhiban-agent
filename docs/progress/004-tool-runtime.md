# 过程记录 004：工具运行时

## 1. 状态

| 字段 | 值 |
|---|---|
| 对应 Spec | [SPEC-004](../../specs/004-tool-runtime/spec.md) |
| 当前阶段 | SPEC-004 实现与验证完成 |
| Spec 状态 | `implemented` |
| 实现状态 | T0~T9 完成 |
| 最后更新 | 2026-08-19 |

## 2. 本次完成

1. 建立 `ToolSpec` 元数据（权限/超时/幂等/重试/结果预算）与 `Tool` 协议（`execute(ctx, args)`）。
2. 建立 `ToolContext`（user_id 来自认证主体，不接受模型传入）。
3. 建立 `ToolExecutor`：参数校验、权限检查、超时、重试、结果截断、Hook、审计日志。
4. 建立幂等原语：`operation_key` + `canonical_args`（键序规范化）。
5. 建立 Hook 生命周期（before/after/on_error）与异常隔离。
6. 抽象 `SearchAdapter` 契约 + `MockSearchAdapter`（版本化固定语料）+ 结果净化（去 HTML/注入防护）。
7. 用 LLM 重构 `summary` 工具（三种格式，复用 summary_llm）。
8. 重构 orchestrator 使用 `ToolExecutor` + `ToolContext`。
9. 新增 17 个工具运行时测试，总计 73 个后端测试全绿。

## 3. 关键决策

### 3.1 审计落库延后

当前三个工具（current_time/web_search/summary）都是只读，`ToolExecutor` 用结构化日志记录审计字段。`tool_calls` 表的持久化写入延后到 SPEC-006（引入写工具时一并做）。

### 3.2 summary 用独立 summary_llm

summary 工具通过 registry 注入 `summary_llm`（复用 `summary_llm_*` 配置），与主对话模型分离，可用更快的模型。

### 3.3 SearchResult 用 slots dataclass

`SearchResult` 是 `@dataclass(frozen=True, slots=True)`，无 `__dict__`，序列化用 `dataclasses.asdict` 而非 `__dict__`。

### 3.4 Tool Protocol 的逆变 TInput

`TInput` 只出现在 `execute` 的参数位置（逆变），需 `contravariant=True`，否则 mypy 报 Protocol 不变错误。

## 4. 文件变更

新增：

- `apps/api/src/zhiban/tools/spec.py`
- `apps/api/src/zhiban/tools/executor.py`
- `apps/api/src/zhiban/tools/hooks.py`
- `apps/api/src/zhiban/tools/ids.py`
- `apps/api/src/zhiban/tools/search/base.py`
- `apps/api/src/zhiban/tools/search/mock.py`
- `apps/api/src/zhiban/tools/search/sanitize.py`
- `apps/api/src/zhiban/tools/search/__init__.py`
- `apps/api/src/zhiban/tools/builtin/web_search.py`
- `apps/api/tests/test_tool_runtime.py`
- `apps/api/tests/test_search_and_summary.py`

重构：

- `apps/api/src/zhiban/tools/base.py`（ToolSpec + ToolContext + execute(ctx, args)）
- `apps/api/src/zhiban/tools/registry.py`（create_registry 注入依赖）
- `apps/api/src/zhiban/tools/builtin/current_time.py`
- `apps/api/src/zhiban/tools/builtin/summary.py`（LLM 驱动）
- `apps/api/src/zhiban/agent/orchestrator.py`（ToolExecutor + ToolContext）

删除：

- `apps/api/src/zhiban/tools/builtin/mock_search.py`（被 web_search + search/mock 取代）

## 5. 验证摘要

- 后端测试：73 passed（新增 17）。
- mypy：68 source files，无 override。
- ruff / format：全通过。

## 6. 已知问题

1. `tool_calls` 表持久化审计写入延后 SPEC-006。
2. 写工具幂等落库去重延后 SPEC-006（当前无写工具）。
3. 敏感操作确认 UI 延后 SPEC-007。
4. 真实搜索 provider 延后 P1。

## 7. 下一步

进入 SPEC-005（记忆系统）：候选提取、校验、检索、治理与 Memory Flush。
