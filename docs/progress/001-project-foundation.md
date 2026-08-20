# 过程记录 001：工程基础

## 1. 状态

| 字段 | 值 |
|---|---|
| 对应 Spec | [SPEC-001](../../specs/001-project-foundation/spec.md) |
| 当前阶段 | SPEC-001 收尾完成 |
| Spec 状态 | `partial` |
| 实现状态 | T0~T6、容器、在线数据库和故障恢复完成；远程 CI 待执行 |
| 最后更新 | 2026-08-17 |

## 2. 本次完成

本次完成规格准备和首个工程子步骤，尚未创建业务功能：

1. 建立项目级 [Spec 规范](../../specs/README.md)。
2. 编写工程基础 [Spec](../../specs/001-project-foundation/spec.md)。
3. 将实现拆分为可追踪的 [任务清单](../../specs/001-project-foundation/tasks.md)。
4. 建立事实型 [验证记录](../../specs/001-project-foundation/verification.md)。
5. 建立过程文档目录与更新规则。
6. 预检本机 Node、pnpm、Python、uv、Docker 和 Corepack。
7. 初始化 pnpm workspace，并锁定 pnpm `11.22.0`。
8. 初始化 uv 工作区，锁定 Python `3.12.13` 与质量工具。
9. 创建环境变量示例、忽略规则、编辑器和 Node/Python 版本文件。
10. 创建根 Makefile 与 monorepo 基础目录。
11. 实际运行冻结安装、Lint 和命令入口验证。
12. 创建 Next.js 基础页面、工程状态页和错误边界。
13. 创建 FastAPI app factory、Worker 入口和类型化设置。
14. 实现 request ID、统一错误、结构化日志和 `live/ready`。
15. 添加 2 个 Web 测试和 6 个 API 测试。
16. 完成 Lint、类型、测试、生产构建和运行时 Smoke。
17. 创建 PostgreSQL/pgvector、Redis、API、Worker、Web Compose。
18. 创建 API/Worker 与 Web Dockerfile。
19. 初始化 SQLAlchemy、Alembic 和 pgvector 初始迁移。
20. 把 ready 从固定 pending 改为真实数据库、revision 和 Redis 探针。
21. 增加 readiness/migration 测试，API 测试总数提升到 11。
22. 完成 Compose YAML 静态验证和 Alembic 离线 SQL 验证。
23. 建立 OpenAPI 与 TypeScript 契约包。
24. 实现不依赖 Git 的确定性契约漂移检查。
25. 添加本地 CI 等价脚本和 GitHub Actions workflow。
26. 添加 Secret、Python 依赖和 JavaScript 依赖审计。
27. 验证 Worker 可独立启动并响应 SIGTERM 正常退出。
28. 完成 SPEC-001 最终验收记录并如实标记为 `partial`。
29. 安装 Docker CLI、Compose、Buildx、Colima 和 Lima。
30. 启动 PostgreSQL/pgvector 与 Redis，验证健康和持久卷。
31. 执行在线 migration downgrade/upgrade/current 循环。
32. 验证真实数据库、Redis 故障检测与恢复。
33. 构建并运行 API、Worker、Web 三个镜像。
34. 在真实容器环境通过 `make ci`。

## 3. 关键决策

### 3.1 规格先行

后续每个步骤必须依次完成：

```text
Spec ready
→ 实现任务
→ 自动化与手工验证
→ verification.md
→ progress 文档
→ Spec verified/partial
```

这样可以让需求、代码、测试和答辩证据保持可追踪，避免一次性生成大量代码后无法解释。

### 3.2 工具链

- Node 锁定为 `.node-version` 中的 `24.14.1`，最低支持版本仍为 22。
- pnpm 不做全局安装，由 Corepack 运行；`packageManager` 锁定 `pnpm@11.22.0`。
- 系统 Python 仍为 3.9.6，项目由 uv 使用 Python 3.12.13。
- Python 开发工具实际锁定：ruff 0.16.3、mypy 2.3.1、pytest 9.1.1。
- Docker/Compose/Buildx 使用 Colima arm64 daemon，宿主机仍保留 uv/pnpm 开发路径。

### 3.3 下载降级策略

默认 PyPI 下载曾长时间停滞；进一步检查发现，一次被中断的 `uv sync` 仍在后台持有虚拟环境锁，导致镜像重试也在等待。

处理方式：

1. 清理残留 `uv` 进程。
2. 使用 30 秒 HTTP 超时和清华 PyPI 镜像重试。
3. 由 `uv.lock` 固定版本，并在 `pyproject.toml` 记录可覆盖的默认镜像。

重试在约 6 秒内完成，不再无限等待默认源。

### 3.4 Web 脚手架

`create-next-app` 在内部调用裸 pnpm 时失败，因为当前环境只通过 Corepack 提供 pnpm。生成文件已存在，因此没有重复运行生成器，而是：

1. 移除嵌套 workspace。
2. 在根 workspace 安装依赖。
3. 锁定最新兼容 TypeScript 5.x。
4. 删除不必要且产生类型冲突的 React Vite 插件。

Next.js 启动时还自动生成了另一套 AI 规则文件。项目已有 Spec 规范，因此关闭 `agentRules` 并删除自动规则，避免规则冲突。

### 3.5 API 诚实状态

- `live` 只表示 FastAPI 进程可用，返回 200。
- `ready` 在数据库、Redis 和迁移尚未接入时返回 503，而不是为了显示绿色状态假装全部就绪。
- Web 首页只调用 `live` 展示 API 是否连接；工程状态页明确标识后续依赖尚未实现。

### 3.6 任务可靠性

与总体方案一致：

- PostgreSQL `jobs/outbox` 保存后台任务事实。
- Redis 通知队列只携带可重建的 `job_id`。
- Redis 通知丢失时由 PostgreSQL 轮询补偿。

### 3.7 Readiness 语义

- `live` 不检查外部依赖，进程存活即可返回 200。
- `ready` 并发检查数据库与 Redis，并校验数据库 revision 是否等于 Alembic head。
- 状态区分 `not_configured`、`unavailable` 和 `migration_pending`，便于定位而不暴露连接串。
- 所有探针受 1 秒默认超时控制；客户端在 lifespan 创建但不在 import 时联网。

### 3.8 容器环境与补验

默认 GHCR/Homebrew 下载缓慢时采用分层降级：

1. Docker、Colima、Lima 使用清华 Homebrew Bottle 镜像。
2. Compose 镜像缺失，改从 Docker 官方 GitHub Release 安装用户级 CLI 插件。
3. Buildx 使用 Homebrew Bottle，并按 caveat 配置 CLI 插件目录。

未关闭或绕过 Homebrew 的第三方 tap 信任检查。旧 Docker Desktop 遗留的 `credsStore: desktop` 指向不存在的程序，只移除了该失效字段。

完整容器运行发现 Web standalone 的 pnpm symlink 目标缺失；最终通过 `pnpm deploy --prod` 提供完整生产依赖，Web 健康检查通过。

### 3.9 契约不依赖 Git

当前目录不是 Git 仓库，因此契约漂移不能依赖 `git diff`。检查脚本在临时目录重新生成 OpenAPI 和 TypeScript，逐字节比较已提交产物，既可本地运行，也可在未来 CI 中复用。

### 3.10 安全审计端点

npm 镜像可用于快速下载，但不提供 security audit API。处理方式是：

- 依赖下载继续使用镜像。
- `pnpm audit` 单独访问 npm 官方安全端点。
- `pip-audit` 设置 15 秒超时。

最终两类依赖审计均未发现已知漏洞。

## 4. 文件变更

新增：

- `specs/README.md`
- `specs/001-project-foundation/spec.md`
- `specs/001-project-foundation/tasks.md`
- `specs/001-project-foundation/verification.md`
- `docs/progress/README.md`
- `docs/progress/001-project-foundation.md`
- `package.json`
- `pnpm-workspace.yaml`
- `pnpm-lock.yaml`
- `pyproject.toml`
- `uv.lock`
- `.python-version`
- `.node-version`
- `.npmrc`
- `.gitignore`
- `.editorconfig`
- `.env.example`
- `Makefile`
- `apps/web/README.md`
- `apps/api/README.md`
- `packages/contracts/README.md`
- `infra/README.md`
- `fixtures/README.md`
- `scripts/README.md`
- `apps/web/app/` 页面、状态页和错误边界
- `apps/web/components/api-status.tsx`
- `apps/web/tests/` 与 Vitest 配置
- `apps/api/src/zhiban/` API、Core、日志和 Worker 骨架
- `apps/api/tests/` 六个基础测试
- `scripts/dev.sh`
- `scripts/smoke.sh`
- `infra/compose/compose.yml`
- `infra/docker/api.Dockerfile`
- `infra/docker/web.Dockerfile`
- `.dockerignore`
- `apps/api/alembic.ini`
- `apps/api/migrations/`
- `apps/api/src/zhiban/db/`
- `apps/api/src/zhiban/core/resources.py`
- `apps/api/src/zhiban/core/readiness.py`
- `apps/api/tests/test_migrations.py`
- `apps/api/tests/test_readiness.py`
- `packages/contracts/package.json`
- `packages/contracts/openapi.json`
- `packages/contracts/src/api.ts`
- `scripts/export_openapi.py`
- `scripts/check_contracts.py`
- `scripts/check_secrets.py`
- `scripts/ci.sh`
- `.github/workflows/ci.yml`

更新：

- 根 `README.md`：增加 Spec 驱动入口。
- Web/API/脚本 README：改为真实运行说明。
- Spec、任务、验证与过程状态。

未修改原计划文件，也未创建聊天、记忆、工具等业务代码。

## 5. 验证摘要

已实际确认：

- Node.js：`v24.14.1`
- Corepack：`0.34.6`
- uv：`0.11.11`
- 系统 Python：`3.9.6`
- 项目 Python：`3.12.13`
- pnpm：`11.22.0`，由 Corepack 运行
- ruff：`0.16.3`
- mypy：`2.3.1`
- pytest：`9.1.1`
- Next.js：`16.3.1`
- React：`19.2.8`
- TypeScript：`5.9.3`
- Vitest：`4.1.10`
- FastAPI：`0.141.1`
- Uvicorn：`0.52.3`
- Pydantic：`2.13.4`
- SQLAlchemy：`2.0.52`
- asyncpg：`0.31.0`
- redis-py：`8.1.0`
- Alembic：`1.19.1`
- pgvector：`0.5.0`
- Docker CLI：`29.7.2`
- Docker Compose：`5.4.0`
- Docker Buildx：`0.36.1`
- Colima：`0.10.3`
- Docker daemon：`29.5.2 linux/arm64`
- PostgreSQL pgvector extension：`0.8.6`

实际结果：

- `make setup`：通过。
- `make lint`：首次因脚本调用裸 pnpm 失败；改为 `corepack pnpm` 后通过。
- `make help`：通过。
- `make typecheck`：TypeScript 与 13 个 Python 源文件通过。
- `make test`：2 个 Web 测试、6 个 API 测试通过。
- `make build`：Next.js 生产构建和 Python 包导入通过。
- `make dev`：Web 与 API 实际启动。
- `make smoke`：Web、API live 与 ready=503 语义通过。
- `.next` 构建产物 Secret 扫描：未发现服务端配置名或示例秘密值。
- `make db-offline-sql`：生成 `CREATE EXTENSION vector` 和 Alembic head SQL。
- Compose YAML：五个服务、两个命名卷的结构断言通过。
- API ready 在无配置时返回 `not_configured`，真实依赖健康时返回 200。
- Redis 停止时 ready=503/`redis=unavailable`，恢复后 200。
- PostgreSQL 停止时 ready=503/`database=unavailable`，恢复后 200。
- revision 落后时 ready=503/`migration_pending`，升级后 200。
- migration downgrade/upgrade/current 循环通过，downgrade 不删除 pgvector。
- API、Worker、Web 镜像构建并在 Compose 中运行。
- `make contracts-check`：确定性契约无漂移。
- Worker：记录 `worker_started/worker_stopped`，SIGTERM 后退出码 0。
- Secret 扫描：通过。
- `pip-audit`：未发现已知漏洞。
- `pnpm audit --audit-level=high`：未发现已知漏洞。
- `make ci`：本地 CI 等价检查通过。

详细命令、退出码和结果见 [verification.md](../../specs/001-project-foundation/verification.md)。

## 6. 已知问题

1. 当前目录不是 Git 仓库，GitHub Actions workflow 尚未实际运行。
2. `SPEC-FND-AC-007` 中的分页和业务重试测试将在对应业务 Spec 落实。

因此 `SPEC-001` 仍为 `partial`，不是 `verified`；本地、容器和真实数据库可执行检查均通过。

## 7. 下一步

创建并评审 `SPEC-002`：

1. 用户、Session、会话和消息数据模型。
2. Cookie 认证、密码哈希、CSRF/Origin 和限流边界。
3. Repository 强制 `user_id` 作用域与跨用户测试。
4. 登录、会话列表和基础消息页面。

真实 PostgreSQL/Redis 已可用于 `SPEC-002` 的持久化与跨用户隔离测试。
