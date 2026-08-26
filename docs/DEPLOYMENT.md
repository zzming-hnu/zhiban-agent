# 知伴 · 部署与依赖迁移指南

> 本文档说明如何从 GitHub 拉取代码后，在全新环境完成部署。重点关注「哪些依赖无法上传 GitHub，需要自行下载/配置」。

## 1. 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Node.js | >= 22 | 前端 + pnpm |
| pnpm | 11.x（corepack 提供） | 包管理器 |
| Python | 3.12（<3.13） | 后端 |
| uv | 最新 | Python 包管理器 |
| Docker / Colima | 最新 | 基础设施容器（macOS 用 Colima） |
| PostgreSQL + pgvector | 16/17 | 数据库（Docker 提供） |
| Redis | 7.x | 缓存/队列（Docker 提供） |

## 2. 需要自行获取的「密钥/服务」（无法上传 GitHub）

> ⚠️ 这些是**隐私信息**，项目 `.env` 中已全部置空。拉取代码后需要自己填写。

### 2.1 DeepSeek API Key

```bash
# .env
LLM_API_KEY=你的DeepSeek密钥    # 到 platform.deepseek.com 申请
```

### 2.2 Embedding API Key

记忆检索用 **BAAI/bge-m3**（1024 维），默认走硅基流动（SiliconFlow，国内直连、免费模型）：

```bash
# .env
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=你的siliconflow密钥
```

> 也可换成其他 OpenAI 兼容的 embedding 服务，但需保证向量维度与数据库列一致（当前为 1024 维，见迁移 `20260823_0011`）。

### 2.3 邮件 SMTP 授权码（可选）

邮件提醒需要 SMTP 服务。QQ 邮箱为例：

```bash
# .env
SMTP_ENABLED=true
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USERNAME=你的邮箱@qq.com
SMTP_PASSWORD=你的授权码    # 邮箱设置里生成，不是登录密码
SMTP_FROM=知伴 <你的邮箱@qq.com>
```

### 2.4 搜索服务

项目用 **Bocha 博查搜索 API**（国内直连，返回结构化结果）：

```bash
# .env
SEARCH_PROVIDER=bocha
SEARCH_API_KEY=你的bocha密钥    # open.bochaai.com 申请
```

> 也支持 `SEARCH_PROVIDER=searxng`（需自建 SearXNG）或 `mock`（无网络时）。生产环境推荐 Bocha，无需自建搜索服务、省内存。

## 3. 依赖安装（有锁文件，可复现）

### 3.1 Python

```bash
uv sync --all-groups --frozen
```

依赖锁定在 `uv.lock`，`pyproject.toml` 声明了所有依赖。

### 3.2 Node

```bash
corepack pnpm install --frozen-lockfile
```

依赖锁定在 `pnpm-lock.yaml`。

> 注意：`pyproject.toml` 里配置了清华 PyPI 镜像（`pypi.tuna.tsinghua.edu.cn`）。如果海外环境拉取慢，可删除 `[[tool.uv.index]]` 段。

## 4. 2C2G 小主机部署（生产精简版）

针对 2 核 2G 云服务器，提供了专门的精简 compose：`infra/compose/compose.prod.yml`。

相比开发版 `compose.yml` 的降级点：

| 优化 | 说明 |
|------|------|
| 移除 SearXNG | 联网搜索改用 Bocha API，省 300~600MB |
| api + worker 合并 | 同镜像双进程，省一个 Python 解释器内存 |
| PostgreSQL 调优 | `shared_buffers=128MB`、`max_connections=20`（见 `postgres-small.conf`） |
| 内存上限 | 每服务 `mem_limit`（postgres 512m / redis 256m / app 512m / web 384m） |
| Redis 内存上限 | `maxmemory 128mb` + `allkeys-lru` 淘汰策略 |

优化后总内存约 **800MB~1GB**，2G 主机可稳定运行。

```bash
# 1. 配置环境变量（生产密钥）
cp .env.example .env
# 编辑 .env，至少填入：
#   SESSION_SECRET（随机串）、POSTGRES_PASSWORD
#   LLM_API_KEY、EMBEDDING_API_KEY、SEARCH_API_KEY

# 2. 构建并启动（精简版）
docker compose -f infra/compose/compose.prod.yml up -d --build

# 3. 验证
curl http://localhost:8000/api/v1/health/live
# Web: http://<服务器IP>:3000
```

> ⚠️ 生产注意事项：
> - 务必替换默认数据库密码和 `SESSION_SECRET`
> - 若用 Nginx 反代，只需暴露 3000/8000 端口，`5432`/`6379` 端口可不对公网开放

## 5. 完整部署步骤

### 5.1 一键 Docker Compose（推荐）

```bash
# 1. 配置 .env（复制 .env.example 并填写密钥）
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 等

# 2. 启动完整栈
make stack-build
make stack-up

# 3. 验证
make smoke
```

### 5.2 宿主机开发模式

```bash
# 1. 启动基础设施（Postgres + Redis）
colima start          # macOS
make infra-up

# 2. 安装依赖
make setup

# 3. 启动开发进程
make dev
```

### 5.3 数据库迁移

```bash
make db-upgrade        # 升级到最新
make db-current        # 查看当前版本
```

## 6. 验证

```bash
make test              # 全部自动化测试
make ci                # 本地 CI 等价检查
make security-check    # 密钥扫描 + 依赖审计
make smoke             # 冒烟测试
make e2e               # 浏览器端到端
```

## 7. 演示数据

```bash
make seed-demo         # 创建 demo-a/demo-b 演示账号
make reset-demo        # 清空演示账号
```

## 8. 隐私说明

- `.env` 已被 `.gitignore` 排除，真实密钥不会上传
- `.env.example` 是模板（占位符，无真实密钥）
- 提交前建议跑 `make security-check` 确认无密钥泄露
- 数据库密码 `zhiban_dev_only` 是本地开发占位，生产必须更换
