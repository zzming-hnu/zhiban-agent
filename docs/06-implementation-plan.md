# 知伴：实施计划

## 1. 目标与实施边界

“知伴”是一个独立、轻量、可实际运行的通用个人 AI 助理。首版围绕“连续对话、可控记忆、可靠工具调用、待办提醒、安全隔离”形成完整闭环，不追求企业平台级的通用编排能力。

### 1.1 首版范围

- 用户注册、登录、登出和会话续期。
- 多会话聊天，服务端通过 SSE 流式返回状态、文本、工具调用与错误事件。
- 单 Agent Orchestrator，负责上下文构建、LLM 调用、工具循环、错误降级和最终回复。
- 用户级长期记忆：写入、检索、合并、冲突处理、过期与明确遗忘。
- 工具注册与执行框架；P0 工具包括待办/提醒、可控 Mock 搜索与摘要。
- Worker 执行提醒、记忆异步任务和失败重试。
- PostgreSQL/pgvector、Redis、结构化日志、指标和最小告警。

### 1.2 明确不做

- 不直接实现企业内部 DSL、工作流平台或配置中心。
- 不实现多 Agent 协作、自治角色群或复杂规划树。
- 不接入真实社交账号、企业 IM、邮件通讯录等高风险外部系统。
- P0 不依赖真实搜索供应商或真实短信/邮件推送；使用可重复的 Mock 搜索语料和站内提醒投递保证演示稳定。
- 不复制或直接复用企业内部仓库代码；只吸收成熟模式中的边界划分、幂等、重试、观测和测试思想。

## 2. 需求与测试映射约定

需求编号沿用 `01-product-requirements.md`：

- `FR-xxx`：功能需求。
- `NFR-xxx`：非功能需求。
- `AC-xxx`：产品验收标准。
- `PRD SEC-xxx`：产品安全需求。为避免与测试编号混淆，本文在引用需求时加 `PRD` 前缀。

测试编号定义在 `07-test-plan.md`，使用 `UT/IT/API/AG/MEM/TOOL/SEC/E2E/PERF/DR-xxx`。其中 `SEC-xxx` 单独出现时表示安全测试，不是 PRD 的安全需求。

## 3. 建议 monorepo 目录

建议使用 `apps/web` 与 `apps/api`，避免 `frontend/backend` 与 package 名称混用。Node 与 Python 各自保留原生工具链，根目录只负责编排。

```text
zhiban/
├── apps/
│   ├── web/                       # Next.js + React + TypeScript
│   │   ├── app/                   # 路由、页面、Server Components
│   │   ├── components/            # 对话、记忆、待办等 UI
│   │   ├── features/              # 按业务能力组织客户端逻辑
│   │   ├── lib/                   # API client、SSE client、鉴权
│   │   └── tests/
│   └── api/                       # FastAPI
│       ├── src/zhiban/
│       │   ├── api/               # HTTP/SSE 路由和 schema
│       │   ├── auth/
│       │   ├── conversations/
│       │   ├── agent/
│       │   ├── memory/
│       │   ├── tools/
│       │   ├── todos/
│       │   ├── search/
│       │   ├── workers/
│       │   ├── observability/
│       │   ├── db/
│       │   └── core/              # 配置、错误、依赖注入
│       ├── migrations/            # Alembic
│       └── tests/
├── packages/
│   ├── contracts/                 # OpenAPI 产物、共享事件定义、生成客户端
│   ├── ui/                        # 可选：少量共享 React 组件
│   ├── eslint-config/
│   └── tsconfig/
├── infra/
│   ├── compose/                   # 本地 PostgreSQL/Redis
│   ├── docker/
│   └── deploy/                    # 部署清单，P0 保持单环境简单化
├── scripts/                       # seed、reset-demo、smoke、备份恢复演练
├── fixtures/
│   ├── search/                    # 可控 Mock 搜索语料
│   └── llm/                       # LLM 正常与异常响应样本
├── docs/
├── .env.example
├── Makefile                       # 或 justfile，统一常用命令
├── package.json                   # pnpm workspace
├── pnpm-workspace.yaml
└── pyproject.toml                 # 根级 Python 工具配置或 workspace 说明
```

约束：

- TypeScript 不手写复制 Pydantic schema；由 FastAPI OpenAPI 生成客户端或类型。
- API 层只做鉴权、校验和协议转换，业务状态机放在领域模块。
- Tool Registry 与 Tool Executor 分离；工具只依赖受限执行上下文，不直接访问任意请求对象。
- 同步 API 与异步 Worker 复用业务服务，但不复用请求生命周期对象。
- `packages/ui` 不是首版前置条件；只有出现稳定复用时才抽取。

## 4. 八阶段实施计划

工作量以一名熟悉技术栈的开发者“人日”为建议值，不包含需求等待时间。总计约 27～38 人日，可按 MVP 削减至 19～25 人日。

### 阶段 1：工程脚手架与基础设施

**建议工作量：3～4 人日**

**任务**

- 初始化 pnpm workspace、Next.js、FastAPI、统一命令和基础目录。
- 配置 PostgreSQL + pgvector、Redis、Alembic、Docker Compose。
- 建立配置加载、请求 ID、统一错误结构、日志和健康检查。
- 生成 OpenAPI 客户端的最小链路。
- 建立 lint、类型检查、单元测试、迁移检查和构建 CI。
- 创建最小 schema：users、sessions、conversations、messages、outbox_jobs。

**依赖**：无。

**输出**

- Web/API/数据库/Redis 可在本地一条命令启动。
- `/health/live` 与 `/health/ready` 可区分进程存活和依赖可用。
- 第一版 Alembic migration、`.env.example`、seed/reset 脚本框架。

**Definition of Done**

- 全新环境按运行说明在 15 分钟内启动。
- CI 可阻止格式、类型、测试、迁移或构建失败的变更。
- migration 可从空库升级到最新，并可在测试库验证 downgrade。

**映射**：`NFR-005/007~009/011/013/014`、`AC-066/067`、`PRD SEC-002/007`；`UT-001~010`、`IT-001~010`、`API-001~005`、`DR-001`。

**关键风险**

- Node/Python 工具链命令分裂：由根级 Makefile/justfile 收敛。
- pgvector 镜像与扩展版本不一致：镜像、扩展和迁移显式固定并在启动时检查。

### 阶段 2：Auth 与会话骨架

**建议工作量：3～4 人日**

**任务**

- 实现注册、登录、登出、刷新/续期策略和密码安全存储。
- 建立用户、会话、消息 CRUD 与分页。
- 所有资源查询强制携带 `user_id`，服务层禁止裸主键跨租户读取。
- Web 端建立受保护路由、登录页、会话列表和空聊天页。
- 对关键写操作增加 CSRF/Origin 策略（取决于 Cookie 或 Bearer 方案）和基础限流。

**依赖**：阶段 1。

**输出**

- 完整登录态闭环。
- 用户只能读取和修改自己的会话与消息。
- API 错误格式和前端登录失效处理一致。

**Definition of Done**

- 未认证、过期认证、跨用户资源访问均返回预期状态，不泄露资源存在性。
- 密码、Token、Cookie 配置满足开发/生产环境差异要求。
- 两个 seed 用户的数据可验证严格隔离。

**映射**：`FR-001~005`、`FR-010~012`、`FR-110~114`、`AC-001~004`、`PRD SEC-001~004/006/010/014`；`API-010~029`、`SEC-001~015`、`E2E-001`。

**关键风险**

- 为赶进度使用前端传入的 user_id：必须从服务端认证上下文取得。
- Cookie 与跨域部署组合复杂：MVP 优先同站部署或反向代理统一域名。

### 阶段 3：流式聊天与 Agent Orchestrator

**建议工作量：5～7 人日**

**任务**

- 定义 SSE 事件：`run.started`、`message.delta`、`tool.call.started/completed/failed`、`message.completed`、`run.completed/failed/cancelled`、`warning.degraded`、`ping`。
- 持久化用户消息、助理消息、生成状态和客户端请求幂等键。
- 实现单 Agent 循环：构造上下文、调用 LLM、解析工具意图、限制轮次、生成最终回复。
- 实现 Token 预算、旧消息裁剪、摘要压缩和 flush 时机。
- 处理 LLM JSON 畸形、429、5xx、超时、空答和重复答，提供可读降级回复。
- Web 端实现增量渲染、取消、重连/补取最终消息和错误提示。

**依赖**：阶段 2；可与阶段 4 的 Registry 接口设计并行。

**输出**

- 可完成普通多轮流式对话。
- Agent trace 记录模型调用、轮次、耗时和脱敏错误，不保存密钥或完整敏感 Prompt。
- 中断后不会产生重复用户消息或重复工具副作用。

**Definition of Done**

- SSE 正常结束、客户端取消、网络断开和服务端异常均有确定终态。
- 超过 Token 预算时触发可测试的裁剪/压缩，不直接把无限历史发送给模型。
- 外部模型失败时返回用户可理解的错误和可重试建议。

**映射**：`FR-012~019`、`FR-120/124~128`、`NFR-001/003/005/006/012`、`AC-010~014/060`；`AG-001~029`、`API-030~049`、`E2E-010~019`、`PERF-001~004`。

**关键风险**

- SSE 与数据库事务生命周期绑定导致长事务：先提交消息，再独立流式生成与更新状态。
- 模型输出驱动无限循环：工具轮次、重复调用签名和总耗时三重限制。

### 阶段 4：工具注册、执行与搜索摘要

**建议工作量：4～5 人日**

**任务**

- 定义工具元数据、JSON Schema、权限、超时、重试、幂等与副作用等级。
- 实现 Registry、Executor、参数校验、统一结果/错误和审计记录。
- 对只读工具与写工具采用不同重试策略；写工具要求 idempotency key。
- 实现重复调用检测、最大工具轮数和强制 final round。
- 提供 Mock 搜索工具：固定语料、固定来源、可注入延迟/超时/错误。
- 实现搜索结果裁剪、来源标注和摘要；真实搜索 provider 作为可选 P1 adapter。

**依赖**：阶段 1；与阶段 3 并行开发，在联调点接入 Orchestrator。

**输出**

- 新增工具只需实现统一接口并注册。
- Mock 搜索在离线环境可重复演示“检索—调用—摘要—引用来源”。
- 工具调用有 trace、耗时、结果大小、错误类型和用户归属。

**Definition of Done**

- 非法 schema、未知工具、超时、可重试错误、不可重试错误和重复调用均行为明确。
- URL/网络类工具默认拒绝私网、环回、云元数据地址和重定向绕过。
- 工具失败不导致聊天无响应，Agent 能给出部分结果或说明限制。

**映射**：`FR-018`、`FR-070~075`、`FR-080~085`、`FR-121~123/126/127`、`NFR-006/007/012~014`、`AC-040~044/061/062`、`PRD SEC-008~010`；`TOOL-001~029`、`SEC-020~029`、`E2E-040~049`。

**关键风险**

- “通用工具”演变成可执行任意代码：首版只允许显式注册的类型化工具。
- 搜索结果中的 Prompt Injection：外部内容始终标记为不可信数据，不作为系统指令。

### 阶段 5：长期记忆

**建议工作量：5～7 人日**

**任务**

- 定义记忆类型、来源消息、规范化值、置信度、状态、TTL 和版本。
- 实现候选记忆提取、确定性校验、去重/合并、冲突记录与显式确认策略。
- pgvector 存储 embedding，并以用户过滤、类型过滤、相似度、时效和置信度混合排序。
- 在上下文预算内注入少量相关记忆，标明来源和不确定性。
- 支持“记住”“忘记”“更正”三类显式操作；遗忘后禁止从旧消息重新静默恢复。
- 对 embedding/LLM 不可用提供关键词或结构化字段降级。

**依赖**：阶段 3；向量基础设施来自阶段 1。数据模型与检索测试可提前并行。

**输出**

- 记忆列表/状态 API 和最小 UI，可查看、确认、更正、删除。
- 对写入、读取、冲突、删除有审计记录。
- seed 包含偏好、习惯、待办相关和冲突样例。

**Definition of Done**

- “第一次告知偏好，跨会话主动使用”和“明确忘记后不再使用”通过 E2E。
- 所有检索先按 user_id 过滤，再进行排序；跨用户向量相近也不可返回。
- 冲突记忆不会无条件覆盖高置信度显式记忆。

**映射**：`FR-020~031`、`FR-040~045`、`FR-111/116`、`NFR-003/006/008/012`、`AC-020~025/063`、`PRD SEC-004~007/011~013`；`MEM-001~039`、`AG-010~019`、`SEC-030~035`、`E2E-020~029`。

**关键风险**

- 每轮都写记忆造成污染：候选提取与最终写入分开，限制类型和频率。
- “删除记忆”仍从摘要或缓存泄露：删除时失效相关缓存和上下文摘要，并记录 tombstone。

### 阶段 6：待办、提醒与 Worker

**建议工作量：3～5 人日**

**任务**

- 实现待办创建、查询、修改、完成和删除工具/API。
- 统一存储 UTC，保存用户 IANA 时区和输入原文；处理 DST 和歧义时间。
- 设计 reminder job、outbox、claim/lease、重试、死信和幂等投递。
- Worker 轮询或队列消费到期任务；P0 投递到站内通知/演示收件箱。
- 提供 Mock clock、立即触发和重置能力，避免演示等待真实时间。

**依赖**：阶段 4；用户时区来自阶段 2。可与阶段 5 大部分并行。

**输出**

- 对话中可创建、修改、取消待办和提醒。
- Worker 重启、重复消费或网络抖动不产生重复可见投递。
- 管理/脚本入口可查看待处理、失败和死信任务。

**Definition of Done**

- 时区、DST、并发修改、重复消费和补偿场景测试通过。
- “创建并修改提醒”E2E 可用 Mock clock 稳定完成。
- 生产配置不会误用演示投递器。

**映射**：`FR-050~059`、`FR-090~093`、`NFR-003/004/006`、`AC-030~035`、`PRD SEC-004/006/009/010`；`TOOL-030~039`、`IT-030~039`、`E2E-030~039`、`DR-010~014`。

**关键风险**

- exactly-once 不现实：采用 at-least-once 消费加幂等写入/投递。
- 时区解释不确定：让 Agent 回显绝对时间和时区，歧义时请求确认。

### 阶段 7：稳定性、安全与可观测性

**建议工作量：3～4 人日**

**任务**

- 完成超时预算、重试抖动、熔断/限流和依赖降级矩阵。
- 增加 Prompt Injection、SSRF、越权、输入大小、上传/URL 白名单防护。
- 日志字段脱敏；禁止记录密码、Token、Cookie、完整个人记忆和原始第三方密钥。
- 指标覆盖请求率、错误率、延迟、SSE 中断、LLM/工具错误、队列积压、记忆命中。
- 建立 trace_id、conversation_id、message_id、tool_call_id 关联，但用户标识使用内部 ID/哈希。
- 编写备份、恢复、数据删除和故障处置 runbook。

**依赖**：阶段 2～6；安全用例应从各阶段开始，而非全部后置。

**输出**

- 最小仪表盘/查询模板、告警阈值说明和 runbook。
- 安全回归集、依赖故障注入集、数据脱敏检查。
- 数据库备份与恢复演练脚本。

**Definition of Done**

- 所有外部依赖单点故障时，接口在超时预算内结束并返回可读信息。
- P0 安全用例无未处置高危项；日志抽检不包含已定义敏感字段。
- 可从 trace_id 定位一次聊天的 API、模型、工具和 Worker 路径。

**映射**：`FR-120~128`、`NFR-003~009/012~014/030~033`、`AC-060~069`、`PRD SEC-001~014`；`SEC-001~049`、`PERF-010~019`、`DR-001~019`、`E2E-050~059`。

**关键风险**

- 可观测数据反而泄露隐私：默认少记录，并对允许字段建立清单。
- 不受控重试放大故障：每层只承担一种重试责任，统一总超时和重试预算。

### 阶段 8：E2E、部署与答辩固化

**建议工作量：2～3 人日**

**任务**

- 固化关键 E2E、性能基线、smoke 和恢复演练。
- 创建生产镜像、迁移/启动顺序、健康检查和回滚说明。
- 完成 seed、`reset-demo`、Mock 模式、演示账号和录屏。
- 编写运行说明、架构图、已知限制、测试报告模板和答辩脚本。
- 在干净环境完整走一遍部署、重置、演示和故障恢复。

**依赖**：阶段 1～7。

**输出**

- 可重复部署与演示的 release candidate。
- 主路径与离线/模型不可用备选演示材料。
- 提交包、运行说明和答辩材料。

**Definition of Done**

- 关键 E2E 和 smoke 全部通过，且结果来自实际执行记录。
- 数据重置不依赖手工改库；Mock 模式有明显环境标识。
- 演示脚本在 8～12 分钟内完成，并预留问答时间。

**映射**：全部 P0 `FR/NFR/AC/PRD SEC`，重点为 `AC-001~069` 与 `NFR-011/013/014`；`E2E-001~059`、`PERF-001~019`、`DR-001~019`。

**关键风险**

- 演示依赖公网或单一模型：准备 Mock、备用 provider 或录屏。
- 最后阶段才发现环境不可复现：阶段 1 即要求空环境启动，阶段 8 只做固化。

## 5. MVP 关键路径与并行安排

### 5.1 关键路径

`阶段 1 基础设施 → 阶段 2 Auth/会话 → 阶段 3 流式聊天 → 阶段 4 工具执行 → 阶段 5 记忆 → 阶段 6 提醒 → 阶段 8 E2E/答辩`

阶段 7 的安全和观测不是可完全后置的独立阶段：数据隔离、工具权限、日志脱敏必须随阶段 2～6 同步实现，阶段 7 负责补齐和系统化验证。

### 5.2 可并行项

- Web 登录/会话 UI 可与 API Auth 并行，以 OpenAPI contract 和 Mock API 对齐。
- 阶段 3 的 SSE 客户端可与后端 Orchestrator 并行，先使用固定事件流 fixture。
- 阶段 4 Registry/Executor 可与阶段 3 并行，先以 fake LLM 发出工具调用。
- 阶段 5 的记忆数据模型/排序测试可与阶段 4 联调并行。
- 阶段 6 的 Worker/调度器可与记忆 UI 并行。
- 安全用例、故障 fixture、运行文档和 smoke 脚本贯穿全程。

## 6. 范围削减顺序

进度不足时按以下顺序削减，始终保留“对话—记忆—工具—安全隔离”的答辩主线：

1. 取消真实搜索 provider，仅保留有来源的 Mock 搜索。
2. 取消真实邮件/短信/推送，仅保留站内演示收件箱。
3. 取消独立 `packages/ui` 和复杂视觉动效。
4. 取消记忆自动确认 UI，保留列表、明确记住/忘记和服务端冲突策略。
5. 降低语义检索复杂度，保留 user filter + pgvector + 简单加权排序。
6. 取消复杂 recurring reminder，仅保留一次性提醒和待办修改。
7. 取消多 provider 动态切换，保留一个 provider + fake provider。
8. 最后才削减自动记忆提取；若必须削减，仍保留显式“请记住”和跨会话检索闭环。

不可削减项：跨用户隔离、工具参数校验、总超时、幂等、日志脱敏、可读错误、可重复 reset/seed。

## 7. 数据迁移、Seed 与 Mock 策略

### 7.1 Migration

- 所有 schema 变更通过 Alembic，禁止启动时自动 `create_all` 修改生产库。
- migration 命名包含序号和目的；CI 从空库升级到 head，并检查单 head。
- 破坏性变更使用 expand/migrate/contract：先新增兼容字段，回填，再移除旧字段。
- embedding 模型/维度作为元数据保存；更换模型使用新列或新表渐进重建，不原地混写。
- 每个 release 明确“迁移前备份、迁移命令、失败回滚/前滚策略”。

### 7.2 Seed

- seed 幂等，可按 `dev`、`test`、`demo` profile 执行。
- demo seed 包含两个用户，以验证隔离；包含会话、偏好记忆、冲突记忆、待办和搜索 fixture。
- 不将真实姓名、邮箱、聊天记录、Token 或第三方密钥提交到仓库。
- `reset-demo` 只允许在明确的非生产环境运行，并要求环境哨兵变量和数据库名称双重确认。

### 7.3 Mock

- `FakeLLM` 支持正常文本、工具调用、畸形 JSON、429、5xx、超时、空答和重复答。
- `MockSearchProvider` 读取版本化 fixture，返回固定标题、摘要、URL 和时间戳。
- `MockDeliveryProvider` 写入演示收件箱，支持失败、延迟和重复回执。
- `FakeClock` 驱动提醒测试和演示，禁止测试依赖真实 sleep。
- Mock 与生产 adapter 实现同一接口；应用启动日志和 UI 明确显示 Mock 模式。

## 8. 配置与环境变量

配置应由类型化 Settings 加载，启动时校验；生产环境缺失关键值应直接失败，不使用危险默认值。

建议变量分组：

- 应用：`APP_ENV`、`APP_VERSION`、`LOG_LEVEL`、`PUBLIC_APP_URL`。
- Web/API：`NEXT_PUBLIC_API_BASE_URL`、`API_CORS_ORIGINS`、`TRUSTED_HOSTS`。
- 数据：`DATABASE_URL`、`REDIS_URL`、连接池上限。
- Auth：`SESSION_SECRET` 或 JWT 密钥、Cookie Secure/SameSite、会话 TTL。
- LLM：provider、model、API key、请求超时、最大重试、Token 预算、最大工具轮数。
- Embedding：provider、model、dimension、batch size。
- 工具：搜索 provider、允许域名、工具总超时、单工具结果大小。
- Worker：并发数、poll interval、lease TTL、最大重试、死信阈值。
- Mock：`LLM_MODE=fake`、`SEARCH_MODE=mock`、`DELIVERY_MODE=mock`、`CLOCK_MODE`。
- 观测：OTLP endpoint、service name、采样率；禁止在环境变量中配置需写入日志的敏感明文。

`.env.example` 只写键和安全示例；本地 `.env`、生产密钥和任何真实凭据不入库。

## 9. CI Gate

建议将 CI 分为由快到慢的 gate：

1. **静态检查**：Markdown/配置校验、ESLint、Prettier、Ruff、Python formatter check。
2. **类型与契约**：TypeScript、mypy/pyright、OpenAPI 生成后无未提交漂移。
3. **单元测试**：Web/API 单元测试，覆盖核心状态机和纯函数。
4. **集成测试**：临时 PostgreSQL/pgvector、Redis；执行 migration、repository、Worker、SSE 测试。
5. **安全检查**：依赖漏洞、secret scan、SAST、权限和 SSRF 回归集。
6. **构建**：Web production build、API/Worker 镜像构建和容器健康检查。
7. **E2E/Smoke**：FakeLLM + Mock 外部依赖运行 P0 场景；主分支或合并队列必跑。
8. **定时测试**：真实 provider 契约、性能、备份恢复和长时间任务，不阻塞每个小提交但阻塞 release。

合并最低条件：

- 所有必需 gate 通过。
- 新功能包含对应测试编号，迁移和配置变更有说明。
- 不降低核心模块覆盖门槛；安全高危为 0。
- OpenAPI、migration、锁文件和生成代码无漂移。
- 未声称执行尚未实际运行的测试；实际结果由 CI 记录。

## 10. 里程碑验收

- **M1 可启动**：阶段 1 完成，空环境可复现。
- **M2 可对话**：阶段 2～3 完成，多轮流式聊天和异常降级可用。
- **M3 可行动**：阶段 4 完成，可控搜索与工具链闭环。
- **M4 有记忆**：阶段 5 完成，跨会话偏好和明确遗忘闭环。
- **M5 会提醒**：阶段 6 完成，Mock clock 下创建、修改、投递闭环。
- **M6 可答辩**：阶段 7～8 完成，安全、观测、E2E、部署与备选演示固化。
