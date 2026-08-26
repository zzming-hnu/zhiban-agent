#!/bin/bash
# 知伴一键部署脚本（适用于 2C2G 云服务器）
#
# 用法：
#   1. 把本脚本放到服务器上（或直接在服务器上 git clone 项目后用项目内的 deploy.sh）
#   2. 设置环境变量（见下方"需要配置"），或运行后按提示填写
#   3. 执行：bash deploy.sh
#
# 需要配置（通过环境变量传入，避免密钥写死在脚本里）：
#   LLM_API_KEY         DeepSeek 密钥
#   EMBEDDING_API_KEY   硅基流动密钥
#   SEARCH_API_KEY      Bocha 搜索密钥
#   (可选) DOMAIN       服务器域名或公网 IP，用于前端访问 API

set -euo pipefail

# ---------------------------------------------------------------------------
# 0. 配置项
# ---------------------------------------------------------------------------
REPO_URL="https://github.com/zzming-hnu/zhiban-agent.git"
APP_DIR="${APP_DIR:-$HOME/zhiban-agent}"

# 公网访问地址（前端浏览器访问 API 用）。默认用服务器公网 IP，可覆盖。
PUBLIC_IP="${PUBLIC_IP:-$(curl -s --max-time 5 ifconfig.me || echo 'localhost')}"
WEB_ORIGIN="${WEB_ORIGIN:-http://${PUBLIC_IP}:3000}"
NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://${PUBLIC_IP}:8000/api/v1}"

# 密钥（从环境变量读取，未设置则生成随机值）
LLM_API_KEY="${LLM_API_KEY:-}"
EMBEDDING_API_KEY="${EMBEDDING_API_KEY:-}"
SEARCH_API_KEY="${SEARCH_API_KEY:-}"
SESSION_SECRET="${SESSION_SECRET:-$(openssl rand -hex 32)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 16)}"

# ---------------------------------------------------------------------------
# 1. 检查 Docker
# ---------------------------------------------------------------------------
log() { echo -e "\033[1;32m[deploy]\033[0m $*"; }
warn() { echo -e "\033[1;33m[warn]\033[0m $*"; }

log "检查 Docker..."
if ! command -v docker >/dev/null 2>&1; then
  warn "未检测到 Docker，开始安装..."
  if command -v apt-get >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
  elif command -v yum >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
  else
    echo "不支持的包管理器，请手动安装 Docker：https://docs.docker.com/engine/install/"
    exit 1
  fi
  systemctl enable --now docker 2>/dev/null || true
fi

# 检查 docker compose 插件
if ! docker compose version >/dev/null 2>&1; then
  warn "缺少 docker compose 插件，请手动安装：https://docs.docker.com/compose/install/"
  exit 1
fi

log "Docker 就绪：$(docker --version)"

# ---------------------------------------------------------------------------
# 2. 拉取代码
# ---------------------------------------------------------------------------
if [ -d "$APP_DIR/.git" ]; then
  log "项目已存在，拉取最新代码..."
  cd "$APP_DIR"
  git pull --ff-only
else
  log "克隆项目..."
  git clone "$REPO_URL" "$APP_DIR"
  cd "$APP_DIR"
fi

# ---------------------------------------------------------------------------
# 3. 生成 .env
# ---------------------------------------------------------------------------
log "生成 .env..."
cat > .env <<EOF
APP_ENV=production
APP_VERSION=0.1.0
LOG_LEVEL=INFO
DEMO_MODE=false
WEB_ORIGIN=${WEB_ORIGIN}
NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
API_HOST=0.0.0.0
API_PORT=8000
SESSION_SECRET=${SESSION_SECRET}
DATABASE_URL=postgresql+asyncpg://zhiban:${POSTGRES_PASSWORD}@postgres:5432/zhiban
REDIS_URL=redis://redis:6379/0
LLM_PROVIDER=deepseek
LLM_API_KEY=${LLM_API_KEY}
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_MODELS=deepseek-v4-flash,deepseek-v4-pro
LLM_REASONING_EFFORT=low
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
SEARCH_PROVIDER=bocha
SEARCH_API_KEY=${SEARCH_API_KEY}
SEARCH_BASE_URL=
SMTP_ENABLED=false
EOF

# 导出变量供 docker compose 使用（compose 的 ${...} 替换优先读 shell 环境变量）
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
export SESSION_SECRET
export WEB_ORIGIN
export NEXT_PUBLIC_API_BASE_URL

# ---------------------------------------------------------------------------
# 4. 构建并启动（精简版 compose）
# ---------------------------------------------------------------------------
log "构建并启动服务（首次构建约 5-10 分钟）..."
docker compose -f infra/compose/compose.prod.yml up -d --build

log "等待服务就绪..."
sleep 10

# ---------------------------------------------------------------------------
# 5. 验证
# ---------------------------------------------------------------------------
log "验证健康检查..."
if curl -sf http://localhost:8000/api/v1/health/live >/dev/null 2>&1; then
  log "✅ API 健康检查通过"
else
  warn "API 可能尚未就绪，稍等几秒后重试：curl http://localhost:8000/api/v1/health/live"
fi

echo ""
log "部署完成！"
echo "  Web 访问:  http://${PUBLIC_IP}:3000"
echo "  API 文档:  http://${PUBLIC_IP}:8000/api/docs"
echo ""
log "查看日志: docker compose -f infra/compose/compose.prod.yml logs -f"
