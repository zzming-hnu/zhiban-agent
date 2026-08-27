# 知伴 · 技术实现

> 反映当前真实实现（2026-08-20）。每个小节描述「怎么实现的」+「关键文件」。

## 1. 工程结构

```
apps/
  api/                          # 后端（FastAPI）
    src/zhiban/
      agent/                    # 有界 ReAct + 路由 + subagent
        prompts/                # 三层 prompt（base + tool_use + memory_rules）
        subagents/              # MemoryAgent / TaskAgent / SearchAgent
      auth/                     # 认证、会话、安全
      conversations/            # 会话、消息、run、SSE
      memory/                   # 记忆系统
      todos/                    # 待办、提醒
      tools/                    # 工具运行时
      workers/                  # Worker（jobs/outbox 消费）
      notifications/            # 邮件提醒
      llm/                      # LLM/Embedding 适配器
      core/                     # 配置、错误、资源、token 预算
      db/                       # ORM 模型、session
      observability/            # 日志、脱敏
    tests/                      # pytest（142 用例）
  web/                          # 前端（Next.js）
    app/                        # 页面（login/chat/memories/todos）
    components/                 # shadcn/ui 组件 + 业务组件
    lib/                        # API client、utils

packages/contracts/             # OpenAPI + TS 契约
infra/                          # Docker Compose、Dockerfile
scripts/                        # 开发脚本、seed/reset、检查
specs/                          # Spec 驱动实施文档
docs/                           # 设计文档 + 现状文档
```

## 2. 认证与隔离（SPEC-002）

### 2.1 认证方案

- **session + HttpOnly Cookie**（明确弃用 JWT）：服务端存 `AuthSession`，客户端只持 Cookie。
- 密码用 **Argon2id** 哈希（`auth/security.py`）。
- CSRF：double-submit token（`zhiban_csrf` Cookie + `X-CSRF-Token` header）。

### 2.2 用户隔离

所有 Repository 方法的第一个筛选条件都是 `user_id`，从认证主体 `Principal` 派生。例如：

```python
async def get(self, *, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
    select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,   # 强制作用域
    )
```

跨用户访问会得到 404（而非 403），避免泄露资源存在性。有 `test_cross_user_memory_isolation` 等测试验证。

### 2.3 幂等

`Idempotency-Key` header + `idempotency_records` 表：相同 key 重放返回缓存响应，不产生副作用。

## 3. 聊天与 Agent（SPEC-003）

### 3.1 两段式聊天

```
① POST /conversations/{id}/messages → 202 {run_id, stream_url}
② GET /runs/{run_id}/stream → SSE
```

### 3.2 有界 ReAct 实现

核心在 `agent/orchestrator.py` 的 `_BoundedAgent.run()`：

- `agent_max_tool_rounds=4`（可配置）
- `agent_total_timeout_seconds=60`
- `agent_final_round_timeout_seconds=15`（每个流式调用独立超时）
- 重复检测：`_canonical_args()` 生成 `sha256(tool_name + args)` 签名，命中历史则 `WARNING_DEGRADED` 转入收尾
- 空回复兜底：连续两次空输出 → `_empty_fallback()`

### 3.3 写工具确定性确认

写工具（`todo.*`/`reminder.*`/`memory.add/update/delete`）成功后，**不再额外调 LLM 生成确认语**，直接拼确定性文案「已为你处理：...」。这避免了「模型调完工具后 final round 卡住」的经典问题。

### 3.4 上下文管理

`agent/context.py` + `agent/compaction.py`：

- Token 预算：`model_context_window=32768`，soft/hard 阈值比例触发压缩
- 滚动摘要：超阈值时把最旧消息折叠为结构化 JSON 摘要（goals/decisions/open_questions/constraints/referenced_entities/tool_facts）
- 保留最近 `context_keep_recent_turns=4` 轮原文

### 3.5 流式卡死防护

`orchestrator.py` 主循环和 final round 都包了 `asyncio.timeout(15s)`，防止 LLM 流式卡住导致前端一直等待。

## 4. 工具运行时（SPEC-004）

### 4.1 ToolSpec 声明式定义

```python
spec = ToolSpec(
    name="todo.create",
    description="...",
    input_model=CreateTodoInput,   # Pydantic 模型
    permission="write",
    timeout_seconds=5.0,
    idempotency="required",
    retry_policy="never",
)
```

### 4.2 ToolExecutor 执行链

`tools/executor.py` 的 `execute()`：
1. **校验**：Pydantic `model_validate(args)`
2. **权限**：`sensitive` 工具拒绝无确认调用
3. **Before hooks**：可拒绝
4. **执行**：`asyncio.timeout` + `safe_once` 重试
5. **截断**：超 `result_token_budget` 标记 truncated
6. **After hooks** + 审计日志

### 4.3 工具名 sanitize（关键 bug 修复）

DeepSeek 要求 tool name 匹配 `^[a-zA-Z0-9_-]+$`（不允许点号），但内部工具名是 `todo.create`/`memory.add` 带点号。解决：

- `registry.openai_schemas()` 输出时 `.` → `_`
- `registry.resolve_tool_name()` 反向映射 `_` → `.`

## 5. 记忆系统（SPEC-005）

> 记忆系统经历了三期演进：一期「候选提取→校验→决策→检索→治理」闭环；二期「演化链 + 整合」；三期「自然语言 fact 范式 + 语义去重 + reconcile」。以下为三期后的最终实现。

### 5.1 自然语言 fact 范式（`memory/extractor.py`）

- LLM 输出严格 JSON 数组，核心字段是**一句自然语言 `fact`**（如「用户不喜欢吃辣」），而非易出错的 `subject/predicate/value` 三元组。
- 三元组字段降级为可选（默认空），仅向后兼容。
- 提取规则：只从用户消息提取、排除敏感信息、evidence_quote 必须能在原文找到。
- 两层分类字段：`memory_type`（8 类）+ `category`（4 类）。

### 5.2 确定性校验（`memory/validator.py`）

- 证据来源在批次内、evidence_quote 命中原文。
- 敏感内容（密码/token/验证码）不进隐式记忆。
- 置信度阈值（habit 0.80，其他 0.65）。

### 5.3 语义去重（`memory/dedup.py`）

- `fact_similarity(a, b)`：对称词法相似度（jieba），阈值 `0.80`。
- **否定极性判断**：一方含否定词（不/没/无/别/非等）而另一方不含，直接判 0——区分「喜欢吃辣」（同义，去重）与「不喜欢吃辣」（反义，保留），防止正反偏好被误合并。
- 应用场景：写入时（flush 自动提取前）+ 定期（consolidate 整合）。

### 5.4 主动记忆语义调和（`memory/reconcile.py`）

用户明确说「记住 X」时，把新 fact + 现有相关记忆（词法粗筛 top 5）喂给模型，判断四选一：

| action | 含义 |
|---|---|
| `add` | 新增 |
| `update` | 更新旧值 |
| `supersede` | 正反取代（「喜欢」→「不喜欢」） |
| `ignore` | 重复忽略 |

**模型只提议，工程层裁决**：校验 `target_id` 必须真实存在且属于该用户，否则回退 `add`，杜绝幻觉误删。

### 5.5 演化链 + 整合（`memory/service.py` + `consolidate.py`）

- 记忆冲突/正反更新时，旧值标记 `superseded` 并经 `superseded_by_id` 指向新值，保留演化历史。
- `memory.consolidate` 后台任务：确定性语义去重（Phase 1，无需 LLM）+ LLM 提议冗余/矛盾（Phase 2），自动（记忆数≥15）与主动（「整理记忆」）双触发。

### 5.6 检索（`memory/search.py`）

- **混合检索**：向量（pgvector cosine）+ lexical（jieba/BM25）+ 时间衰减。
- Embedding 不可用 → 纯 lexical 降级。

### 5.7 记忆注入（`runs_router.py` `_inject_retrieved_memories`）

- explicit 记忆：全量注入 `[用户的核心信息与偏好（务必遵循）]`。
- implicit 记忆：按相关性召回 `[与当前问题相关的用户记忆（仅供参考）]`。
- 注入时附带演化历史（「此前为：X」），支持「你之前……现在……」的时间追问。

### 5.8 Memory Flush

压缩前先把稳定记忆 flush 到记忆库（`memory/flush.py`），通过 Worker job 异步执行；写入前做语义去重，跳过显式请求消息。

## 6. 待办与提醒（SPEC-006 + 周期扩展）

### 6.1 时区处理

- `todos/timezone.py`：`to_utc()` / `format_absolute()` / `validate_timezone()`
- 默认 `Asia/Shanghai`

### 6.2 周期提醒（2026-08-20 新增）

数据模型：`recurrence`（none/daily/weekly）+ `recurrence_end_at`。

Worker 投递后自动生成下一次（`workers/reminder_jobs.py`）：

```python
async def _schedule_next_occurrence(repo, reminder):
    if reminder.recurrence == "none": return
    next_at = next_occurrence(reminder.remind_at, reminder.recurrence)  # +1天/+1周
    if reminder.recurrence_end_at and next_at > reminder.recurrence_end_at: return
    await repo.create(... dedupe_key=_recurring_dedupe_key(reminder, next_at) ...)
```

### 6.3 三路提醒触达

1. **站内 toast**：前端 `reminder-toast.tsx` 轮询 `pending-notifications`
2. **浏览器通知**：Notification API（登录后请求权限）
3. **邮件**：`notifications/email.py`（SMTP，端口 465 自动用 SMTP_SSL）

## 7. LLM 适配（多模型）

### 7.1 多模型支持（`llm/factory.py`）

- `LLM_MODELS` 配置（逗号分隔）+ `/models` 端点
- 前端选择模型 → 传 `model` → 存 `run.model` → stream 端点读 `run.model` 构建 adapter
- `available_models()` 白名单校验

### 7.2 Reasoning 控制

- `llm_reasoning_effort` 配置（low/medium/high），透传给 provider
- `openai_adapter.py` 的 `_iter_chunks()` 过滤 `reasoning_content`，只返回 `content`（推理模型的思考过程不发给客户端）

### 7.3 重试策略

- 首字节前网络错误/429/5xx：指数退避 + 抖动，最多 2 次
- 已发送正文后不重放（SPEC-AG-053）

## 8. 前端实现

### 8.1 技术栈

Next.js 16 App Router + React 19 + Tailwind v4 + shadcn/ui + sonner（toast）。

### 8.2 页面

| 页面 | 路径 | 功能 |
|---|---|---|
| 登录/注册 | `/login` | 登录、注册切换 |
| 聊天 | `/chat` | 侧栏（对话列表/模型选择/导航）、消息流、输入框 |
| 记忆 | `/memories` | 按类别 Tab 展示、编辑、删除（Dialog 确认） |
| 待办 | `/todos` | 待办列表、提醒列表、新建待办 |

### 8.3 关键交互细节

- **Markdown 渲染**：`react-markdown` + `remark-gfm` + `rehype-sanitize`（防 XSS）
- **IME 修复**：输入框 `onKeyDown` 检测 `isComposing`/`keyCode===229`，中文输入法确认候选词不误触发发送
- **工具调用展示**：Badge 显示工具名 + 状态（✅/❌）+ args JSON
- **删除二次确认**：所有删除用 Dialog，替代原生 `confirm()`

## 9. 后台任务与 Worker

### 9.1 jobs/outbox 模式

- PostgreSQL `jobs` 表（`status: pending/running/succeeded/failed/dead`）+ `outbox_events` 表
- Worker `claim → lease → dispatch → mark_succeeded/failed`
- 幂等键 + 重试（`max_attempts=5`，退避 1s/5s/30s/2m/10m）

### 9.2 Worker 任务类型

| job_type | handler | 说明 |
|---|---|---|
| `memory.extract` | `handle_memory_extract` | 记忆抽取 |
| `memory.consolidate` | `handle_memory_consolidate` | 记忆整合（去冗余 + 消解矛盾） |
| `reminder.scan` | `handle_reminder_scan` | 扫描 due 提醒 |
| `reminder.deliver` | `handle_reminder_deliver` | 单条提醒投递 |

### 9.3 时钟偏差处理

Worker claim 用 `func.now()`（数据库时钟）而非 Python `datetime.now(UTC)`，避免测试环境 Python 时钟快 37 秒的问题。

## 10. 可观测与安全

### 10.1 日志

- structlog 结构化日志
- `request_id/trace_id/run_id/conversation_id/tool_call_id` 串联
- 脱敏（`observability/redaction.py`）：密码/Token/Cookie/正文只记长度

### 10.2 错误分类

`llm/errors.py` 的 `ErrorKind`：validation/auth/permission/conflict/rate_limit/dependency_transient/tool_timeout/model_invalid/safety/internal，对应不同的重试策略。
