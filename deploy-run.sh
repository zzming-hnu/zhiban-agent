#!/bin/bash
# 服务器端：拉取预构建镜像并运行（不构建，适合 2C2G 小内存服务器）。
#
# 用法（在服务器上）：
#   1. 配置环境变量（见下方）
#   2. bash deploy-run.sh

set -euo pipefail

GHCR="ghcr.io/zzming-hnu/zhiban-agent"

# 公网地址（前端访问 API 用）
PUBLIC_IP="${PUBLIC_IP:-$(curl -s --max-time 5 ifconfig.me || echo 'localhost')}"

# 密钥（从环境变量读取，未设置则生成随机值）
SESSION_SECRET="${SESSION_SECRET:-$(openssl rand -hex 32)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 16)}"

log() { echo -e "\033[1;32m[deploy]\033[0m $*"; }

# ---------------------------------------------------------------------------
# 1. 登录 GHCR（拉私有镜像需要）
# ---------------------------------------------------------------------------
if [ -z "${GHCR_TOKEN:-}" ]; then
  log "提示：需要 GHCR Token 才能拉取私有镜像"
  log "请执行：export GHCR_TOKEN='ghp_xxx' 后重新运行，或手动 docker login ghcr.io"
  exit 1
fi
echo "$GHCR_TOKEN" | docker login ghcr.io -u zzming-hnu --password-stdin

# ---------------------------------------------------------------------------
# 2. 生成 .env（应用运行时读取）
# ---------------------------------------------------------------------------
log "生成 .env..."
cat > .env <<EOF
APP_ENV=production
APP_VERSION=0.1.0
LOG_LEVEL=INFO
DEMO_MODE=false
WEB_ORIGIN=http://${PUBLIC_IP}:3000
NEXT_PUBLIC_API_BASE_URL=http://${PUBLIC_IP}:8000/api/v1
API_HOST=0.0.0.0
API_PORT=8000
SESSION_SECRET=${SESSION_SECRET}
DATABASE_URL=postgresql+asyncpg://zhiban:${POSTGRES_PASSWORD}@postgres:5432/zhiban
REDIS_URL=redis://redis:6379/0
LLM_PROVIDER=deepseek
LLM_API_KEY=${LLM_API_KEY:-}
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_MODELS=deepseek-v4-flash,deepseek-v4-pro
LLM_REASONING_EFFORT=low
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=${EMBEDDING_API_KEY:-}
SEARCH_PROVIDER=bocha
SEARCH_API_KEY=${SEARCH_API_KEY:-}
SEARCH_BASE_URL=
SMTP_ENABLED=false
EOF

# 导出变量供 compose 使用
export SESSION_SECRET
export POSTGRES_PASSWORD
export LLM_API_KEY
export LLM_PROVIDER="deepseek"
export LLM_BASE_URL="https://api.deepseek.com"
export LLM_MODEL="deepseek-v4-flash"
export EMBEDDING_MODEL="BAAI/bge-m3"
export EMBEDDING_BASE_URL="https://api.siliconflow.cn/v1"
export EMBEDDING_API_KEY
export SEARCH_PROVIDER="bocha"
export SEARCH_API_KEY
export SEARCH_BASE_URL=""
export WEB_ORIGIN="http://${PUBLIC_IP}:3000"
export NEXT_PUBLIC_API_BASE_URL="http://${PUBLIC_IP}:8000/api/v1"

# ---------------------------------------------------------------------------
# 3. 拉取镜像并启动
# ---------------------------------------------------------------------------
log "拉取镜像..."
docker compose -f infra/compose/compose.prod-run.yml pull

log "启动服务..."
docker compose -f infra/compose/compose.prod-run.yml up -d

log "等待就绪..."
sleep 10

if curl -sf http://localhost:8000/api/v1/health/live >/dev/null 2>&1; then
  log "✅ 部署成功！"
  echo "  Web:  http://${PUBLIC_IP}:3000"
  echo "  API:  http://${PUBLIC_IP}:8000/api/docs"
else
  log "⚠️ 服务可能还在启动，稍后执行：docker compose -f infra/compose/compose.prod-run.yml logs -f"
fi
