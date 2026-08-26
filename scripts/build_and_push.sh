#!/bin/bash
# Build the app & web images locally and push them to GHCR.
#
# Usage (run on your laptop, not the server):
#   1. docker login ghcr.io -u zzming-hnu   (enter a GHCR token)
#   2. bash scripts/build_and_push.sh
#
# The images are then pulled on the 2C2G server via compose.prod-run.yml.

set -euo pipefail

GHCR="ghcr.io/zzming-hnu/zhiban-agent"

cd "$(dirname "$0")/.."

echo "==> 构建 app 镜像（api + worker）..."
docker build -f infra/docker/api-prod.Dockerfile -t "$GHCR/app:latest" .

echo "==> 构建 web 镜像（Next.js）..."
docker build \
  -f infra/docker/web.Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://47.253.234.149:8000/api/v1}" \
  -t "$GHCR/web:latest" .

echo "==> 推送到 GHCR..."
docker push "$GHCR/app:latest"
docker push "$GHCR/web:latest"

echo ""
echo "完成！镜像已推送到："
echo "  $GHCR/app:latest"
echo "  $GHCR/web:latest"
