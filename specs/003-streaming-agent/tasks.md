# SPEC-003 任务清单

状态：`implemented`

本清单只在完成真实变更和验证后勾选。任务按依赖顺序排列；同一组中标注「可并行」的项目可以并行。

## T0：规格准备

- [x] `AG-T000` 编写 `SPEC-003` 的目标、边界、要求和验收映射。
- [x] `AG-T001` 确认范围（完整 P0）、compaction（包含）、摘要模型（独立配置）。
- [x] `AG-T002` 实现开始时将 `spec.md` 状态改为 `in_progress`。

## T1：数据模型与迁移

- [x] `AG-T010` 新增 `agent_runs` 表（含状态枚举、route、model、tool_rounds、error_code、时间戳）。
- [x] `AG-T011` 新增 `conversation_summaries` 表（覆盖区间、结构化 summary、token_count、model、version）。
- [x] `AG-T012` 新增同一会话单 active run 的部分唯一索引。
- [x] `AG-T013` 编写 Alembic 迁移（单 head），验证 upgrade/downgrade。

## T2：SSE 事件协议与领域事件

- [x] `AG-T020` 定义领域事件模型（`agent/events.py`）：run/message/tool 事件，含 seq/event_id/occurred_at。
- [x] `AG-T021` 实现 SSE 编解码（`conversations/stream.py`）：event type、id、data 序列化。
- [x] `AG-T022` 实现单 run 事件序号单调递增与终态互斥保证。
- [x] `AG-T023` 实现 ping 心跳预留（`sse_ping` 函数；实际心跳循环在长流中接入）。

## T3：两段式链路与 run 生命周期

- [x] `AG-T030` 重构 `POST /conversations/{id}/messages` 为两段式：事务写 user msg + assistant placeholder + run，返回 202 + run_id。
- [x] `AG-T031` 实现 `GET /runs/{run_id}/stream` SSE 端点。
- [x] `AG-T032` 实现 run 生命周期状态机（`conversations/runs.py`）。
- [x] `AG-T033` 实现同一会话单 active run 约束（`cancel_active_for_conversation` 取消中断 run）。
- [x] `AG-T034` 实现 Redis 事件缓冲（15m TTL）与 run 快照。

## T4：LLM Adapter 重构

- [x] `AG-T040` 修正 `LLMAdapter` 协议（协变类型，strict mypy 通过）。
- [x] `AG-T041` 实现错误分类与重试判定（`llm/errors.py`）。
- [x] `AG-T042` 重构 `openai_adapter.py`：`reasoning_content` 处理、指数退避重试、usage 统计、流式 tool_calls 累加。
- [x] `AG-T043` 实现主模型 + 摘要模型双 factory（`summary_llm_*` 配置）。
- [x] `AG-T044` 新增 `summary_llm_model` 等配置项与校验。

## T5：有界 Agent 循环

- [x] `AG-T050` 重构 `agent/orchestrator.py`：有界循环 + final round + 总超时，每轮流式逐 token 输出。
- [x] `AG-T051` 实现空回复/重复输出确定性兜底。
- [x] `AG-T052` 实现重复工具调用检测（canonical_args 签名 + 连续两轮进 final round）。
- [x] `AG-T053` 实现工具轮数与工具调用总数上限。
- [x] `AG-T054` 实现用户取消预留（AbortController 信号前端中断）。

## T6：Token 预算与上下文管理

- [x] `AG-T060` 实现 Token 估算与预算分配（`core/token_budget.py`，保守近似）。
- [x] `AG-T061` 实现近期窗口 + rolling summary 上下文组装（`agent/context.py`）。
- [x] `AG-T062` 实现软/硬阈值触发 compaction（`agent/compaction.py`）。
- [x] `AG-T063` 实现 rolling summary 结构化 schema 与覆盖区间记录。
- [x] `AG-T064` 实现旧工具结果折叠预留（`fold_tool_result`）。
- [x] `AG-T065` 实现单条消息超预算的错误处理预留。

## T7：错误、降级与前端对齐

- [x] `AG-T070` 实现 LLM 不可用 / 工具失败 / Redis 不可用的降级语义。
- [x] `AG-T071` 前端 `lib/api.ts` 迁移到两段式：POST messages + GET stream（含 SSE 事件解析）。
- [x] `AG-T072` 前端聊天页适配 run 状态与流式渲染。
- [x] `AG-T073` 移除旧 `/chat` 端点。

## T8：测试

- [x] `AG-T080` SSE 事件协议测试（seq 递增、终态互斥、事件类型、SSE 编解码）。
- [x] `AG-T081` 两段式消息创建测试（返回 202 + run_id + stream_url）。
- [x] `AG-T082` 有界循环测试（快路径流式、空回复兜底、无重复工具）。
- [x] `AG-T083` Token 预算 + compaction 测试（软阈值触发、短会话不触发）。
- [x] `AG-T084` LLM Adapter 测试（错误分类）。
- [x] `AG-T085` 迁移 upgrade/downgrade 测试（沿用 SPEC-002 的迁移测试框架）。

## T9：文档与验证

- [x] `AG-T090` 移除 mypy override，`llm/tools/agent` strict mypy 全绿。
- [x] `AG-T091` 移除 `pyjwt`、`passlib[bcrypt]` 依赖并同步 `uv.lock`。
- [x] `AG-T092` 完成 `verification.md`。
- [x] `AG-T093` 更新 `docs/progress/003-streaming-agent.md`。
- [x] `AG-T094` 更新 README 与 Spec 状态。

## 完成规则

- `SPEC-AG-AC-001~015` 均有真实结果。
- 迁移单 head 且可 downgrade。
- SSE 协议、两段式、有界循环、Token/compaction、错误分类均有自动化测试证据。
- mypy strict 全绿，无 override；无废弃依赖。
- 真实 Kimi K2.5 流式对话端到端可用。
- Markdown 渲染（含 XSS 防护）可用。
