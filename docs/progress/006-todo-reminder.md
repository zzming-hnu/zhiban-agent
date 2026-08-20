# 过程记录 006：待办与提醒

## 1. 状态

| 字段 | 值 |
|---|---|
| 对应 Spec | [SPEC-006](../../specs/006-todo-reminder/spec.md) |
| 当前阶段 | SPEC-006 实现与验证完成 |
| Spec 状态 | `implemented` |
| 实现状态 | T0~T8 完成 |
| 最后更新 | 2026-08-19 |

## 2. 本次完成

1. 新增 `todos`、`reminders` 表（迁移 0008）。
2. 实现待办/提醒领域逻辑 + 时区转换（UTC 存储 + IANA 回显 + 过去时间拒绝）。
3. 实现 `todo.create/complete`、`reminder.create/cancel` 工具。
4. 实现 Worker 提醒调度：周期扫描 + `FOR UPDATE SKIP LOCKED` + 幂等投递。
5. 实现任务进度统计（done/pending/overdue）。
6. 实现 `/todos` `/reminders` REST API + `deliver-now` 演示投递端点。
7. 前端待办/提醒页面（/todos）。
8. 新增 11 个测试，总计 112 后端 + 5 前端测试全绿。

## 3. 关键决策

### 3.1 幂等投递以 status 为事实源

投递不依赖独立 outbox 记录，而是以 reminder.status 状态机（scheduled→delivering→delivered）保证幂等：重复扫描只投 scheduled 的提醒，已 delivered 的跳过。

### 3.2 时区统一 UTC 存储

存储 UTC，用户 IANA 时区只用于回显和解释。过去时间在 service 层拒绝（`past_time` 错误码）。

### 3.3 提醒 dedupe 幂等

`dedupe_key = SHA-256(user + title + remind_at)`，相同请求幂等返回已有提醒（不依赖数据库唯一约束报错）。

### 3.4 Mock clock 用 deliver-now 简化

完整 FakeClock（时间推进）未做，用「立即投递」端点替代，满足答辩演示需求。

## 4. 文件变更

新增：

- `apps/api/migrations/versions/20260819_0008_todos_reminders.py`
- `apps/api/src/zhiban/todos/`（timezone/schemas/repository/service/tools/router/__init__）
- `apps/api/src/zhiban/workers/reminder_jobs.py`
- `apps/web/app/todos/page.tsx`
- `apps/api/tests/test_todos.py`
- `apps/api/tests/test_reminder_delivery.py`

重构：

- `apps/api/src/zhiban/db/models.py`（Todo/Reminder）
- `apps/api/src/zhiban/workers/main.py`（注册 reminder handler + 扫描循环）
- `apps/api/src/zhiban/conversations/runs_router.py`（注册 todo/reminder 工具）
- `apps/api/src/zhiban/api/router.py`（挂载 todos router）
- `apps/web/lib/api.ts`（todo/reminder API）
- `apps/web/app/chat/page.tsx`（待办入口）

## 5. 验证摘要

- 迁移：单 head `20260819_0008`，upgrade/downgrade 通过。
- 后端：112 passed（新增 11）。
- 前端：5 passed。
- mypy：95 source files，无 override。
- ruff / tsc / eslint：全通过。

## 6. 已知问题

1. 完整 FakeClock 未做（用 deliver-now 替代）。
2. 提醒「稍后处理」snooze 未做。
3. 待办「逾期」视觉标注未做。
4. 真实 Kimi 端到端未实测。

## 7. 下一步

进入 SPEC-007（hardening/release）：安全、观测、E2E、部署与答辩固化。
