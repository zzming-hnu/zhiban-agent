# SPEC-006 验证记录

## 1. 当前状态

| 字段 | 值 |
|---|---|
| Spec 状态 | `implemented` |
| 实现状态 | T0~T8 完成 |
| 验证结论 | 待办、提醒、调度、时区、幂等投递、演示投递均通过自动化测试 |
| 记录日期 | 2026-08-19 |

## 2. 环境

工作目录：`/Users/zzming/work`。PostgreSQL `zhiban`（开发库）+ `zhiban_test`（测试库）、Redis、Worker。

## 3. 迁移

```text
20260819_0008: todos + reminders 表（todo_status / reminder_status 枚举、dedupe 唯一索引、due 索引）
```

单 head `20260819_0008`，upgrade/downgrade 循环通过。

## 4. 测试结果

命令：`.venv/bin/pytest -q`

```text
112 passed, 2 warnings
```

新增待办/提醒测试（11 个）：

- `test_todos.py`（8）：时区转换（to_utc/validate/format）、待办创建/完成/进度、提醒创建/取消/过去时间拒绝/幂等去重。
- `test_reminder_delivery.py`（3）：扫描投递、幂等扫描、跳过未来/已取消。

前端：5 个测试通过。

## 5. 质量门禁

```text
mypy: Success, 95 source files（无 override）
ruff check + format: 全通过
前端 tsc/eslint/vitest: 全通过
OpenAPI 契约：已重新生成
```

## 6. 关键实现

- **时区**：统一存 UTC，用户 IANA 时区回显；过去时间拒绝（`past_time` 错误）。
- **幂等**：提醒 dedupe_key（user+title+time）幂等返回已有；投递以 status 为事实源，重复扫描不重复投递。
- **调度**：Worker 周期扫描 + `FOR UPDATE SKIP LOCKED` 抢占 + status 状态机（scheduled→delivering→delivered/cancelled）。
- **演示投递**：`deliver-now` 端点立即投递（幂等），答辩不用真等到点。

## 7. 偏差记录

| 偏差 | 说明 |
|---|---|
| Mock clock 用 deliver-now 简化 | 完整 FakeClock（时间推进）未做，用「立即投递」端点替代，满足演示需求 |
| 投递不接真实推送 | 应用内提醒中心（reminders 状态），不做短信/邮件/PUSH |
| 提醒不做重复规则 | P1 的每日/每周 cron 延后 |

## 8. 未执行项

- 完整 FakeClock（可配置时间偏移）。
- 提醒「稍后处理」（snooze）。
- 待办的「逾期」视觉标注（后端已统计 overdue，前端未标红）。
- 真实 Kimi 端到端（工具调用创建待办/提醒未实测）。
- GitHub 远程 CI。

## 9. 验收状态

| 验收 ID | 状态 | 证据 |
|---|---|---|
| SPEC-TODO-AC-001 | 通过 | test_todos 待办创建 + 前端页面 |
| SPEC-TODO-AC-002 | 通过 | complete/cancel 测试 |
| SPEC-REM-AC-001 | 通过 | 提醒创建 + format_absolute 回显时区 |
| SPEC-REM-AC-002 | 通过 | test_reminder_delivery 扫描投递 |
| SPEC-REM-AC-003 | 通过 | 幂等扫描测试（第二次 0） |
| SPEC-REM-AC-004 | 部分 | cancel 使旧调度失效（cancel 测试），修改时间未实现 |
| SPEC-TZ-AC-001 | 通过 | to_utc/validate_timezone 测试 |
| SPEC-TRK-AC-001 | 通过 | progress 统计测试 |
| SPEC-CLOCK-AC-001 | 通过 | deliver-now 端点 + 幂等 |
