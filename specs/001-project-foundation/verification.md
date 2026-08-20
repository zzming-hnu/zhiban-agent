# SPEC-001 验证记录

## 1. 当前状态

| 字段 | 值 |
|---|---|
| Spec 状态 | `partial` |
| 实现状态 | T0~T6 实现任务全部完成 |
| 验证结论 | 本地、容器、在线数据库与故障恢复均通过；仅远程 GitHub Actions 未执行，因此暂不标记 `verified` |
| 记录日期 | 2026-08-17 |

## 2. 环境预检

工作目录：`/Users/zzming/work`

### 2.1 Node 与 pnpm

命令：

```bash
node --version && pnpm --version && python3 --version && uv --version && docker --version
```

实际结果：

```text
v24.14.1
(eval):1: command not found: pnpm
```

退出码：`127`

说明：Node 可用；命令在 pnpm 缺失处停止，后续工具改为独立检查。pnpm 需要通过 Corepack 激活。

### 2.2 Python

命令：

```bash
python3 --version
```

实际结果：

```text
Python 3.9.6
```

退出码：`0`

说明：系统 Python 低于目标 3.12。实现必须由 uv 管理项目 Python，不能直接使用系统解释器。

### 2.3 uv

命令：

```bash
uv --version
```

实际结果：

```text
uv 0.11.11 (Homebrew 2026-05-06 aarch64-apple-darwin)
```

退出码：`0`

### 2.4 Docker

命令：

```bash
docker --version
```

实际结果：

```text
(eval):1: command not found: docker
```

退出码：`127`

说明：当前机器无法运行 Docker Compose。后续可以创建并静态检查 Compose 配置，但实际容器验证在 Docker 可用前必须标为未执行。

### 2.5 Corepack

命令：

```bash
corepack --version
```

实际结果：

```text
0.34.6
```

退出码：`0`

说明：可以通过 Corepack 管理并锁定 pnpm。

### 2.6 项目管理的实际工具链

项目锁定结果：

```text
Node.js 24.14.1
pnpm 11.22.0
Python 3.12.13
uv 0.11.11
ruff 0.16.3
mypy 2.3.1
pytest 9.1.1
```

验证命令：

```bash
corepack pnpm --version
uv run python --version
uv run ruff --version
uv run mypy --version
uv run pytest --version
```

以上命令退出码均为 `0`。

依赖下载过程：

1. 默认 PyPI 下载 `ruff/mypy` 长时间无进展。
2. 一次用户中断后的 `uv sync` 进程未真正退出，导致后续进程等待 `.venv` 锁。
3. 清理残留 `uv` 进程后，使用清华 PyPI 镜像完成同步：

```bash
env UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple" \
  UV_HTTP_TIMEOUT=30 \
  uv sync --all-groups
```

退出码：`0`。实际安装 12 个开发依赖包。为避免后续重复卡在默认源，`pyproject.toml` 记录清华镜像为默认索引；环境仍可用 `UV_DEFAULT_INDEX` 覆盖，最终版本由 `uv.lock` 固定。

## 3. T1 工具链验证

### 3.1 锁定安装、Lint 与命令入口

首次执行：

```bash
make setup && make lint && make help
```

结果：`make setup` 成功，`make lint` 失败。原因是根 `package.json` 的脚本调用裸 `pnpm`，当前环境只有 Corepack，没有全局 pnpm shim。

修复：根脚本统一改为 `corepack pnpm ...`。

修复后再次执行同一命令，退出码 `0`：

```text
pnpm frozen lockfile: 已是最新
uv frozen sync: Checked 12 packages
pnpm recursive lint: 当前尚无子项目
ruff check .: All checks passed
make help: 成功输出稳定命令列表
```

### 3.2 未完成应用的防误用

命令：

```bash
make dev
```

实际结果：

```text
scripts/dev.sh 将在 Web/API 骨架完成后提供
make: *** [dev] Error 2
```

退出码：`2`，符合预期。工程尚无可运行应用时必须明确失败，不能输出虚假的启动成功。

## 4. T2/T3 Web、API 与 Worker 验证

### 4.1 Web 脚手架

使用 `create-next-app@latest` 生成 Next.js App Router 工程。生成器成功创建文件，但在内部执行裸 `pnpm install` 时因当前环境没有全局 pnpm shim 失败：

```text
Error: spawn pnpm ENOENT
```

处理方式：

1. 保留生成器已创建的源码和配置。
2. 删除嵌套的 `apps/web/pnpm-workspace.yaml`，由根 workspace 统一管理。
3. 将构建脚本依赖迁移到根 Corepack/pnpm。
4. 使用 npm 镜像在根目录完成依赖安装。

该失败没有被记为脚手架成功；依赖安装完成并通过构建后才勾选 T2。

实际锁定的主要 Web 版本：

```text
Next.js 16.3.1
React 19.2.8
TypeScript 5.9.3
Vitest 4.1.10
```

### 4.2 API 与 Worker

实际锁定的主要 Python 版本：

```text
FastAPI 0.141.1
Uvicorn 0.52.3
Pydantic 2.13.4
Pydantic Settings 2.15.0
Structlog 26.1.0
HTTPX2 2.10.0
```

已验证行为：

- `GET /api/v1/health/live` 返回 200、服务名、版本和 `x-request-id`。
- `GET /api/v1/health/ready` 在数据库/Redis 尚未接入时诚实返回 503。
- 非法客户端 request ID 被替换。
- 未处理异常返回统一安全 envelope，不返回原异常正文。
- Production 设置拒绝开发 Session Secret 和缺失依赖配置。
- Worker 入口可独立导入，且 import 阶段不连接网络。

### 4.3 首轮失败与修复

首轮 Lint 发现：

- FastAPI `Depends` 默认参数触发 Ruff `B008`。
- 一处超长配置错误文案。
- 三处测试 import 顺序问题。

修复后 Ruff 与 ESLint 均通过。

首轮 TypeScript 检查发现：

1. `@vitejs/plugin-react` 最新版本使用当前 TypeScript 不能解析的声明语法。Vitest 不依赖该插件即可处理本项目 JSX，因此删除该非必要依赖。
2. Next 生成的全局 `LayoutProps` 在单独运行 `tsc` 前尚未生成。改为显式 `ReactNode` Props，避免类型检查依赖构建顺序。
3. `create-next-app` 的 `"typescript": "^5"` 被解析为 5.0.2，低于 Next 推荐版本。查询包管理器后锁定最新兼容 5.x：5.9.3。

首轮 API 测试出现 Starlette 对旧 `httpx` 的弃用警告。按 FastAPI 版本提示替换为 `httpx2` 后，测试无警告。

### 4.4 最终质量结果

命令：

```bash
make lint && make typecheck && make test && make build && make smoke
```

退出码：`0`。

结果：

```text
ESLint: passed
Ruff: passed
TypeScript: passed
Mypy: 13 source files, no issues
Vitest: 2 files / 2 tests passed
Pytest: 6 tests passed
Next.js build: / and /api-status generated
Python package import: passed
Smoke: Web、API live、API ready=503 均符合预期
Web .next bundle secret scan: no matches
```

### 4.5 可见运行效果

开发服务已实际启动：

- Web：`http://localhost:3000`
- 工程状态页：`http://localhost:3000/api-status`
- API live：`http://localhost:8000/api/v1/health/live`
- API 文档：`http://localhost:8000/api/docs`

Next.js 启动时自动生成了 `AGENTS.md/CLAUDE.md`。项目已有独立 Spec 规范，因此设置 `agentRules: false` 并删除自动文件，避免产生第二套冲突规则。

## 5. T4 基础设施、迁移与 Readiness 验证

### 5.1 环境能力

实际检查：

```text
docker: command not found
podman: command not found
colima: command not found
psql: command not found
redis-server: command not found
```

因此本机不能执行真实 PostgreSQL/Redis、镜像构建或 Compose 健康检查。T4 采用“实现完成 + 静态/离线/Mock 验证 + 明确环境缺口”的方式交付。

### 5.2 锁定依赖与基础设施配置

新增运行依赖：

```text
SQLAlchemy 2.0.52
asyncpg 0.31.0
redis 8.1.0
Alembic 1.19.1
pgvector 0.5.0
```

Compose 定义：

- `pgvector/pgvector:pg17`
- `redis:7.4-alpine`
- API、Worker 和 Web 应用镜像
- PostgreSQL/Redis 命名卷与健康检查

Dockerfile 运行验证未执行。Next.js 本地 standalone 构建确认生成 `apps/web/.next/standalone/apps/web/server.js`，与 Web Dockerfile 启动路径一致。

### 5.3 Alembic

初始 head：

```text
20260817_0001
```

离线命令：

```bash
make db-offline-sql
```

退出码：`0`。输出包含：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
INSERT INTO alembic_version (version_num) VALUES ('20260817_0001');
```

Downgrade 明确不执行 `DROP EXTENSION`，避免删除共享数据库中由其他应用使用的 pgvector。

在线 `upgrade/downgrade/current` 未执行，因为本机没有 PostgreSQL。不能据离线 SQL 宣称真实迁移已成功。

### 5.4 动态 Readiness

Readiness 不在 import 时联网；应用 lifespan 只创建惰性客户端。当前无数据库/Redis 配置时，实际响应：

```json
{
  "status": "not_ready",
  "checks": {
    "configuration": "ok",
    "database": "not_configured",
    "migrations": "not_configured",
    "redis": "not_configured"
  }
}
```

自动化测试另覆盖：

- 数据库/Redis 均健康且 revision 等于 head：200 + `ready`。
- 数据库或 Redis 抛出连接错误：503 + `unavailable`。
- 数据库可用但 revision 不等于 head：503 + `migration_pending`。
- 探针受 `READINESS_TIMEOUT_SECONDS` 限制。

### 5.5 静态与质量验证

Compose YAML 使用 PyYAML 解析并断言五个服务、两个命名卷，退出码 `0`。

`make infra-up` 在当前环境按设计失败：

```text
未安装 Docker；请安装后再运行基础设施
```

退出码：`2`。没有进入无限等待或伪造容器启动。

完整命令：

```bash
make lint && make typecheck && make test && make build && make db-offline-sql && make smoke
```

退出码：`0`：

```text
ESLint / Ruff: passed
TypeScript: passed
Mypy: 19 source files, no issues
Vitest: 2 tests passed
Pytest: 11 tests passed
Next.js standalone build: passed
Alembic offline SQL: passed
Web/API smoke: passed
```

## 6. T5/T6 契约、CI 与安全验证

### 6.1 OpenAPI 与 TypeScript 契约

产物：

- `packages/contracts/openapi.json`
- `packages/contracts/src/api.ts`
- `packages/contracts/dist/`

版本：

```text
openapi-typescript 7.13.0
TypeScript 5.9.3
```

`make contracts-check` 不依赖 Git：它在临时目录重新导出 OpenAPI、重新生成 TypeScript，再逐字节比较两个已提交产物。

实际结果：

```text
contract drift check: passed
```

当前目录不是 Git 仓库，因此没有使用 `git diff --exit-code` 伪装漂移门禁。

### 6.2 Worker 独立入口

实际运行 `make dev-worker` 后观察到：

```json
{"service":"worker","message":"worker_started"}
{"service":"worker","message":"worker_stopped"}
```

向 Python Worker 发送 SIGTERM 后，进程记录停止事件并以退出码 `0` 结束。

### 6.3 Secret 与依赖审计

首次 JavaScript 审计使用 npm 镜像时失败：

```text
ERR_PNPM_AUDIT_ENDPOINT_NOT_EXISTS
```

原因是镜像不实现 npm security audit endpoint，不是漏洞命中。依赖下载继续使用镜像，仅审计请求切换到 npm 官方安全端点。

最终结果：

```text
high-confidence secret scan: passed
pip-audit: No known vulnerabilities found
pnpm audit --audit-level=high: No known vulnerabilities found
```

`pip-audit` 设置 15 秒网络超时，避免审计服务异常导致无限等待。“未发现已知漏洞”不等于代码绝对安全，只代表当前数据库和锁定依赖未命中已知项。

### 6.4 CI

新增：

- `.github/workflows/ci.yml`
- `scripts/ci.sh`
- `make ci`

GitHub workflow 包含 pgvector PostgreSQL 与 Redis services，并配置在线 migration、ready 和完整质量检查。YAML 结构解析通过。

当前目录不是 Git 仓库，workflow 没有被 GitHub 实际执行，因此远程 CI 状态为“未执行”。

本地 `make ci` 实际退出码为 `0`，覆盖：

```text
frozen dependency install
contract drift
ESLint / Ruff / Ruff format
TypeScript / generated contract types / Mypy
2 Web tests / 11 API tests
Web + contract production build
Python package import
Alembic offline SQL
Web/API smoke
Secret scan
pip-audit / pnpm audit
```

### 6.5 最终本地结果

所有本地可执行任务已通过。未执行项只与缺少 Docker/真实 PostgreSQL/Redis/Git 远程有关，没有把它们记为成功。

## 7. 文档验证

当前已完成：

- `specs/README.md`：Spec 状态、目录、编号、DoR、DoD 和验证规则。
- `specs/001-project-foundation/spec.md`：工程基础规范。
- `specs/001-project-foundation/tasks.md`：实现任务拆分。
- `docs/progress/001-project-foundation.md`：过程记录。
- 根 README：Spec 驱动入口。
- Web、API、Contracts、Infra 与 Scripts README：实际命令和限制。
- Markdown 代码围栏、编号和相对链接静态检查已完成。
- IDE 文档诊断：无错误。

待执行：GitHub Actions 远程 workflow。当前目录不是 Git 仓库，无法获得远程 CI 结果。

## 8. 验收状态

| 验收 ID | 状态 | 证据 |
|---|---|---|
| `SPEC-FND-AC-001` | 通过 | 锁定安装、宿主机启动、镜像构建和完整容器启动均已验证 |
| `SPEC-FND-AC-002` | 通过 | Web、FastAPI 与 Worker 入口均已创建 |
| `SPEC-FND-AC-003` | 通过 | 真实数据库、Redis、migration head 健康时 ready=200；异常时 ready=503 |
| `SPEC-FND-AC-004` | 通过 | 在线 upgrade/current/downgrade/upgrade 通过，pgvector 0.8.6 可用 |
| `SPEC-FND-AC-005` | 通过 | 真实 Redis/PostgreSQL 停止、检测、恢复和 Smoke 通过 |
| `SPEC-FND-AC-006` | 通过 | 统一错误中间件与异常安全测试通过 |
| `SPEC-FND-AC-007` | 部分 | 设置、request ID、错误、健康、迁移和契约测试已建立；分页/重试在业务 Spec 实现 |
| `SPEC-FND-AC-008` | 部分 | 含在线迁移的本地 CI 等价检查通过；GitHub workflow 未实际运行 |
| `SPEC-FND-AC-009` | 通过 | `.env.example` 无真实秘密，服务端变量未出现在 `.next` 构建产物 |
| `SPEC-FND-AC-010` | 通过 | 下载、配置、迁移、镜像和测试中的失败均有记录并完成修复 |

## 9. 容器与数据库环境补验

### 9.1 安装结果

通过 Homebrew/官方 Release 安装：

```text
Docker CLI 29.7.2
Docker Compose 5.4.0
Docker Buildx 0.36.1
Colima 0.10.3
Lima 2.2.0
Docker daemon 29.5.2 linux/arm64
```

Colima 使用 macOS Virtualization.Framework、arm64、4 CPU、6 GiB 内存。未信任或禁用 Homebrew 的第三方 tap 安全检查。

默认 Homebrew GHCR 下载长时间无进展后，改用清华 Bottle 镜像；镜像缺失的 Compose 插件从 Docker 官方 GitHub Release 下载。旧 Docker Desktop 配置引用不存在的 `docker-credential-desktop`，只移除了失效 `credsStore` 字段，保留其余配置。

### 9.2 真实基础设施

Compose 实际拉起：

```text
postgres: pgvector/pgvector:pg17, healthy
redis: redis:7.4-alpine, healthy
api: zhiban-api, healthy
worker: zhiban-worker, running
web: zhiban-web, healthy
```

PostgreSQL 中 pgvector 扩展版本：`0.8.6`。Redis 返回 `PONG`。

### 9.3 在线迁移与 Readiness

首次在线 migration 发现 `sqlalchemy[asyncio]` 缺失 `greenlet`；依赖从基础 `sqlalchemy` 修正为官方 asyncio extra 后通过。

实际验证：

- `upgrade -> current(head)`：通过。
- `downgrade -> upgrade -> current(head)`：通过。
- downgrade 后 pgvector 仍为 0.8.6，没有错误删除共享扩展。
- revision 落后时：`database=ok`、`migrations=migration_pending`、HTTP 503。
- 升级到 head 后：全部 `ok`、HTTP 200。
- Redis 停止时：`redis=unavailable`、HTTP 503；恢复后 200。
- PostgreSQL 停止时：`database/migrations=unavailable`、HTTP 503；恢复后 200。

### 9.4 完整镜像

API、Worker、Web 三个镜像均实际构建。首次 Web standalone 容器暴露 pnpm symlink 的 `@swc/helpers` 目标未打包；仅声明直接依赖仍不足，最终在 builder 使用 `pnpm deploy --prod` 提供完整生产 node_modules 后，Web 容器健康。

镜像结果：

```text
zhiban-api:latest
zhiban-worker:latest
zhiban-web:latest
```

完整容器栈 `EXPECTED_READY_STATUS=200 make smoke` 通过。

### 9.5 环境化测试隔离

创建本地 `.env` 后，本地 CI 首次暴露测试仍受进程环境变量影响。所有“无配置”测试改为显式覆盖数据库、Redis、Provider Key 和开发 Secret，确保测试在有无 `.env` 时结果一致。

最终 `make ci` 在真实 PostgreSQL/Redis 环境下通过：

```text
2 Web tests passed
11 API tests passed
online migration at head
ready HTTP 200
contract/lint/type/build/security all passed
```

## 10. 最终结论与补验条件

`SPEC-001` 状态为 `partial`：

- 实现任务 T0~T6 全部完成。
- 本地 CI 等价检查与完整容器栈通过。
- 产品基础页面和 API 持续可运行。
- 真实 migration、pgvector、Redis 和依赖故障恢复通过。
- GitHub 远程 CI 尚未执行。

升级为 `verified` 需要补充：

1. Git 仓库连接 GitHub 后运行 workflow 并通过。
2. 在后续业务 Spec 中落实分页与重试基础测试，关闭 `SPEC-FND-AC-007` 的剩余项。

这些补验不阻塞开始 `SPEC-002`；真实持久化环境已经可用。
