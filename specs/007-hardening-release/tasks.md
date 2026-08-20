# SPEC-007 任务清单

状态：`implemented`

本清单只在完成真实变更和验证后勾选。

## T0：规格准备

- [x] `HAR-T000` 编写 `SPEC-007` 的目标、边界、要求和验收映射。
- [x] `HAR-T001` 实现开始时将 `spec.md` 状态改为 `in_progress`。

## T1：日志脱敏

- [x] `HAR-T010` 实现日志脱敏器（password/token/cookie/正文）。
- [x] `HAR-T011` 接入 structlog 处理器。
- [x] `HAR-T012` 脱敏测试（4 个）。

## T2：安全加固测试

- [x] `HAR-T020` Prompt Injection 测试（sanitize 去 HTML/script）。
- [x] `HAR-T021` SSRF 边界确认（SearXNG 是受控 provider）。
- [x] `HAR-T022` 越权测试（SPEC-002 已有，本 Spec 复用）。

## T3：E2E 测试

- [x] `HAR-T030` Playwright 框架 + chromium。
- [x] `HAR-T031` 注册→登录态→记忆/待办页 E2E。
- [x] `HAR-T032` 未登录跳转 E2E。

## T4：故障注入

- [x] `HAR-T040` LLM 失败（抛 LLMError）测试。
- [x] `HAR-T041` LLM 超时（final round 兜底）测试。
- [x] `HAR-T042` 搜索失败降级（已有 + sanitize 测试）。

## T5：演示固化

- [x] `HAR-T050` seed 脚本（demo-a/demo-b + 记忆 + 待办）。
- [x] `HAR-T051` reset-demo 脚本（环境哨兵保护）。
- [x] `HAR-T052` Makefile 集成 + README 更新。

## T6：答辩材料

- [x] `HAR-T060` 已知限制清单（docs/known-limitations.md）。
- [x] `HAR-T061` 测试报告（各 spec verification.md 已有）。
- [x] `HAR-T062` 运行说明（README 更新）。

## T7：文档与验证

- [x] `HAR-T070` 完成 `verification.md`。
- [x] `HAR-T071` 更新 `docs/progress/007-hardening-release.md`。
- [x] `HAR-T072` 更新 README 与 Spec 状态。

## 完成规则

- `SPEC-HAR-AC-001~006` 均有真实结果。
- 日志脱敏、Prompt Injection、E2E、故障注入、seed/reset 均有自动化测试证据。
- 答辩材料齐全。
