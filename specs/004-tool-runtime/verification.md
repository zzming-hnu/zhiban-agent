# SPEC-004 验证记录

## 1. 当前状态

| 字段 | 值 |
|---|---|
| Spec 状态 | `implemented` |
| 实现状态 | T0~T9 完成，T10 文档收尾 |
| 验证结论 | 工具协议、Executor、幂等、Hook、SearchAdapter、LLM summary 均通过自动化测试 |
| 记录日期 | 2026-08-19 |

## 2. 环境

工作目录：`/Users/zzming/work`

真实基础设施：PostgreSQL `zhiban`（开发库）+ `zhiban_test`（测试库）、Redis。

关键版本：Python 3.12.13、FastAPI 0.141.1。

## 3. 测试结果

命令：

```bash
.venv/bin/pytest -q
```

退出码：`0`

结果：

```text
73 passed, 2 warnings
```

新增 17 个工具运行时测试：

- `test_tool_runtime.py`（12）：registry 重名拒绝、schema 生成、executor 校验/超时/执行错误/敏感拒绝、canonical_args、operation_key、Hook 顺序与隔离。
- `test_search_and_summary.py`（5）：sanitize 去 HTML/截断/保留 URL、mock search 确定性、web_search 工具净化与来源、summary LLM 生成、空输入校验。

## 4. 质量门禁

命令：

```bash
.venv/bin/mypy apps/api/src
.venv/bin/ruff check .
.venv/bin/ruff format --check apps/api scripts
```

结果：

```text
mypy: Success, 68 source files（无 override）
ruff check: All checks passed
ruff format: 98 files already formatted
```

## 5. 偏差记录

| 偏差 | 说明 |
|---|---|
| 审计落库延后 | `ToolExecutor` 用结构化日志记录审计字段（tool_name/permission/ok/error_code/duration_ms/truncated）；`tool_calls` 表的持久化写入延后到 SPEC-006（待办/提醒引入写工具时一并做，因为当前三个工具都是只读的） |
| 幂等去重走 orchestrator 层 | 当前三个工具都是只读（`idempotency=none/optional`），无写工具；`operation_key` 已实现，写工具的去重落库在 SPEC-006 引入写工具时接入 |
| summary 用 summary_llm | summary 工具通过 registry 注入 `summary_llm`（复用 `summary_llm_*` 配置），与主对话模型分离 |
| 敏感操作确认延后 | `permission=sensitive` 标记与拒绝执行（`tool_confirmation_required`），完整确认 UI 放 SPEC-007 |
| 真实搜索 provider 延后 | 只定义 `SearchAdapter` 契约 + Mock 实现 |

## 6. 验收状态

| 验收 ID | 状态 | 证据 |
|---|---|---|
| SPEC-TOOL-AC-001 | 通过 | ToolSpec 完整，权限/超时/幂等/重试声明 |
| SPEC-TOOL-AC-002 | 通过 | test_tool_runtime（重名拒绝、schema） |
| SPEC-TOOL-AC-003 | 通过 | test_tool_runtime（超时/执行错误/敏感拒绝） |
| SPEC-TOOL-AC-004 | 部分 | operation_key 实现；写工具去重落库延后 SPEC-006 |
| SPEC-TOOL-AC-005 | 通过 | canonical_args 键序规范化 |
| SPEC-TOOL-AC-006 | 部分 | 结构化日志审计；tool_calls 表持久化延后 SPEC-006 |
| SPEC-TOOL-AC-007 | 通过 | Hook 顺序与异常隔离测试 |
| SPEC-TOOL-AC-008 | 通过 | SearchAdapter 契约 + sanitize + mock |
| SPEC-TOOL-AC-009 | 通过 | 搜索不可用返回 `search_unavailable`，不伪造 |
| SPEC-TOOL-AC-010 | 通过 | summary 用 LLM，三种格式 |
| SPEC-TOOL-AC-011 | 通过 | 工具只需 spec + 注册（registry 注入依赖） |

## 7. 未执行项

- `tool_calls` 表持久化审计写入（延后 SPEC-006，引入写工具时一并做）。
- 写工具幂等落库去重（当前无写工具）。
- 敏感操作确认 UI（SPEC-007）。
- GitHub 远程 CI（目录未初始化 Git）。
