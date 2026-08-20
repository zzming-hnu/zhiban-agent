# SPEC-006 任务清单

状态：`implemented`

本清单只在完成真实变更和验证后勾选。任务按依赖顺序排列；同一组中标注「可并行」的项目可以并行。

## T0：规格准备

- [x] `TODO-T000` 编写 `SPEC-006` 的目标、边界、要求和验收映射。
- [x] `TODO-T001` 实现开始时将 `spec.md` 状态改为 `in_progress`。

## T1：数据模型与迁移

- [x] `TODO-T010` 新增 `todos` 表。
- [x] `TODO-T011` 新增 `reminders` 表。
- [x] `TODO-T012` 唯一索引：reminders dedupe_key、todos 作用域。
- [x] `TODO-T013` 编写 Alembic 迁移（单 head），验证 upgrade/downgrade。

## T2：领域逻辑与工具

- [x] `TODO-T020` 实现 `todos/service.py`。
- [x] `TODO-T021` 实现 `reminders/service.py`（时区转换）。
- [x] `TODO-T022` 实现 `todo.*` 工具。
- [x] `TODO-T023` 实现 `reminder.*` 工具。
- [x] `TODO-T024` 时区转换（UTC 存储 + IANA 回显 + 过去时间拒绝）。

## T3：Worker 调度

- [x] `TODO-T030` 提醒调度扫描。
- [x] `TODO-T031` 幂等投递（status 作为事实源）。
- [x] `TODO-T032` 投递重试/退避/dead（沿用 jobs 基础设施）。
- [x] `TODO-T033` 注册 reminder handler + 周期扫描循环。

## T4：任务跟踪

- [x] `TODO-T040` 任务进度查询（done/pending/overdue 统计）。
- [x] `TODO-T041` `/todos` `/reminders` REST API。
- [x] `TODO-T042` 任务跟踪（progress 端点）。

## T5：Mock clock

- [x] `TODO-T050` 实现 `deliver-now` 演示投递端点。
- [x] `TODO-T051` 幂等（已投递的提醒不重复投递）。

## T6：前端对齐

- [x] `TODO-T060` 待办/提醒页面（/todos）。
- [x] `TODO-T061` 聊天页侧边栏入口。

## T7：测试

- [x] `TODO-T070` 数据模型/迁移测试。
- [x] `TODO-T071` 待办/提醒服务 + 时区测试。
- [x] `TODO-T072` 工具测试（幂等、参数校验）。
- [x] `TODO-T073` Worker 调度/幂等投递测试。
- [x] `TODO-T074` 过去时间拒绝 + 幂等测试。

## T8：文档与验证

- [x] `TODO-T080` 完成 `verification.md`。
- [x] `TODO-T081` 更新 `docs/progress/006-todo-reminder.md`。
- [x] `TODO-T082` 更新 README 与 Spec 状态。

## 完成规则

- `SPEC-TODO-AC-*`、`SPEC-REM-AC-*`、`SPEC-TZ-AC-*`、`SPEC-TRK-AC-*`、`SPEC-CLOCK-AC-*` 均有真实结果。
- 待办、提醒、调度、时区、幂等投递、Mock clock 均有自动化测试证据。
- mypy strict 全绿，无 override。
