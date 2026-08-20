# API 与 Worker

`apps/api` 承载 FastAPI、领域模块、数据库迁移和 Worker。

代码使用 `src/zhiban` 布局：

- `api/`：HTTP/SSE 协议层。
- `core/`：配置、错误和依赖装配。
- `db/`：数据库连接与迁移支持。
- `observability/`：日志、指标和 Trace。
- `workers/`：后台任务入口。

## 当前接口

- `GET /api/v1/health/live`：进程存活，返回 200。
- `GET /api/v1/health/ready`：真实检查数据库、Alembic revision 和 Redis；未配置或不可用时返回 503。
- `/api/docs`：非生产环境 OpenAPI UI。

## 命令

从仓库根目录运行：

```bash
make dev-api
make dev-worker
make lint
make typecheck
make test
make db-offline-sql
```

API 不在 import 时连接外部依赖。数据库和 Redis 客户端只在应用 lifespan 中创建，网络连接由短超时 readiness 或业务操作触发。

初始 Alembic migration 启用 pgvector：

```bash
make infra-up
make db-upgrade
make db-current
```
