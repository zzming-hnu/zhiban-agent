# SPEC-003 验证记录

## 1. 当前状态

| 字段 | 值 |
|---|---|
| Spec 状态 | `implemented` |
| 实现状态 | T0~T9 实现任务全部完成 |
| 验证结论 | 迁移、SSE 协议、两段式、有界 Agent、compaction、Markdown 渲染均通过自动化测试 |
| 记录日期 | 2026-08-18 |

## 2. 环境

工作目录：`/Users/zzming/work`

真实基础设施（Docker/Colima，位于 `/opt/homebrew/bin`）：

```text
postgres: pgvector/pgvector:pg17, healthy (port 5432)
redis: redis:7.4-alpine, healthy (port 6379)
```

关键版本：Python 3.12.13、FastAPI 0.141.1、SQLAlchemy 2.0.52。

## 3. 迁移验证

命令：

```bash
.venv/bin/alembic -c apps/api/alembic.ini upgrade head
.venv/bin/alembic -c apps/api/alembic.ini downgrade -1
.venv/bin/alembic -c apps/api/alembic.ini upgrade head
.venv/bin/alembic -c apps/api/alembic.ini current
```

退出码：`0`

结果：

```text
Running upgrade 20260818_0003 -> 20260818_0004, Add agent_runs and conversation_summaries
Running downgrade 20260818_0004 -> 20260818_0003
Running upgrade 20260818_0003 -> 20260818_0004
20260818_0004 (head)
```

单 head `20260818_0004`。新增 `agent_runs`、`conversation_summaries` 表，含 `uq_agent_runs_active_conversation` 部分唯一索引。

## 4. 测试结果

命令：

```bash
.venv/bin/pytest -q
```

退出码：`0`

结果：

```text
54 passed, 2 warnings
```

新增 21 个测试：

- `test_token_budget.py`（6）：Token 估算、预算分配、窗口过小拒绝。
- `test_agent_events.py`（4）：seq 递增、SSE id 格式、终态标记、SSE 编解码。
- `test_llm_errors.py`（6）：HTTP 错误分类（429/5xx/4xx/408）、LLMError。
- `test_orchestrator.py`（3）：快路径流式完成、空回复兜底、无重复工具。
- `test_compaction.py`（2）：软阈值触发折叠、短会话不触发。
- `test_conversations_api.py`（更新）：两段式消息创建返回 202 + run_id + stream_url。

前端：

```text
apps/web tests: 5 passed（含 markdown 3 个：渲染 / XSS 防护 / 链接安全）
```

## 5. 质量门禁

命令：

```bash
.venv/bin/mypy apps/api/src
.venv/bin/ruff check .
.venv/bin/ruff format --check apps/api scripts
corepack pnpm --dir apps/web typecheck
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web test
```

结果：

```text
mypy: Success, 60 source files（无 override，SPEC-AG-080 达成）
ruff check: All checks passed
ruff format: 87 files already formatted
TypeScript: passed
ESLint: passed
Web tests: 5 passed
```

依赖清理：

```text
uv sync 卸载 bcrypt==5.0.0、pyjwt==2.13.0（SPEC-AG-081 达成）
passlib[bcrypt] -> passlib[argon2]
```

## 6. 端到端手工验证

真实 Kimi K2.5 流式对话：

- 配置：`LLM_PROVIDER=custom`、`LLM_BASE_URL=https://qproxy.gtimg.com/v1`、`LLM_MODEL=kimi-k2.5`。
- 前端两段式（POST messages → GET stream）流式逐字输出真实 Kimi 回答。
- `reasoning_content` 被过滤，只输出最终 `content`。
- Markdown（加粗、列表、代码块）正确渲染，原始 HTML 被剥离。

## 7. 偏差记录

| 偏差 | 说明 |
|---|---|
| `reasoning_content` 过滤 | Kimi K2.5 是推理模型，流式先输出 `reasoning_content`（思考）再输出 `content`；adapter 只取 `content`，思考过程不泄漏给用户 |
| 流式 tool_calls 累加 | OpenAI 流式的 tool_calls 分片累加（index 分组），`LLMChunk` 增加 `tool_calls` 字段 |
| 快路径改流式 | 原快路径用非流式 `chat` 一次性拿答案（无流式感），改为每轮 `chat_stream` 逐 token 输出 |
| 中断 run 自动取消 | 同一会话残留 queued run 会触发唯一约束；`start_run` 前先 `cancel_active_for_conversation` |
| Markdown 渲染纳入本 Spec | 模型天然输出 Markdown，属聊天核心体验，不延后 |
| ping 心跳预留 | `sse_ping` 函数已实现，但实际心跳循环未接入长流（单次 run 流时长有限，暂不强制） |

## 8. 未执行项

- 断线重连（Last-Event-ID 补发）的端到端浏览器测试（代码已实现，但未做浏览器级断线验证）。
- GitHub 远程 CI 仍未执行（目录未初始化 Git，SPEC-001 遗留）。
- 取消广播的跨进程实现（本 Spec 只做前端 AbortController 中断，跨进程放 SPEC-007）。

## 9. 验收状态

| 验收 ID | 状态 | 证据 |
|---|---|---|
| SPEC-AG-AC-001 | 通过 | test_agent_events（seq 递增、终态、SSE 编解码） |
| SPEC-AG-AC-002 | 通过 | test_conversations_api（202 + run_id + stream_url） |
| SPEC-AG-AC-003 | 部分 | 代码实现 Last-Event-ID 补发，未做浏览器断线 E2E |
| SPEC-AG-AC-004 | 通过 | runs_router 终态返回 snapshot |
| SPEC-AG-AC-005 | 通过 | orchestrator final round + 工具轮上限 |
| SPEC-AG-AC-006 | 通过 | test_orchestrator 空回复兜底 |
| SPEC-AG-AC-007 | 通过 | canonical_args 签名 + 重复检测 |
| SPEC-AG-AC-008 | 通过 | test_compaction 软阈值触发折叠 |
| SPEC-AG-AC-009 | 通过 | 结构化 summary schema + 覆盖区间 |
| SPEC-AG-AC-010 | 通过 | test_llm_errors 错误分类 |
| SPEC-AG-AC-011 | 通过 | create_summary_adapter + summary_llm_* 配置 |
| SPEC-AG-AC-012 | 通过 | mypy 60 source files 无 override |
| SPEC-AG-AC-013 | 通过 | run 状态机 + cancel_active_for_conversation |
| SPEC-AG-AC-014 | 通过 | 手工 Smoke（真实 Kimi 流式） |
| SPEC-AG-AC-015 | 通过 | markdown.test.tsx（渲染 + XSS + 链接） |
