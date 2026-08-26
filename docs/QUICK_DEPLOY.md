# 知伴 · 云服务器快速部署指南（2C2G）

> 面向 2 核 2G 云服务器的一键部署步骤。全程在**你自己的服务器**上操作，密钥不外泄。

## 一、准备：三个 API 密钥

部署前先准备好这三个密钥（都是你已有的）：

| 密钥 | 来源 | 用途 |
|------|------|------|
| `LLM_API_KEY` | DeepSeek（platform.deepseek.com） | 对话模型 |
| `EMBEDDING_API_KEY` | 硅基流动（cloud.siliconflow.cn） | 记忆语义检索 |
| `SEARCH_API_KEY` | 博查 Bocha（open.bochaai.com） | 联网搜索 |

## 二、部署步骤

### 第 1 步：登录服务器

```bash
ssh 用户名@你的服务器IP
```

### 第 2 步：下载部署脚本

```bash
cd ~
curl -fsSL https://raw.githubusercontent.com/zzming-hnu/zhiban-agent/main/deploy.sh -o deploy.sh
```

> 如果 GitHub 下载慢，也可以：先在本地把项目 `deploy.sh` 用 `scp` 传到服务器：
> ```bash
> scp deploy.sh 用户名@服务器IP:~/deploy.sh
> ```

### 第 3 步：设置密钥并运行

```bash
# 把下面三个密钥替换成你自己的（用环境变量传入，不写死在脚本里）
export LLM_API_KEY="sk-你的deepseek密钥"
export EMBEDDING_API_KEY="sk-你的硅基流动密钥"
export SEARCH_API_KEY="sk-你的bocha密钥"

# （可选）如果你的服务器有域名，可以指定：
# export PUBLIC_IP="你的域名"

# 执行部署（会自动装 Docker、拉代码、配置、启动）
bash deploy.sh
```

首次构建约 5~10 分钟（要下载 Docker 镜像 + 构建前端）。

### 第 4 步：验证

```bash
# 健康检查
curl http://localhost:8000/api/v1/health/live
# 应该返回 {"status":"ok",...}

# 查看日志（确认无报错）
docker compose -f ~/zhiban-agent/infra/compose/compose.prod.yml logs -f
```

### 第 5 步：访问

- **Web 页面**：`http://你的服务器IP:3000`
- **API 文档**：`http://你的服务器IP:8000/api/docs`

## 三、安全组/防火墙配置

在云服务器控制台的**安全组**里，放行以下端口：

| 端口 | 用途 | 建议 |
|------|------|------|
| 3000 | Web 前端 | 对公网开放 |
| 8000 | API | 对公网开放（或只对前端反代开放） |
| 5432 | PostgreSQL | **不要对公网开放** |
| 6379 | Redis | **不要对公网开放** |

## 四、常用运维命令

```bash
cd ~/zhiban-agent

# 查看服务状态
docker compose -f infra/compose/compose.prod.yml ps

# 查看日志
docker compose -f infra/compose/compose.prod.yml logs -f

# 重启
docker compose -f infra/compose/compose.prod.yml restart

# 停止
docker compose -f infra/compose/compose.prod.yml down

# 更新到最新代码并重建
git pull
docker compose -f infra/compose/compose.prod.yml up -d --build
```

## 五、生产安全提醒

1. **数据库密码和 SESSION_SECRET** 由脚本自动生成随机值，无需手动设置。
2. 如果要用**域名 + HTTPS**，建议在前面加一层 Nginx/Caddy 反代，只需暴露 3000/8000。
3. 数据库（5432）、Redis（6379）端口**不要对公网开放**，否则有安全风险。
4. 邮件提醒（SMTP）默认关闭，站内提醒正常可用；如需邮件，在 `.env` 里填 SMTP 配置。

## 六、故障排查

| 现象 | 排查 |
|------|------|
| 前端能打开但请求失败 | 检查 `NEXT_PUBLIC_API_BASE_URL` 是否指向服务器公网 IP |
| 搜索没结果 | 检查 `SEARCH_API_KEY` 是否有效、服务器能否访问 `api.bochaai.com` |
| 记忆检索失败 | 检查 `EMBEDDING_API_KEY` 是否有效、能否访问 `api.siliconflow.cn` |
| 内存不足 | `docker stats` 查看各容器内存，`dmesg | grep -i oom` 看是否 OOM |
