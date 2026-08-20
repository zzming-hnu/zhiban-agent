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

当前记忆检索用 `text-embedding-3-small`（1536 维）。默认走腾讯网关，需自行提供。也可换成其他 OpenAI 兼容的 embedding 服务。

```bash
# .env
EMBEDDING_BASE_URL=你的embedding服务地址
EMBEDDING_API_KEY=你的embedding密钥
```

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

项目用 **SearXNG**（自建搜索），通过 Docker 启动（无需密钥）：

```bash
# 无需配置密钥，compose 里自带 searxng 服务
SEARCH_PROVIDER=searxng
SEARCH_BASE_URL=http://localhost:8888
```

无网络时切 `SEARCH_PROVIDER=mock`。

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

## 4. 完整部署步骤

### 4.1 一键 Docker Compose（推荐）

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

### 4.2 宿主机开发模式

```bash
# 1. 启动基础设施（Postgres + Redis）
colima start          # macOS
make infra-up

# 2. 安装依赖
make setup

# 3. 启动开发进程
make dev
```

### 4.3 数据库迁移

```bash
make db-upgrade        # 升级到最新
make db-current        # 查看当前版本
```

## 5. 验证

```bash
make test              # 全部自动化测试
make ci                # 本地 CI 等价检查
make security-check    # 密钥扫描 + 依赖审计
make smoke             # 冒烟测试
make e2e               # 浏览器端到端
```

## 6. 演示数据

```bash
make seed-demo         # 创建 demo-a/demo-b 演示账号
make reset-demo        # 清空演示账号
```

## 7. 隐私说明

- `.env` 已被 `.gitignore` 排除，真实密钥不会上传
- `.env.example` 是模板（占位符，无真实密钥）
- 提交前建议跑 `make security-check` 确认无密钥泄露
- 数据库密码 `zhiban_dev_only` 是本地开发占位，生产必须更换
