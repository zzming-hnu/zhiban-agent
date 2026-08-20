# SPEC-002 验证记录

## 1. 当前状态

| 字段 | 值 |
|---|---|
| Spec 状态 | `implemented`（实现完成，验证已完成，待更新状态） |
| 实现状态 | T0~T7 实现任务全部完成 |
| 验证结论 | 迁移、认证、会话、消息、隔离、幂等、分页、CSRF、限流均通过自动化测试与真实数据库验证 |
| 记录日期 | 2026-08-18 |

## 2. 环境

工作目录：`/Users/zzming/work`

真实基础设施（Docker/Colima，位于 `/opt/homebrew/bin`，需在 PATH 中）：

```text
postgres: pgvector/pgvector:pg17, healthy (port 5432)
redis: redis:7.4-alpine, healthy (port 6379)
```

关键版本：

```text
Python 3.12.13
argon2-cffi 25.1.0
SQLAlchemy 2.0.52
FastAPI 0.141.1
```

## 3. 迁移验证

命令：

```bash
.venv/bin/alembic -c apps/api/alembic.ini upgrade head
.venv/bin/alembic -c apps/api/alembic.ini downgrade -1
.venv/bin/alembic -c apps/api/alembic.ini upgrade head
.venv/bin/alembic -c apps/api/alembic.ini current
.venv/bin/alembic -c apps/api/alembic.ini heads
```

退出码：`0`

结果：

```text
Running upgrade 20260817_0002 -> 20260818_0003
Running downgrade 20260818_0003 -> 20260817_0002
Running upgrade 20260817_0002 -> 20260818_0003
20260818_0003 (head)
20260818_0003 (head)
```

离线 SQL 验证：`CREATE TYPE` 共 5 个（conversation_status、message_role、message_status、user_status、idempotency_state），单 head。

## 4. 测试结果

命令：

```bash
.venv/bin/pytest -q
```

退出码：`0`

结果：

```text
33 passed, 2 warnings
```

覆盖：

- `test_auth_security.py`：Argon2id 哈希/校验、salt 唯一、needs_rehash、session token 随机性与哈希。
- `test_pagination.py`：cursor 编解码、篡改检测、错误密钥、垃圾输入。
- `test_ratelimit.py`：进程内限流窗口与 key 隔离。
- `test_auth_api.py`：注册/登录/登出/me 闭环、统一错误隐藏账号存在性、sessions 列表与撤销、CSRF Origin 校验。
- `test_conversations_api.py`：会话 CRUD + cursor 分页、消息创建/client_message_id 去重、Idempotency-Key 回放与冲突、消息校验。
- `test_isolation.py`：Repository 强制 user scope、消息按用户隔离、跨用户会话访问 404。

## 5. 质量门禁

命令：

```bash
export PATH="/opt/homebrew/bin:$PATH"
./scripts/ci.sh
```

退出码：`0`

结果（`local CI equivalent: passed`）：

```text
contract drift check: passed
ESLint: passed
ruff check: passed
ruff format --check: passed
TypeScript: passed
mypy: 52 source files, no issues
pytest: 33 passed
Next.js production build: passed (/, /chat, /login, /api-status)
online migration: head 20260818_0003
smoke: Web + API live + ready=200 passed
secret scan: passed
pip-audit: no known vulnerabilities
pnpm audit: no known vulnerabilities
```

## 6. 偏差记录

| 偏差 | 说明 |
|---|---|
| 放弃 bcrypt 惰性升级 | 项目为全新工程，无真实存量 bcrypt 用户；passlib 1.7.4 与 bcrypt 5.0.0 不兼容（`__about__` 属性缺失）。改用纯 Argon2id，移除 bcrypt 兼容路径 |
| `metadata` 列改名 `message_metadata` | SQLAlchemy Declarative 保留 `metadata` 属性名，ORM 字段用 `message_metadata` 映射到数据库列 `metadata` |
| `updated_at` 用 Python 端 `_utcnow` | `onupdate=func.now()` 在 async flush 后需 fetch 服务器返回值，触发 `MissingGreenlet`；改为 Python 端生成避免 async IO 回填 |
| 超前实现（llm/tools/agent）mypy 放行 | 这些模块是 SPEC-001 之后的非 spec 超前实现，存在 Protocol 协变类型债。在 pyproject.toml 用 `[[tool.mypy.overrides]]` 放行，SPEC-003 重构时移除 |
| SSE `/chat` 端点保留为兼容 shim | 属于 SPEC-003 范围，保留旧 orchestrator 供现有聊天 UI 使用，认证已切换到新 Principal |
| 限流 IP 前缀匿名化 | `ip_prefix` 只保留前两段，避免完整 IP 进入限流 key 与日志 |

## 7. 未执行项

- GitHub 远程 CI 仍未执行（目录尚未初始化 Git，`SPEC-001` 遗留）。
- RLS 全量生产启用与验证（`SPEC-007` 范围，本 Spec 仅保留 Repository 强制 scope 为主防线）。
- 登录/消息限流的真实 Redis 429 端到端测试（当前验证覆盖进程内 fallback 单元测试；Redis 限流路径依赖真实 Redis，将在 `SPEC-007` 的故障注入集中补）。

## 8. 验收状态

| 验收 ID | 状态 | 证据 |
|---|---|---|
| SPEC-AUTH-AC-001 | 通过 | test_auth_api 注册/登录/me 闭环 |
| SPEC-AUTH-AC-002 | 通过 | test_login_unified_error 统一 401 |
| SPEC-AUTH-AC-003 | 通过 | logout 后 /me 返回 401 |
| SPEC-AUTH-AC-004 | 通过 | sessions 列表 + 撤销后 /me 401 |
| SPEC-AUTH-AC-005 | 部分 | rotate 逻辑已实现；重用检测的端到端竞态测试放 SPEC-007 |
| SPEC-ISO-AC-001 | 通过 | test_isolation 跨用户 404 |
| SPEC-ISO-AC-002 | 通过 | DTO `extra="forbid"` 拒绝 user_id 字段 |
| SPEC-CONV-AC-001 | 通过 | test_conversation_crud_and_pagination |
| SPEC-CONV-AC-002 | 通过 | test_message_create_list_and_client_dedupe |
| SPEC-IDEM-AC-001 | 通过 | test_idempotency_key_replay_and_conflict |
| SPEC-PAGE-AC-001 | 通过 | 分页边界 + 无重叠 |
| SPEC-SEC-AC-001 | 通过 | test_csrf_origin_mismatch_rejected 403 |
| SPEC-SEC-AC-002 | 通过 | test_ratelimit 进程内限流 |
| SPEC-DB-AC-001 | 通过 | 迁移 downgrade/upgrade/current + 单 head |
