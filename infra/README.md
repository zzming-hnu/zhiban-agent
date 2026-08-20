# 基础设施

- `compose/`：本地 PostgreSQL/pgvector、Redis 及应用服务编排。
- `docker/`：Web、API 和 Worker 镜像定义。

## 本地基础设施

```bash
colima start
make infra-up
make db-upgrade
make infra-logs
make infra-down
```

启动完整容器栈：

```bash
make stack-build
make stack-up
EXPECTED_READY_STATUS=200 make smoke
make stack-down
```

Compose 包含：

- PostgreSQL 17 + pgvector，命名卷持久化。
- Redis 7.4，AOF 持久化。
- FastAPI、Worker 和 Next.js 应用服务。

`make infra-reset` 会删除本地数据库和 Redis 卷；目标命令在 `APP_ENV=production` 时拒绝执行。

当前本机环境：

- Docker CLI 29.7.2
- Docker Compose 5.4.0
- Colima 0.10.3，macOS Virtualization.Framework / arm64
- Docker daemon 29.5.2

Compose 五个服务均已实际启动；PostgreSQL、Redis、API 和 Web 健康，Worker 正常运行。`make db-downgrade && make db-upgrade`、pgvector 0.8.6、依赖故障检测与恢复均已验证。
