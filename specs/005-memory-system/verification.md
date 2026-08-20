# SPEC-005 验证记录

## 1. 当前状态

| 字段 | 值 |
|---|---|
| Spec 状态 | `implemented` |
| 实现状态 | T0~T11 完成 |
| 验证结论 | 记忆写入（显式+隐式）、检索、治理、Flush、Worker、用户分类均通过自动化测试 |
| 记录日期 | 2026-08-19 |

## 2. 环境

工作目录：`/Users/zzming/work`

真实基础设施：PostgreSQL `zhiban`（开发库）+ `zhiban_test`（测试库）、Redis。Worker 进程已启动。

## 3. 迁移

```text
20260819_0005: jobs/outbox_events/memories/memory_candidates
20260819_0006: conversations.memory_flushed_through_message_id
20260819_0007: memories.category
```

单 head `20260819_0007`，upgrade/downgrade 循环通过。HNSW `ix_memories_embedding`（vector_cosine_ops）、唯一索引 `uq_memories_active_fingerprint` 验证通过。

## 4. 测试结果

命令：`.venv/bin/pytest -q`

```text
99 passed, 2 warnings
```

新增记忆测试（相比 SPEC-004 的 73，新增 26 个）：

- `test_memory_core.py`（10）：normalize/ids/validator
- `test_memory_service.py`（4）：add/去重/槽位冲突/删除
- `test_memory_api.py`（2）：CRUD + 跨用户隔离
- `test_memory_search.py`（3）：降级/隔离/删除不可检索
- `test_memory_category.py`（3）：创建/更新分类 + 枚举
- `test_jobs.py`（4）：claim/lease/retry/幂等

前端：5 个测试通过（含 Markdown 3 个）。

## 5. 质量门禁

```text
mypy: Success, 84 source files（无 override）
ruff check: All checks passed
ruff format: 84 files already formatted
前端 tsc/eslint: passed
前端 vitest: 5 passed
```

## 6. 关键实现

- Worker claim 修复时钟偏差：时间比较统一用数据库 `func.now()`，不依赖主机时钟。
- 记忆 `source_message_ids` 序列化：JSONB 列存字符串列表（`model_dump(mode="json")`），避免 UUID 不可 JSON 序列化。
- 测试隔离：conftest 提供 `clean_database` fixture，按 FK 依赖顺序清理所有业务表。

## 7. 偏差记录

| 偏差 | 说明 |
|---|---|
| 用户分类两层并存 | 保留技术型 memory_type（8 类），新增 category（4 类）做展示；分类由提取时判断 |
| Embedding 未接入检索 | EmbeddingAdapter 已实现，但检索暂用 lexical 降级（embedding=None）；真实 embedding 接线留待后续 |
| 审计落库延后 | tool_calls 持久化延后 SPEC-006 |
| 记忆工具需 session | memory.add/list/update/delete 通过 runs_router 的 `_register_memory_tools` 注册（需 user session） |

## 8. 未执行项

- Embedding 写入/检索的真实接线（当前 lexical 降级）。
- 记忆自动确认 UI（P1）。
- 前端记忆页的「按类别筛选」交互增强（当前只分组展示）。
- GitHub 远程 CI（目录未初始化 Git）。

## 9. 验收状态

| 验收 ID | 状态 | 证据 |
|---|---|---|
| SPEC-MEM-AC-001 | 通过 | test_memory_service add + memory.add 工具 |
| SPEC-MEM-AC-002 | 通过 | extractor + validator + service 测试 |
| SPEC-MEM-AC-003 | 通过 | test_memory_core sensitive_implicit |
| SPEC-MEM-AC-004 | 通过 | test_memory_api 跨用户 404 + search 隔离 |
| SPEC-MEM-AC-005 | 通过 | search 评分 + 注入门槛 |
| SPEC-MEM-AC-006 | 通过 | update_value + category 更新测试 |
| SPEC-MEM-AC-007 | 通过 | soft_delete + deleted 不可检索 |
| SPEC-MEM-AC-008 | 通过 | lexical 降级测试 |
| SPEC-MEM-AC-009 | 部分 | 后端闭环已通，真实 Kimi 端到端未实测（脚本被拒） |
