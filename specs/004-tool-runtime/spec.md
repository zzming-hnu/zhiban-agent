# SPEC-004：工具运行时（Registry、Executor 与搜索摘要）

## 1. 元数据

| 字段 | 值 |
|---|---|
| Spec ID | `SPEC-004` |
| 状态 | `implemented` |
| 版本 | `1.0.0` |
| 创建日期 | 2026-08-18 |
| 最后更新 | 2026-08-18 |
| 实施阶段 | `06-implementation-plan.md` 阶段 4 |
| 前置依赖 | `SPEC-003`（流式聊天与有界 Agent，状态 `implemented`） |
| 后续依赖 | `SPEC-005`（记忆系统）、`SPEC-006`（待办与提醒） |

来源：

- [产品需求](../../docs/01-product-requirements.md)：`FR-018`、`FR-070~075`、`FR-080~085`、`FR-121~123/126/127`、`NFR-006/007/012~014`、`AC-040~044/061/062`、`PRD SEC-008~010`。
- [记忆、上下文与工具设计](../../docs/04-memory-context-tool-design.md)：第 8 节。
- [技术架构](../../docs/03-technical-architecture.md)：第 6 节。
- [参考源码分析](../../docs/02-reference-code-analysis.md)：工具协议、Hook、结构化错误、身份守卫。
- [实施计划](../../docs/06-implementation-plan.md)：阶段 4。
- [测试计划](../../docs/07-test-plan.md)：`TOOL-001~039`、`SEC-020~029`、`E2E-040~049`。

## 2. 背景与问题

`SPEC-003` 已建立有界 Agent 循环，工具通过一个最小 `Tool` Protocol（只有 `name/description/input_schema/execute`）接入。这套最小协议存在以下缺口：

1. **无工具元数据**：没有 `permission`（read/write/sensitive）、`timeout`、`idempotency`、`retry_policy`、`result_token_budget` 等声明，Agent 无法据此约束工具行为。
2. **无独立 Executor**：工具执行直接写在 orchestrator 里，没有统一的超时、重试、幂等、审计、结果截断职责边界。
3. **无权限模型**：所有工具一视同仁，无法区分只读/写/敏感操作，敏感操作无确认机制。
4. **无幂等保障**：写工具重复调用可能产生重复副作用，没有 `operation_key` 落库去重。
5. **无审计记录**：`tool_calls` 表已建但未使用，工具调用无开始/终态/耗时/错误码记录。
6. **无 Hook 生命周期**：没有 before/after/on_error 钩子，无法做限流、观测、参数规范化。
7. **搜索工具是硬编码 Mock**：`MockSearchTool` 直接内联固定结果，未抽象 SearchAdapter 契约，未做结果净化与 Prompt Injection 防护。
8. **summary 工具是规则切分**：`SummaryTool` 用字符串截断/规则切分，未调用 LLM，与"摘要"语义不符。

本 Spec 按文档第 8 节定义，把最小工具协议升级为完整的工具运行时。

## 3. 目标

1. 建立 `ToolSpec` 元数据与 `Tool` 协议：权限、超时、幂等、重试、结果预算。
2. 建立独立的 `ToolExecutor`：参数校验、超时、重试、幂等、结果截断、审计。
3. 建立权限模型：`read`/`write`/`sensitive`，敏感操作确认预留。
4. 建立幂等机制：写工具 `operation_key` 落库，重复调用不产生重复副作用。
5. 建立工具调用审计：`tool_calls` 表记录开始/终态/耗时/错误码。
6. 建立 Hook 生命周期：`before/after/on_error`。
7. 抽象 `SearchAdapter` 契约，Mock 与真实 provider 实现同一接口，结果净化 + 来源标注 + Prompt Injection 防护。
8. 用 LLM 实现 `summary` 工具（真正的摘要，而非规则切分）。
9. 保留三个现有工具，纳入新协议；`current_time`、`web_search`、`summary` 全部升级。

## 4. 非目标

本步骤不实现：

- 待办、提醒工具（`SPEC-006`）。
- 记忆工具（`SPEC-005`）。
- 真实搜索 provider 的接入（本 Spec 只定义 `SearchAdapter` 契约 + Mock 实现，真实 provider 放 P1）。
- 任意代码执行、插件系统、用户自定义工具。
- 多 Agent 或工具编排 DSL。
- 敏感操作确认的完整 UI 闭环（只做 `permission=sensitive` 的标记与拒绝执行，确认流程放 `SPEC-007`）。

## 5. 已确认决策

| 决策 | 内容 |
|---|---|
| 范围 | 按文档 §8 完整实现工具运行时 + SearchAdapter 抽象 + LLM summary |
| 搜索 | 只定义契约 + Mock 实现，真实 provider 延后 |
| 敏感操作确认 | 只做标记与拒绝，完整确认 UI 放 SPEC-007 |

## 6. 目标目录契约

在 `SPEC-003` 基础上，本 Spec 新增/重构：

```text
apps/api/src/zhiban/
├── tools/
│   ├── spec.py          # ToolSpec、Permission、Idempotency、RetryPolicy
│   ├── base.py          # Tool 协议、ToolContext、ToolResult
│   ├── registry.py      # ToolRegistry（lifespan 构建、重名拒绝）
│   ├── executor.py      # ToolExecutor（校验/超时/重试/幂等/截断/审计）
│   ├── hooks.py         # before/after/on_error Hook
│   ├── ids.py           # operation_key 确定性生成
│   ├── builtin/
│   │   ├── current_time.py   # current_time.get
│   │   ├── web_search.py     # web.search（SearchAdapter 抽象）
│   │   └── summary.py        # summary.create（LLM 摘要）
│   └── search/
│       ├── base.py      # SearchAdapter 协议、SearchResult
│       ├── mock.py      # MockSearchAdapter（固定语料）
│       └── sanitize.py  # 结果净化、来源标注、注入防护
└── db/
    └── models.py        # tool_calls 表（已建，接入审计）
```

## 7. 规范要求

### 7.1 工具元数据与协议

- **SPEC-TOOL-001** 每个工具 MUST 声明 `ToolSpec`：`name`、`description`、`input_model`、`permission`、`timeout_seconds`、`idempotency`、`retry_policy`、`result_token_budget`。
- **SPEC-TOOL-002** `permission` MUST 为 `read`/`write`/`sensitive` 之一。
- **SPEC-TOOL-003** `idempotency` MUST 为 `none`/`optional`/`required` 之一；写工具 MUST 为 `required`。
- **SPEC-TOOL-004** `retry_policy` MUST 为 `never`/`safe_once` 之一；只读无副作用工具 MAY 为 `safe_once`。
- **SPEC-TOOL-005** 工具 MUST 通过 `input_model` 的 Pydantic schema 校验参数，`additionalProperties=false`；模型返回参数 MUST 再次校验，不能把原始 JSON 直接传给业务函数。
- **SPEC-TOOL-006** 工具 MUST NOT 接受可信 `user_id` 参数；`user_id` 只来自 `ToolContext`（认证主体）。

### 7.2 Registry

- **SPEC-TOOL-010** `ToolRegistry` MUST 在应用 lifespan 构建后冻结，重名注册 MUST 失败。
- **SPEC-TOOL-011** Registry MUST 提供 `get(name)`、`list_names()`、`openai_schemas()`。
- **SPEC-TOOL-012** `openai_schemas()` MUST 由 Pydantic 自动生成 JSON Schema，`additionalProperties=false`。
- **SPEC-TOOL-013** Registry MUST NOT 把内部/管理工具暴露给普通用户。

### 7.3 Executor

- **SPEC-TOOL-020** `ToolExecutor.execute` MUST 依次：参数校验 → 权限检查 → Hook before → 超时执行 → Hook after → 结果截断；异常走 Hook on_error。
- **SPEC-TOOL-021** 每个工具执行 MUST 受 `asyncio.timeout(spec.timeout_seconds)` 约束，超时 MUST 取消并返回 `tool_timeout`。
- **SPEC-TOOL-022** 只读 `safe_once` 工具对网络超时/5xx MUST 重试一次，遵守退避。
- **SPEC-TOOL-023** 参数/权限/schema 错误 MUST NOT 重试。
- **SPEC-TOOL-024** 写工具 MUST 具备持久化幂等键，重试仅在该键已落库且结果未知时进行。
- **SPEC-TOOL-025** 工具结果超过 `result_token_budget` MUST 截断并标记 `truncated=true`。
- **SPEC-TOOL-026** 工具输出含不可序列化值时 MUST 转为受控错误。

### 7.4 幂等与重复调用

- **SPEC-TOOL-030** 写工具 MUST 计算 `operation_key = SHA-256(user_id + run_id + tool_name + canonical_args)`。
- **SPEC-TOOL-031** 同 run 内相同 `operation_key` 的调用，第二次 MUST 返回缓存结果不执行。
- **SPEC-TOOL-032** 数据库 `tool_calls.idempotency_key` 唯一约束 MUST 保证跨请求重复不产生重复副作用。
- **SPEC-TOOL-033** 相同键但参数不同 MUST 返回冲突（409 语义，内部以错误码表达）。
- **SPEC-TOOL-034** `canonical_args` MUST 规范化键顺序，检测语义相同的重复调用。

### 7.5 审计

- **SPEC-TOOL-040** 每次工具调用 MUST 写 `tool_calls` 记录：`user_id`、`run_id`、`round`、`tool_name`、`arguments_hash`、`permission_level`、`idempotency_key`、`status`、`started_at`、`finished_at`、`error_code`、`retry_count`。
- **SPEC-TOOL-041** 参数与结果日志 MUST 按字段脱敏，不记录敏感参数全文。
- **SPEC-TOOL-042** 审计记录 MUST 含 `duration_ms` 与结果是否截断。

### 7.6 Hook

- **SPEC-TOOL-050** Hook 生命周期 MUST 为 `before_tool → execute → after_tool`，异常走 `on_tool_error`。
- **SPEC-TOOL-051** Hook MUST 只读请求上下文、拒绝调用、规范化参数/结果或记录观测，MUST NOT 隐式改写跨请求全局状态。
- **SPEC-TOOL-052** Hook 异常 MUST 被隔离，不阻断主流程（记录后继续）。

### 7.7 Search Adapter 与净化

- **SPEC-TOOL-060** `SearchAdapter` MUST 定义统一契约：`search(query, max_results) -> list[SearchResult]`，`SearchResult` 含 `title`、`url`、`snippet`、`source`、`published_at`。
- **SPEC-TOOL-061** Mock 与真实 provider MUST 实现同一契约，结果 MUST 可追溯到固定语料/来源。
- **SPEC-TOOL-062** 搜索结果 MUST 净化：剥离 HTML/脚本/隐藏文本，保留来源 URL。
- **SPEC-TOOL-063** 搜索正文 MUST 视为不可信数据，MUST NOT 改变工具权限、读取 secret、修改 system prompt、触发高风险工具。
- **SPEC-TOOL-064** 搜索超时/不可用 MUST 明确说明未完成检索，不伪造结果，不把模型知识伪装成"刚刚搜索到"。
- **SPEC-TOOL-065** Mock 搜索 MUST 在界面持续标识"演示数据"。

### 7.8 LLM 摘要工具

- **SPEC-TOOL-070** `summary` 工具 MUST 调用 LLM 生成摘要，而非规则切分。
- **SPEC-TOOL-071** 摘要 MUST 支持 `brief`/`bullets`/`actions` 三种格式。
- **SPEC-TOOL-072** 输入为空、过短、超长 MUST 明确提示，不静默处理。
- **SPEC-TOOL-073** 摘要 MUST NOT 宣称包含未成功读取的内容。

### 7.9 契约与测试

- **SPEC-TOOL-080** 新增工具 MUST 只需实现 `ToolSpec` + 注册，不修改无关模块。
- **SPEC-TOOL-081** 工具调用 MUST 有开始/终态/耗时/错误码，可通过 `run_id` + `tool_call_id` 定位。
- **SPEC-TOOL-082** 契约测试 MUST 覆盖：工具名唯一、schema 可序列化、Mock 与真实 adapter 同契约。

## 8. 行为与数据流

### 8.1 工具执行链路

```text
模型 tool_calls
  -> Registry.get(name)
  -> Executor.execute(ctx, args)
     -> 参数 Pydantic 校验
     -> 权限检查
     -> Hook before
     -> asyncio.timeout(execute)
     -> Hook after
     -> 结果截断
  -> 审计写 tool_calls
  -> ToolResult 回填 Agent
```

### 8.2 幂等流程

```text
写工具调用
  -> operation_key = SHA-256(user_id + run_id + tool_name + canonical_args)
  -> 查 tool_calls.idempotency_key
  -> 命中：返回缓存结果
  -> 未命中：落库 + 执行 + 回写结果
```

## 9. 错误与降级语义

| 场景 | 行为 |
|---|---|
| 未知工具 | `unknown_tool`，不执行 |
| 参数非法 | `tool_invalid_argument`，不执行副作用 |
| 权限不足 | `tool_permission_denied` |
| 工具超时 | `tool_timeout`，取消执行 |
| 只读工具网络错误 | `safe_once` 重试一次后失败 |
| 写工具重复 | 返回缓存结果，不重复副作用 |
| 搜索不可用 | 明确说明未完成检索，不伪造 |
| 摘要 LLM 失败 | 返回摘要失败，不伪装成功 |

## 10. 安全与隐私

- 工具参数与结果日志按字段脱敏。
- 搜索结果视为不可信数据，不提升权限、不执行网页指令。
- 敏感操作（`permission=sensitive`）默认拒绝执行，需确认（确认流程 SPEC-007）。
- `user_id` 只来自认证上下文，工具不接受模型传入的归属。
- 审计记录不含密钥、完整敏感正文。

## 11. 验收标准

| 验收 ID | 必须结果 | 测试映射 |
|---|---|---|
| SPEC-TOOL-AC-001 | ToolSpec 元数据完整，权限/超时/幂等/重试声明正确 | `TOOL-001~005` |
| SPEC-TOOL-AC-002 | Registry 重名拒绝，schema 可序列化 | `TOOL-001/002` |
| SPEC-TOOL-AC-003 | Executor 超时/重试/截断正确 | `TOOL-006~018` |
| SPEC-TOOL-AC-004 | 写工具幂等：重复调用不产生重复副作用 | `TOOL-013~015` |
| SPEC-TOOL-AC-005 | 重复调用签名检测语义相同 | `TOOL-019~021` |
| SPEC-TOOL-AC-006 | 审计记录含开始/终态/耗时/错误码 | `TOOL-018` |
| SPEC-TOOL-AC-007 | Hook 顺序与异常隔离 | 本 Spec 专项测试 |
| SPEC-TOOL-AC-008 | SearchAdapter 契约统一，结果净化 + 来源标注 | `TOOL-037~039`、`SEC-029/034` |
| SPEC-TOOL-AC-009 | 搜索不可用不伪造结果 | `E2E-042~044`、`AC-041` |
| SPEC-TOOL-AC-010 | summary 用 LLM 生成，支持三种格式 | `TOOL-037`、`FR-081` |
| SPEC-TOOL-AC-011 | 新增工具只改 spec+注册，不改无关模块 | `NFR-007`、`TOOL-028` |

## 12. 发布与回滚

- 工具协议升级是向后兼容扩展：现有三个工具的 `execute(args)` 签名迁移到 `execute(ctx, args)`。
- 迁移：`tool_calls` 表已存在，本 Spec 接入审计写入，不新增表（如需新字段用迁移补齐）。
- 回滚 = 恢复 orchestrator 内的直接调用；不删除数据。

## 13. 偏差与决策

| 决策 | 说明 |
|---|---|
| 真实搜索 provider 延后 | 本 Spec 只定义 SearchAdapter 契约 + Mock，真实 provider P1 接入不改 Agent 核心 |
| 敏感操作确认延后 | `permission=sensitive` 标记与拒绝执行，完整确认 UI 放 SPEC-007 |
| summary 改 LLM | 原 SummaryTool 用规则切分，与"摘要"语义不符；改用 LLM，符合 FR-081 |

## 14. 开放问题

- summary 用主模型还是独立 summary 模型（倾向复用 `summary_llm_*` 配置）。
- Mock 搜索固定语料的版本化与来源标注格式。
- 工具结果截断的 token 估算与 `result_token_budget` 默认值校准。
