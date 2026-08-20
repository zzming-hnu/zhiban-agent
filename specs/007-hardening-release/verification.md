# SPEC-007 验证记录

## 1. 当前状态

| 字段 | 值 |
|---|---|
| Spec 状态 | `implemented` |
| 实现状态 | T0~T7 完成 |
| 验证结论 | 日志脱敏、安全测试、E2E、故障注入、演示固化均通过 |
| 记录日期 | 2026-08-19 |

## 2. 测试结果

### 后端

```text
.venv/bin/pytest -q  →  125 passed
```

新增（相比 SPEC-006 的 112）：

- `test_redaction.py`（4）：敏感字段脱敏、正文只记长度、非敏感透传。
- `test_security.py`（4）：sanitize 去 script/onerror/HTML、截断。
- `test_fault_injection.py`（2）：LLM 失败抛 LLMError、LLM 超时兜底。

### 前端 E2E（Playwright）

```text
corepack pnpm --dir apps/web e2e  →  2 passed
```

- 注册 → 登录态保持 → 访问记忆/待办页。
- 未登录访问受保护页跳转登录。

## 3. 质量门禁

```text
mypy: 98 source files, 无 override
ruff check + format: 全通过
```

## 4. 演示固化验证

```text
make seed-demo    → [created] demo-a / demo-b（幂等：第二次 skip）
make reset-demo   → 删除 2 个 demo 账号，真实账号保留
```

## 5. 偏差记录

| 偏差 | 说明 |
|---|---|
| E2E 只覆盖确定性路径 | 聊天流式（依赖真实 LLM）的浏览器 E2E 未做，用后端 API 级验证替代 |
| 不实现完整熔断器 | 只做超时+重试，完整熔断矩阵对答辩收益低 |
| SSRF 靠 SearXNG 受控边界 | 搜索走自建 SearXNG（不抓任意 URL），无需额外 SSRF 过滤 |

## 6. 未执行项

- 聊天流式的浏览器级 E2E（依赖真实 LLM，不稳定）。
- GitHub 远程 CI。
- 完整性能压测。

## 7. 验收状态

| 验收 ID | 状态 | 证据 |
|---|---|---|
| SPEC-HAR-AC-001 | 通过 | test_redaction 4 个测试 |
| SPEC-HAR-AC-002 | 通过 | test_security sanitize 测试 |
| SPEC-HAR-AC-003 | 通过 | Playwright E2E 2 个通过 |
| SPEC-HAR-AC-004 | 通过 | test_fault_injection 2 个测试 |
| SPEC-HAR-AC-005 | 通过 | seed/reset 幂等验证 |
| SPEC-HAR-AC-006 | 通过 | known-limitations.md + README + 各 spec verification |
