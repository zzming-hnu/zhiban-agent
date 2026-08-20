# 过程记录 007：稳定性加固与答辩固化

## 1. 状态

| 字段 | 值 |
|---|---|
| 对应 Spec | [SPEC-007](../../specs/007-hardening-release/spec.md) |
| 当前阶段 | SPEC-007 实现与验证完成 |
| Spec 状态 | `implemented` |
| 实现状态 | T0~T7 完成 |
| 最后更新 | 2026-08-19 |

## 2. 本次完成

1. 日志脱敏：redaction.py（密码/Token/Cookie/正文只记长度），接入 structlog。
2. 安全测试：Prompt Injection（sanitize）、日志脱敏、越权复用。
3. E2E：Playwright 框架 + chromium，注册→登录态→记忆/待办页、未登录跳转。
4. 故障注入：LLM 失败抛错、LLM 超时兜底测试。
5. 演示固化：seed-demo / reset-demo 脚本 + Makefile 集成。
6. 答辩材料：known-limitations.md。

## 3. 关键决策

### 3.1 E2E 聚焦确定性路径

聊天流式依赖真实 LLM（不稳定），E2E 只覆盖确定性路径（登录/导航），流式用后端 API 级验证。

### 3.2 不实现完整熔断器

当前单依赖（Kimi/搜索）已有超时+重试，完整熔断矩阵对答辩收益低。

### 3.3 SearXNG 作为受控搜索边界

搜索走自建 SearXNG（不抓任意 URL），天然规避 SSRF 风险。

## 4. 文件变更

新增：

- `apps/api/src/zhiban/observability/redaction.py`
- `apps/api/tests/test_redaction.py`
- `apps/api/tests/test_security.py`
- `apps/api/tests/test_fault_injection.py`
- `apps/web/playwright.config.ts`
- `apps/web/e2e/main-flow.spec.ts`
- `scripts/seed_demo.py`
- `scripts/reset_demo.py`
- `docs/known-limitations.md`

更新：

- `apps/api/src/zhiban/observability/logging.py`（接入脱敏）
- `apps/web/package.json`（@playwright/test + e2e script）
- `Makefile`（seed-demo/reset-demo/e2e）
- `README.md`（运行说明）

## 5. 验证摘要

- 后端：125 passed（新增 10）。
- 前端 E2E：2 passed。
- seed/reset：幂等验证通过。
- mypy / ruff：全通过。

## 6. 已知问题

1. 聊天流式浏览器 E2E 未做。
2. GitHub 远程 CI 未执行。
3. 完整性能压测未做。

## 7. 下一步

P0 全部完成（SPEC-001~007）。后续方向：
- 长期目标：Agent 平台演进（ReAct 强化 + MCP 工具 + 主副 Agent）。
- shadcn/ui 完整引入（前端美化）。
- 付费搜索 API（替换自建 SearXNG）。
