# 知伴 · 系统架构

> 反映当前真实实现（2026-08-20）。

## 1. 总体拓扑

知伴是一个**模块化单体**，部署上只有 `api` 和 `worker` 两种进程，代码按领域分包。

```
浏览器 (Next.js :3000)
   │  REST / SSE
   ▼
FastAPI (api :8000) ──────────────► PostgreSQL + pgvector（唯一事实源）
   │  ├─ Auth（session + HttpOnly Cookie）
   │  ├─ Conversation（会话/消息）
   │  ├─ Agent Runtime（有界 ReAct + 路由）
   │  ├─ Memory / Todo / Search（领域）
   │  ├─ Tool Registry / Executor
   │  └─ LLM Adapter ──► DeepSeek
   │
   │  写入 jobs / outbox
   ▼
Worker（独立进程，无 HTTP）
   ├─ 记忆抽取 / Embedding
   ├─ 摘要压缩
   ├─ 提醒调度（周期提醒 + 邮件投递）
   └─ jobs/outbox 消费（租约、重试、幂等）

Redis：限流、短租约锁、SSE 事件缓冲、任务通知（可降级到 PG 轮询）
SearXNG：自建搜索服务（localhost:8888，可降级 Mock）
```

## 2. 模块边界

| 模块 | 职责 | 关键点 |
|---|---|---|
| `auth` | 登录、会话、认证主体 | session + HttpOnly Cookie、Argon2id、CSRF、限流 |
| `conversation` | 会话/消息、run 生命周期 | 两段式聊天、cursor 分页、幂等 |
| `agent` | 有界 ReAct、路由、subagent、事件 | 主 Agent + Subagent 架构 |
| `memory` | 候选提取、校验、决策、检索、flush | 确定性规则优先，Embedding + lexical 混合检索 |
| `tools` | Registry、Executor、权限、幂等、审计 | ToolSpec 声明式定义 |
| `todo/reminder` | 待办、提醒、周期规则、投递 | 时区处理、幂等投递 |
| `search` | 搜索抽象、结果净化、引用 | SearXNG adapter + Mock 兜底 |
| `llm` | Chat/Embedding 适配器、重试 | 多模型支持、reasoning 控制 |
| `jobs` | 任务租约、重试、Outbox | at-least-once + 幂等消费 |
| `notifications` | 邮件提醒（SMTP） | 端口自适应（465 SSL / 587 STARTTLS） |

## 3. 主 Agent - Subagent 架构

### 3.1 设计原则

- **主 Agent（Orchestrator）** 只负责：路由决策 + 管理 ReAct 生命周期 + 组织最终回复。
- **Subagent** 干具体事务，返回**结构化摘要**（`SubAgentResult: summary + data + citations`），内部推理不进主 Agent 上下文。
- **路由由 LLM 在 ReAct 中动态决定**，代码不硬编码路由。

### 3.2 Subagent 清单

| Subagent | 职责 | 拥有的工具 |
|---|---|---|
| `MemoryAgent`（memory） | 记忆召回 + 增删改查 | `memory.list/add/update/delete` |
| `TaskAgent`（task） | 待办 + 提醒 | `todo.create/complete`、`reminder.create/cancel` |
| `SearchAgent`（search） | 联网检索 | `web_search` |
| 主 Agent 兜底 | 闲聊/解释 + 轻量只读 | `current_time`、`summary` |

### 3.3 路由流程

```
用户消息
  → 主 Agent 调用 route(llm, user_input)
     → LLM 返回 {"target": "memory"|"task"|"search"|"general"|"none", "reason": "..."}
  → target=memory/task/search：委派对应 subagent
       subagent 内部有界 mini-ReAct（≤3 轮工具调用）
       返回结构化摘要
       主 Agent 基于摘要流式生成最终回复
  → target=none/general：主 Agent 自己 ReAct（调 current_time/summary）
```

### 3.4 关键文件

- `agent/subagent.py`：`SubAgent` 协议 + `SubAgentContext` + `SubAgentResult`
- `agent/router.py`：`route()` 路由决策（LLM 返回 JSON）
- `agent/subagents/base.py`：`ToolCallingSubAgent` 基类（有界 mini-ReAct）
- `agent/subagents/{memory,task,search}_agent.py`：三个 subagent
- `conversations/runs_router.py`：`_build_subagent()` 根据路由构建 subagent

## 4. 有界 ReAct 循环

主 Agent 的 ReAct 循环是**有界**的，防止失控：

```
加载上下文 → 路由 → 委派 subagent 或 主 Agent ReAct
主 Agent ReAct：
  for round in 1..4:
    流式调用 LLM（带工具 schema）
    ├─ 无 tool_calls → 得到最终文本 → 结束
    ├─ 有 tool_calls → 执行工具 → 回填结果 → 下一轮
  final round（tool_choice=none，强制收尾）
```

**终止条件**（任一满足即停）：
- 模型返回非空文本且无工具调用
- 达到 `max_tool_rounds=4`，进入 final round
- 达到 `agent_total_timeout_seconds=60`
- 用户取消
- 连续两次相同 `tool_name + args`（重复检测）
- 工具调用总数达到 8
- 连续两次空回复 → 确定性兜底文案

## 5. 聊天两段式 + SSE

避免断线重连导致消息重复创建：

```
① POST /conversations/{id}/messages（带 Idempotency-Key）
   → 事务创建 user message + assistant placeholder + run
   → 返回 {message_id, assistant_message_id, run_id, stream_url}

② GET /runs/{run_id}/stream（SSE）
   → 事件流：run.started → agent.thinking → tool.call.* → message.delta → message.completed → run.completed
```

**SSE 事件协议**（`agent/events.py`）：

| 事件 | 含义 |
|---|---|
| `run.started` | 开始（带 `delegated` 标记是否委派） |
| `agent.thinking` | 每轮思考开始（带 round） |
| `message.delta` | 文本增量 |
| `tool.call.started` | 工具调用开始（带 arguments） |
| `tool.call.completed/failed` | 工具结果 |
| `message.completed` | 最终正文（权威） |
| `run.completed/failed` | 终止 |

## 6. 记忆系统架构

### 6.1 两层分类

- **技术型 `memory_type`**（8 类）：identity/preference/habit/person/event/task/temporary/communication
- **用户 `category`**（4 类）：basic_info（基本信息）/ communication_taboo（沟通禁忌）/ communication_preference（沟通偏好）/ other

### 6.2 确定性映射

`identity/person/event → basic_info`，`habit/task/temporary → other`，`communication/preference → 由 LLM 判断`。代码强制，避免 LLM 误判。

### 6.3 记忆生命周期

```
用户消息 → 异步记忆抽取（Worker job）
  → LLM 提取候选（严格 JSON）
  → 确定性校验（敏感词/置信度/证据/值格式）
  → 决策（去重/冲突/新增）
  → 持久化（含 Embedding）
```

### 6.4 检索注入（借鉴小 Q 模式）

- **explicit 记忆**：每次查询全量注入 `[用户的核心信息与偏好]`
- **implicit 记忆**：按相关性召回 `[与当前问题相关的用户记忆]`
- Embedding 不可用时降级为 lexical（ILIKE）检索

## 7. 提醒与任务

### 7.1 待办

- 状态机：`pending → done / cancelled`
- 支持 `due_at`（截止时间）+ `timezone`

### 7.2 提醒

- 状态机：`scheduled → delivering → delivered / cancelled`
- **单次 + 周期**（`recurrence`: none/daily/weekly）
- **周期提醒**：到点投递后 Worker 自动生成下一次（`_schedule_next_occurrence`）
- 三路触达：站内 toast（前端轮询）+ 浏览器通知（Notification API）+ 邮件（SMTP）

### 7.3 投递链路

```
Worker scan_and_deliver（每 30s）
  → 扫描 due 提醒
  → mark_delivered
  → 周期提醒：生成下一次 scheduled
  → 发邮件（SMTP 已启用时）
```

## 8. 后台任务（jobs/outbox）

- PostgreSQL `jobs` 表 + `outbox_events` 表是任务事实源
- Worker 通过**租约**（lease）+ **重试**（指数退避 1s/5s/30s/2m/10m）+ **幂等消费**处理
- Redis 只承载 `job_id` 通知，不可用时降级到 PG 轮询

## 9. 数据隔离与安全

- **认证**：session + HttpOnly Cookie（弃用 JWT）
- **密码**：Argon2id 哈希
- **隔离**：所有 Repository 查询强制 `user_id` 作用域（跨用户测试验证）
- **CSRF**：double-submit token
- **幂等**：`Idempotency-Key` 防止重复创建
- **Prompt Injection 防护**：role=user 内容不当指令执行
- **SSRF 规避**：搜索走自建 SearXNG，不抓任意 URL
- **日志脱敏**：密码/Token/Cookie/正文只记长度

## 10. 降级与兜底

| 依赖故障 | 降级行为 |
|---|---|
| LLM 不可用 | run.failed，不伪装成功 |
| Embedding 不可用 | lexical 检索降级 |
| SearXNG 不可用 | 切 Mock / 说明无法获取实时信息 |
| Redis 不可用 | SSE 只保留当前连接，Worker 用 PG 轮询 |
| SMTP 未配置 | 跳过邮件，仅站内提醒 |
| 记忆抽取失败 | 聊天正常完成，后台补偿 |
