# 项目脚本

本目录保存可重复、非交互的工程脚本。

- `dev.sh`：同时启动 Next.js 与 FastAPI，任一进程退出时清理另一进程。
- `smoke.sh`：验证 Web、API live，以及基础设施未接入前 ready 诚实返回 503。
- `export_openapi.py`：确定性导出 FastAPI OpenAPI。
- `check_contracts.py`：在临时目录重新生成并检查契约漂移。
- `check_secrets.py`：扫描高置信度密钥格式和误提交的 `.env`。
- `ci.sh`：执行本地 CI 等价检查，并复用或临时启动 Web/API。

后续业务阶段会增加数据库 Seed、演示数据重置和备份恢复演练。

脚本必须默认拒绝未知或生产环境的破坏性操作。
