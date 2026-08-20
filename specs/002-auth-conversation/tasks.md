# SPEC-002 任务清单

状态：`in_progress`

本清单只在完成真实变更和验证后勾选。任务按依赖顺序排列；同一组中标注「可并行」的项目可以并行。

## T0：规格准备

- [x] `AUTH-T000` 编写 `SPEC-002` 的目标、边界、要求和验收映射。
- [x] `AUTH-T001` 确认认证方案、范围与现有代码处理决策（已确认：session + HttpOnly Cookie / 完整 P0 / 增量补齐）。
- [x] `AUTH-T002` 实现开始时将 `spec.md` 状态改为 `in_progress`。

## T1：数据模型与迁移

- [x] `AUTH-T010` 扩展 `User` 模型：`settings`、`privacy_settings`、`status`、`deleted_at`。
- [x] `AUTH-T011` 新增 `AuthSession` 模型与表：`refresh_token_hash`、`user_agent_hash`、`ip_prefix`、`expires_at`、`revoked_at`、`last_seen_at`。
- [x] `AUTH-T012` 新增 `IdempotencyRecord` 模型与表。
- [x] `AUTH-T013` 扩展 `Conversation`：`archived_at`、`deleted_at`、`version`。
- [x] `AUTH-T014` 扩展 `Message`：`client_message_id`、`parent_message_id`、`token_count`、`metadata`、`updated_at`、`deleted_at`。
- [x] `AUTH-T015` 编写 Alembic 迁移（单 head），并验证 upgrade/downgrade。

依赖：T0。
输出：完整数据模型与可回退迁移。

## T2：认证领域与安全基础

- [x] `AUTH-T020` 实现 Argon2id 哈希与校验，保留 bcrypt 校验做惰性升级。
- [x] `AUTH-T021` 实现 session token 生成、哈希与 Repository 访问。
- [x] `AUTH-T022` 实现注册/登录/登出/当前用户服务逻辑。
- [x] `AUTH-T023` 实现 refresh 轮换与重用检测（家族撤销）。
- [x] `AUTH-T024` 实现 `current_user` / `current_session` 依赖，产出 `Principal(user_id, session_id)`。
- [x] `AUTH-T025` 实现设备列表与单设备撤销接口。

依赖：T1。
可并行：T3（Repository 层）。

## T3：Repository 强制作用域

- [x] `AUTH-T030` 建立 `conversations/repository.py`：所有查询显式带 `user_id`，无裸 `get_by_id`。
- [x] `AUTH-T031` 建立 `messages` 的 scope 访问（含 `client_message_id` 幂等去重）。
- [x] `AUTH-T032` 建立 `auth/repository.py`（users / auth_sessions）。
- [x] `AUTH-T033` 建立跨用户访问返回 404 的统一语义。

依赖：T1。
可并行：T2。

## T4：会话与消息 API

- [x] `AUTH-T040` 实现会话创建/列表（cursor 分页）/详情/重命名/删除。
- [x] `AUTH-T041` 实现消息列表（cursor 分页）/创建（含 `client_message_id` 幂等）。
- [x] `AUTH-T042` 实现 cursor 编解码与校验（`core/pagination.py`）。
- [x] `AUTH-T043` 响应 DTO 统一 `extra="forbid"`，snake_case，UTC 时间。

依赖：T2、T3。

## T5：幂等、CSRF/Origin 与限流

- [x] `AUTH-T050` 实现 `Idempotency-Key` 支持与 `idempotency_records` 读写。
- [x] `AUTH-T051` 实现 Cookie 认证写接口的 `Origin`/`Referer` 校验。
- [x] `AUTH-T052` 实现登录限流（IP 5 次/分、30 次/时）。
- [x] `AUTH-T053` 实现消息创建限流（用户 20 次/分）。
- [x] `AUTH-T054` 实现 Redis 不可用时的进程内降级限流。

依赖：T2、T4。

## T6：前端对齐

- [x] `AUTH-T060` 移除前端 `localStorage` token 依赖，改用 Cookie 自动携带。
- [x] `AUTH-T061` 更新 `lib/api.ts` 的认证与会话/消息 API 调用（含分页字段）。
- [x] `AUTH-T062` 更新登录页与聊天页以适配新认证流程（session 失效跳登录）。
- [x] `AUTH-T063` 更新 OpenAPI 契约与生成产物。

依赖：T4、T5。

## T7：测试

- [x] `AUTH-T070` 认证单元测试（Argon2id、token、轮换、重用检测）。
- [x] `AUTH-T071` Repository 作用域 + 跨用户隔离测试（`TwoUserFixture`）。
- [x] `AUTH-T072` 会话/消息 API 测试（CRUD + cursor 分页边界）。
- [x] `AUTH-T073` 幂等测试（同键同请求 / 同键异请求 409）。
- [x] `AUTH-T074` CSRF/Origin 与限流测试。
- [x] `AUTH-T075` 迁移 upgrade/downgrade 与单 head 测试。

依赖：T2~T6。

## T8：文档与验证

- [ ] `AUTH-T080` 完成 `verification.md`，记录所有实际命令、退出码与结果。
- [ ] `AUTH-T081` 更新 `docs/progress/002-auth-conversation.md`。
- [ ] `AUTH-T082` 更新根 README 与 Spec 状态，对照验收表记录通过/失败/未执行。
- [ ] `AUTH-T083` 更新 `spec.md` 状态为 `verified` 或 `partial`（依据真实证据）。

依赖：T7。

## 完成规则

- `SPEC-AUTH-AC-*`、`SPEC-ISO-AC-*`、`SPEC-CONV-AC-*`、`SPEC-IDEM-AC-*`、`SPEC-PAGE-AC-*`、`SPEC-SEC-AC-*`、`SPEC-DB-AC-*` 均有真实结果。
- 迁移单 head 且可 downgrade。
- 跨用户隔离、幂等、分页、CSRF、限流均有自动化测试证据。
- 前端不再依赖 `localStorage` token，Cookie 认证闭环。
