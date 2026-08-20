# 过程记录 003：流式聊天、LLM Adapter 与有界 Agent

## 1. 状态

| 字段 | 值 |
|---|---|
| 对应 Spec | [SPEC-003](../../specs/003-streaming-agent/spec.md) |
| 当前阶段 | SPEC-003 实现与验证完成 |
| Spec 状态 | `implemented` |
| 实现状态 | T0~T9 完成 |
| 最后更新 | 2026-08-18 |

## 2. 本次完成

1. 新增 `agent_runs`、`conversation_summaries` 表与迁移 `20260818_0004`。
2. 建立 SSE 事件协议（`agent/events.py`）：seq 递增、终态互斥、稳定事件类型。
3. 建立两段式聊天链路：`POST messages` 返回 202 + run_id，`GET /runs/{run_id}/stream` SSE。
4. 建立 run 生命周期状态机与断线重连（Last-Event-ID 补发 + 快照恢复）。
5. 重构 LLM Adapter：错误分类、指数退避重试、`reasoning_content` 过滤、流式 tool_calls 累加。
6. 建立主模型 + 摘要模型双 factory（`summary_llm_*` 独立配置）。
7. 重构有界 Agent 循环：每轮流式逐 token 输出、final round、空回复/重复兜底。
8. 实现 Token 预算（保守近似）与 compaction（软/硬阈值触发 rolling summary）。
9. 前端迁移到两段式 + Markdown 渲染（react-markdown + rehype-sanitize 防 XSS）。
10. 移除 mypy override（60 source files strict 全绿），清理 pyjwt/passlib[bcrypt] 依赖。
11. 新增 21 个后端测试 + 3 个前端 Markdown 测试，总计 54 + 5 全绿。

## 3. 关键决策

### 3.1 快路径改流式

原超前实现的快路径用非流式 `chat` 一次性拿答案，导致"视觉上没有流式感"。改为每轮都用 `chat_stream` 逐 token 输出，`LLMChunk` 增加 `tool_calls` 字段以感知流式中的工具调用。

### 3.2 reasoning_content 过滤

Kimi K2.5 是推理模型，流式先输出 `reasoning_content`（思考链）再输出 `content`（最终答案）。adapter 只取 `content`，思考过程既不输出给用户，也不进日志。

### 3.3 中断 run 自动取消

同一会话残留 `queued` run 会触发 `uq_agent_runs_active_conversation` 唯一约束。`start_run` 前先 `cancel_active_for_conversation`，把中断的旧 run 标记为 cancelled。

### 3.4 Token 估算用保守近似

不引入 tiktoken（OpenAI BPE 与 Kimi 不一致）。中文按字符数、英文按词数，乘安全系数。预留 tokenizer 接口，后续实测校准。

### 3.5 Markdown 渲染纳入本 Spec

模型天然输出 Markdown，不渲染是半成品。引入 react-markdown + remark-gfm + rehype-sanitize（剥离原始 HTML 防 XSS），链接 `noopener noreferrer`。

### 3.6 摘要模型独立配置

主模型 kimi-k2.5 是推理模型（慢/贵），rolling summary 用更快模型更经济。`summary_llm_model` 独立配置，默认回退主模型。

## 4. 文件变更

新增：

- `apps/api/migrations/versions/20260818_0004_agent_runs_summaries.py`
- `apps/api/src/zhiban/agent/events.py`
- `apps/api/src/zhiban/agent/compaction.py`
- `apps/api/src/zhiban/agent/context.py`
- `apps/api/src/zhiban/conversations/runs.py`
- `apps/api/src/zhiban/conversations/runs_router.py`
- `apps/api/src/zhiban/conversations/stream.py`
- `apps/api/src/zhiban/core/token_budget.py`
- `apps/api/src/zhiban/llm/errors.py`
- `apps/web/components/markdown.tsx`
- `apps/api/tests/test_token_budget.py`
- `apps/api/tests/test_agent_events.py`
- `apps/api/tests/test_llm_errors.py`
- `apps/api/tests/test_orchestrator.py`
- `apps/api/tests/test_compaction.py`
- `apps/web/tests/markdown.test.tsx`

重构：

- `apps/api/src/zhiban/agent/orchestrator.py`（有界循环 + 流式）
- `apps/api/src/zhiban/llm/base.py`（LLMChunk 加 tool_calls）
- `apps/api/src/zhiban/llm/openai_adapter.py`（reasoning_content + 重试 + 流式 tool_calls）
- `apps/api/src/zhiban/llm/factory.py`（双 adapter）
- `apps/api/src/zhiban/llm/mock.py`
- `apps/api/src/zhiban/tools/base.py`（泛型 Tool Protocol）
- `apps/api/src/zhiban/tools/registry.py`
- `apps/api/src/zhiban/conversations/router.py`（两段式）
- `apps/api/src/zhiban/conversations/service.py`（start_run）
- `apps/api/src/zhiban/conversations/schemas.py`（RunAccepted）
- `apps/api/src/zhiban/core/config.py`（LLM/agent/context 配置）
- `apps/api/src/zhiban/api/router.py`（挂载 runs_router）
- `apps/api/src/zhiban/db/models.py`（AgentRun/ConversationSummary）
- `apps/api/src/zhiban/db/redis.py`（client 访问器）
- `apps/web/lib/api.ts`（两段式 + SSE 解析）
- `apps/web/app/chat/page.tsx`（Markdown 渲染）
- `apps/web/app/globals.css`（markdown-body 样式）
- `pyproject.toml`（移除 mypy override、依赖清理）
- `apps/api/tests/test_conversations_api.py`、`test_isolation.py`（适配两段式）

## 5. 验证摘要

- 迁移：upgrade/downgrade/current 全通过，单 head `20260818_0004`。
- 后端测试：54 passed（新增 21）。
- 前端测试：5 passed（新增 3 Markdown）。
- mypy：60 source files，无 override。
- ruff / eslint / prettier / tsc：全通过。
- 真实 Kimi K2.5 流式对话 + Markdown 渲染端到端可用。

## 6. 已知问题

1. 断线重连（Last-Event-ID）代码已实现，但未做浏览器级断线 E2E 验证。
2. ping 心跳函数已实现，但未接入长流的心跳循环（单次 run 流时长短，暂不强制）。
3. GitHub 远程 CI 未执行（目录未初始化 Git）。
4. 取消广播的跨进程实现放 SPEC-007。

## 7. 下一步

进入 SPEC-004（工具运行时）：Tool Registry/Executor 完整重构、参数校验、权限、超时、幂等、审计、Mock Search 规范化。
