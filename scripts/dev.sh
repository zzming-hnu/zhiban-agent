#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "${WEB_PID:-}" ]]; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Starting FastAPI on http://localhost:8000"
uv run uvicorn zhiban.main:app \
  --app-dir apps/api/src \
  --host 0.0.0.0 \
  --port 8000 \
  --reload &
API_PID=$!

echo "Starting Next.js on http://localhost:3000"
corepack pnpm --dir apps/web dev &
WEB_PID=$!

while kill -0 "$API_PID" 2>/dev/null && kill -0 "$WEB_PID" 2>/dev/null; do
  sleep 1
done

echo "A development process exited; stopping the remaining process." >&2
exit 1
