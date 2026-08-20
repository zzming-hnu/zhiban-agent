# SPEC-001 任务清单

状态：`partial`

本清单只在完成真实变更和验证后勾选。任务按依赖顺序排列；同一组中标注“可并行”的项目可以并行。

## T0：规格准备

- [x] `FND-T000` 建立项目级 Spec 规范。
- [x] `FND-T001` 编写 `SPEC-001` 的目标、边界、要求和验收映射。
- [x] `FND-T002` 探测 Node、Corepack、Python、uv 与 Docker 当前环境。
- [x] `FND-T003` 实现开始时将 `spec.md` 状态改为 `in_progress`。

## T1：根工作区与工具链

- [x] `FND-T010` 初始化根 `package.json` 和 pnpm workspace。
- [x] `FND-T011` 使用 Corepack 激活并锁定 pnpm 实际版本。
- [x] `FND-T012` 初始化根 `pyproject.toml`，由 uv 锁定 Python 3.12 和依赖。
- [x] `FND-T013` 创建 `.gitignore`、`.editorconfig`、`.env.example`。
- [x] `FND-T014` 建立根 Makefile/等价统一命令。

依赖：T0。  
输出：可重复的 Node/Python 工具链与锁文件。

## T2：Web 骨架

- [x] `FND-T020` 创建 `apps/web` Next.js App Router 工程。
- [x] `FND-T021` 启用 TypeScript strict、ESLint 与格式化。
- [x] `FND-T022` 创建工程初始化页面、错误边界和基础测试。
- [x] `FND-T023` 验证公开环境变量与服务端变量边界。

依赖：T1。  
可并行：T3。

## T3：API 与 Worker 骨架

- [x] `FND-T030` 创建 `apps/api/src/zhiban` Python 包。
- [x] `FND-T031` 创建 FastAPI app factory 与 API 入口。
- [x] `FND-T032` 创建 Worker 独立入口和受控退出。
- [x] `FND-T033` 实现 Pydantic Settings、统一错误和 request_id。
- [x] `FND-T034` 实现结构化日志与字段脱敏基础。
- [x] `FND-T035` 实现 `live/ready` 健康接口及测试。

依赖：T1。  
可并行：T2、T4。

## T4：数据库、Redis 与迁移

- [x] `FND-T040` 创建 PostgreSQL/pgvector 与 Redis Compose 配置。
- [x] `FND-T041` 创建 API/Worker Dockerfile。
- [x] `FND-T042` 初始化 SQLAlchemy 与 Alembic。
- [x] `FND-T043` 创建启用 `vector` 扩展的初始迁移。
- [x] `FND-T044` 实现数据库、Redis 和迁移 ready 探针。
- [x] `FND-T045` 实现数据库 upgrade/downgrade/current 命令。

依赖：T1、T3 的配置接口。  
补验结果：Docker/Colima 环境已建立，Compose、在线 migration、镜像和真实 readiness 已验证。

## T5：契约与统一命令

- [x] `FND-T050` 创建 `packages/contracts` 和 OpenAPI 导出入口。
- [x] `FND-T051` 根命令聚合 setup/dev/lint/typecheck/test/build/migration/smoke。
- [x] `FND-T052` 验证 Web/API/Worker 的独立和聚合命令。
- [x] `FND-T053` 建立依赖、Secret 和基础静态扫描入口。

依赖：T2、T3、T4。

## T6：CI 与文档

- [x] `FND-T060` 添加 CI：安装、Lint、类型、测试、迁移、构建。
- [x] `FND-T061` 更新根 README 的实际快速开始与已知限制。
- [x] `FND-T062` 完成 `verification.md`，记录所有实际命令和结果。
- [x] `FND-T063` 更新 `docs/progress/001-project-foundation.md`。
- [x] `FND-T064` 对照验收表记录通过、失败和未执行项。

依赖：T1~T5。

## 完成规则

- `SPEC-FND-AC-001~010` 均已有真实结果。
- 当前所有实现、Docker、真实数据库和故障恢复验证完成。
- GitHub 远程 workflow 尚未执行，且分页/业务重试基础测试在后续 Spec 落实，因此状态仍为 `partial`。
