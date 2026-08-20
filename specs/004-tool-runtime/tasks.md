# SPEC-004 任务清单

状态：`implemented`

本清单只在完成真实变更和验证后勾选。任务按依赖顺序排列；同一组中标注「可并行」的项目可以并行。

## T0：规格准备

- [x] `TOOL-T000` 编写 `SPEC-004` 的目标、边界、要求和验收映射。
- [x] `TOOL-T001` 实现开始时将 `spec.md` 状态改为 `in_progress`。

## T1：工具元数据与协议

- [x] `TOOL-T010` 定义 `ToolSpec`、`Permission`、`Idempotency`、`RetryPolicy`（`tools/spec.py`）。
- [x] `TOOL-T011` 定义 `ToolContext`（含 `user_id`、`run_id`、`conversation_id`）。
- [x] `TOOL-T012` 重构 `Tool` 协议：`spec` 属性 + `execute(ctx, args)` 签名。
- [x] `TOOL-T013` 定义 `operation_key` 确定性生成（`tools/ids.py`）。

## T2：Registry 重构

- [x] `TOOL-T020` 重构 `ToolRegistry`：注册 `ToolSpec` 校验、重名拒绝。
- [x] `TOOL-T021` 实现 `openai_schemas()` 由 Pydantic 生成，`additionalProperties=false`。
- [x] `TOOL-T022` 注册现有三个工具到新协议。

## T3：Executor

- [x] `TOOL-T030` 实现 `ToolExecutor.execute`：校验 → 权限 → Hook → 超时执行 → 结果截断。
- [x] `TOOL-T031` 实现 `asyncio.timeout` 超时取消。
- [x] `TOOL-T032` 实现 `safe_once` 只读工具重试。
- [x] `TOOL-T033` 实现结果截断与 `truncated` 标记。
- [x] `TOOL-T034` 实现审计（结构化日志，`tool_calls` 表接入留 SPEC-006 持久化）。

## T4：幂等

- [x] `TOOL-T040` 实现写工具 `operation_key` 生成。
- [x] `TOOL-T041` 实现同 run 相同调用检测（orchestrator 层 canonical_args 签名）。
- [x] `TOOL-T042` 实现 `canonical_args` 键顺序规范化。

## T5：Hook

- [x] `TOOL-T050` 定义 `before/after/on_error` Hook 协议（`tools/hooks.py`）。
- [x] `TOOL-T051` 在 Executor 中接入 Hook 生命周期。
- [x] `TOOL-T052` 实现 Hook 异常隔离。

## T6：SearchAdapter 与净化

- [x] `TOOL-T060` 定义 `SearchAdapter` 协议与 `SearchResult`（`tools/search/base.py`）。
- [x] `TOOL-T061` 实现 `MockSearchAdapter`（版本化固定语料）。
- [x] `TOOL-T062` 实现结果净化与来源标注（`tools/search/sanitize.py`）。
- [x] `TOOL-T063` 重构 `web_search` 工具使用 SearchAdapter。

## T7：LLM 摘要工具

- [x] `TOOL-T070` 实现 LLM 驱动的 `summary` 工具（`brief/bullets/actions`）。
- [x] `TOOL-T071` 复用 `summary_llm_*` 配置构造摘要 adapter（通过 registry 注入）。
- [x] `TOOL-T072` 实现输入校验（空/过短/超长）。

## T8：Agent 接入

- [x] `TOOL-T080` 重构 orchestrator 使用 `ToolExecutor`（替换内联执行）。
- [x] `TOOL-T081` 传递 `ToolContext`（user_id/run_id/conversation_id）。

## T9：测试

- [x] `TOOL-T090` ToolSpec/协议/registry 测试（重名拒绝、schema）。
- [x] `TOOL-T091` Executor 测试（超时、重试、截断、权限、参数校验）。
- [x] `TOOL-T092` 幂等测试（canonical_args、operation_key）。
- [x] `TOOL-T093` Hook 测试（顺序、异常隔离）。
- [x] `TOOL-T094` SearchAdapter 测试（契约、净化、注入防护）。
- [x] `TOOL-T095` summary 工具测试（LLM 生成、输入校验）。

## T10：文档与验证

- [ ] `TOOL-T100` 完成 `verification.md`。
- [ ] `TOOL-T101` 更新 `docs/progress/004-tool-runtime.md`。
- [ ] `TOOL-T102` 更新 README 与 Spec 状态。

## 完成规则

- `SPEC-TOOL-AC-001~011` 均有真实结果。
- 工具协议、Executor、幂等、审计、Hook、SearchAdapter、LLM summary 均有自动化测试证据。
- 新增工具只需 spec + 注册，不改无关模块。
- mypy strict 全绿，无 override。
