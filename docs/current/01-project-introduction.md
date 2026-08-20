# 知伴 · 项目介绍

> 本文档反映**当前真实实现状态**（2026-08-20），与 `docs/` 下的设计期文档（00~08）区分。所有描述以代码实际行为为准。

## 1. 一句话定位

**知伴**是一个具备「可控记忆 + 可靠工具调用 + 多轮对话」能力的个人 AI 助理，从 0 到 1 全栈实现，可本地运行、可体验、可测试。

## 2. 项目背景

这是一个 AI 编程工具的实战项目（答辩项目）：使用 AI 编程工具，从 0 到 1 完成一个可实际运行的全栈 Web 应用。课题要求重点考察 AI Agent 应用的端到端工程化能力，包括：

- 记忆系统设计（写入时机、存储结构、检索策略）
- 多轮对话上下文管理与 Token 控制
- 工具调用（Function Calling）的注册、路由与稳定性
- LLM 输出不稳定时的兜底、重试与降级
- 用户数据隔离与隐私保护
- 后台服务架构与接口设计
- 系统可扩展性
- 测试与代码质量

## 3. 产品核心能力

知伴围绕「记住你、理解你、帮你办事」三条主线：

| 能力 | 说明 |
|---|---|
| **连续对话** | 多轮对话、流式输出、上下文滚动摘要压缩 |
| **可控记忆** | 主动/自动记忆提取、增删改查、按类别展示、用户可编辑 |
| **待办与提醒** | 创建/完成/取消待办，单次+周期（每天/每周）提醒，站内 toast + 浏览器通知 + 邮件三路触达 |
| **联网搜索** | 通过 SearXNG 真实搜索，结果净化 + 引用 |
| **工具调用** | Function Calling 完整链路：注册、路由、执行、幂等、审计 |

## 4. 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 16（App Router）、React 19、TypeScript、Tailwind CSS v4、shadcn/ui、sonner |
| 后端 | Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2（async） |
| LLM | DeepSeek（`deepseek-v4-flash` / `deepseek-v4-pro`，OpenAI 兼容协议） |
| Embedding | `text-embedding-3-small`（1536 维） |
| 搜索 | SearXNG（自建，可降级 Mock） |
| 存储 | PostgreSQL 16 + pgvector（唯一事实源） |
| 缓存/锁/队列 | Redis |
| 后台任务 | 独立 Worker 进程（jobs/outbox 模式） |
| 测试 | pytest（142 用例）、vitest、Playwright E2E |
| 质量 | ruff、mypy（strict）、eslint、tsc |

## 5. 架构亮点

1. **模块化单体**：API 与 Worker 两个进程共享同一套领域代码，按领域分包（auth/conversation/agent/memory/tools/todo/llm/jobs）。
2. **主 Agent - Subagent 架构**：主 Agent 负责路由 + 管理 ReAct 生命周期；Memory / Task / Search 三个专业 subagent 干具体事务，返回结构化摘要。
3. **有界 ReAct**：最多 4 个工具轮、60 秒总超时、重复调用检测、空回复兜底、final round 强制收尾。
4. **先确定性、后模型判断**：权限、Schema、幂等、去重、记忆分类映射由代码决定，LLM 只生成候选。
5. **深度异步**：记忆抽取、摘要压缩、提醒投递都走 Worker 后台任务，不阻塞聊天主链路。
6. **用户隔离**：所有数据从认证主体派生 `user_id`，Repository 层强制作用域。

## 6. 工程成熟度

- **测试**：后端 142 个 pytest 用例（含集成测试，独立测试库 `zhiban_test`）、前端 vitest、Playwright E2E。
- **质量门禁**：ruff 全绿、mypy strict 107 源文件无 override、eslint、tsc。
- **可观测**：结构化日志 + `request_id/trace_id/run_id/conversation_id` 串联、日志脱敏。
- **安全**：Argon2id 密码哈希、session + HttpOnly Cookie、CSRF、幂等键、Prompt Injection 防护、SSRF 规避（搜索走自建 SearXNG）。
- **部署**：Docker Compose 一键起全栈（web/api/worker/postgres/redis/searxng）。

## 7. 文档导航

- [系统架构](./02-system-architecture.md)
- [技术实现](./03-technical-implementation.md)
- [功能场景](./04-features-scenarios.md)
- [体验流程](./05-experience-flow.md)
- [后续可优化点](./06-roadmap.md)
- [部署与依赖迁移](../DEPLOYMENT.md)
