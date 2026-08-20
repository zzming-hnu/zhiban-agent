# 过程记录 005：记忆系统

## 1. 状态

| 字段 | 值 |
|---|---|
| 对应 Spec | [SPEC-005](../../specs/005-memory-system/spec.md) |
| 当前阶段 | SPEC-005 实现与验证完成 |
| Spec 状态 | `implemented` |
| 实现状态 | T0~T11 完成 |
| 最后更新 | 2026-08-19 |

## 2. 本次完成

1. 新增 `jobs`、`outbox_events`、`memories`、`memory_candidates` 表（迁移 0005~0007）。
2. 引入 Worker：claim/lease/retry（`FOR UPDATE SKIP LOCKED`）、消费循环、job 分发。
3. 建立记忆领域：枚举、规范化、fingerprint/conflict_key、schema、repository。
4. 建立候选提取（显式+隐式）与确定性校验、决策（add/update/ignore）。
5. 建立混合检索（lexical + vector + 评分）与降级。
6. 建立治理 API（/memories）与记忆工具（memory.add/list/update/delete）。
7. 建立 Memory Flush 与上下文记忆注入。
8. 建立用户分类（基本信息/沟通禁忌/沟通偏好/其他）两层并存模型。
9. 前端记忆管理页（按分类分组、编辑、删除）。
10. 新增 26 个记忆测试，总计 99 后端 + 5 前端测试全绿。

## 3. 关键决策

### 3.1 Worker 时钟偏差

`claim_jobs` 最初用 Python `datetime.now(UTC)` 与数据库 `func.now()` 比较，因主机/容器时钟偏差（约 37 秒）导致 claim 失败。修复为统一用数据库 `func.now()` 做时间比较，不依赖主机时钟。

### 3.2 用户分类两层并存

保留技术型 `memory_type`（8 类）做后端逻辑（TTL/置信度/排序），新增 user-facing `category`（4 类）做展示。分类由模型提取时直接给出，后端只做枚举校验。

### 3.3 记忆工具需 session 注入

memory 工具需要 MemoryService（绑定用户 session），因此在 runs_router 的 `_register_memory_tools` 里注册，而非静态 `create_registry`。

### 3.4 JSONB 列存字符串列表

`source_message_ids` 是 UUID 列表，JSONB 列无法直接序列化 UUID 对象。用 `model_dump(mode="json")` 转成字符串列表再存入。

### 3.5 测试隔离

引入 conftest 的 `clean_database` fixture，按 FK 依赖顺序清理所有业务表，解决测试间数据污染。

## 4. 文件变更

新增：

- `apps/api/migrations/versions/20260819_0005_jobs_outbox_memories.py`
- `apps/api/migrations/versions/20260819_0006_memory_flush_cursor.py`
- `apps/api/migrations/versions/20260819_0007_memory_category.py`
- `apps/api/src/zhiban/memory/`（types/normalize/ids/schemas/repository/validator/service/extractor/search/flush/router/tools/__init__）
- `apps/api/src/zhiban/workers/jobs.py`
- `apps/api/src/zhiban/workers/runner.py`
- `apps/api/src/zhiban/workers/memory_jobs.py`
- `apps/api/src/zhiban/llm/embedding.py`
- `apps/web/app/memories/page.tsx`
- `apps/api/tests/test_memory_core.py`
- `apps/api/tests/test_memory_service.py`
- `apps/api/tests/test_memory_api.py`
- `apps/api/tests/test_memory_search.py`
- `apps/api/tests/test_memory_category.py`
- `apps/api/tests/test_jobs.py`

重构：

- `apps/api/src/zhiban/db/models.py`（Job/OutboxEvent/Memory/MemoryCandidate + Conversation 游标）
- `apps/api/src/zhiban/workers/main.py`（dispatcher + 消费循环）
- `apps/api/src/zhiban/conversations/runs_router.py`（记忆工具注册 + 记忆注入 + 提取 job enqueue）
- `apps/api/src/zhiban/api/router.py`（挂载 memories router）
- `apps/web/lib/api.ts`（记忆 API）
- `apps/web/app/chat/page.tsx`（记忆入口）

## 5. 验证摘要

- 迁移：单 head `20260819_0007`，upgrade/downgrade 通过。
- 后端：99 passed（新增 26）。
- 前端：5 passed。
- mypy：84 source files，无 override。
- ruff / tsc / eslint：全通过。

## 6. 已知问题

1. Embedding 未接入检索（当前 lexical 降级）。
2. 真实 Kimi 端到端记忆闭环未实测（脚本被用户拒绝）。
3. GitHub 远程 CI 未执行。

## 7. 下一步

进入 SPEC-006（待办与提醒）：写工具、Jobs/Outbox、Worker 调度、时区处理、幂等投递。
