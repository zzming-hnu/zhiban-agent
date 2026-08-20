#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DEV_PID=""
DEV_LOG="${TMPDIR:-/tmp}/zhiban-ci-dev.log"

cleanup() {
  if [[ -n "$DEV_PID" ]]; then
    kill "$DEV_PID" 2>/dev/null || true
    wait "$DEV_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

wait_for_url() {
  local url="$1"
  local attempts=30
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for $url" >&2
  if [[ -f "$DEV_LOG" ]]; then
    tail -n 80 "$DEV_LOG" >&2
  fi
  return 1
}

make setup
make contracts-check
make lint
make typecheck
make test
make build
make db-offline-sql >/dev/null

if [[ -n "${DATABASE_URL:-}" ]]; then
  make db-upgrade
  make db-current
fi

if ! curl --fail --silent "http://localhost:3000" >/dev/null 2>&1 ||
  ! curl --fail --silent "http://localhost:8000/api/v1/health/live" >/dev/null 2>&1; then
  make dev >"$DEV_LOG" 2>&1 &
  DEV_PID=$!
fi

wait_for_url "http://localhost:3000"
wait_for_url "http://localhost:8000/api/v1/health/live"

if [[ -n "${DATABASE_URL:-}" && -n "${REDIS_URL:-}" ]]; then
  EXPECTED_READY_STATUS=200 make smoke
else
  EXPECTED_READY_STATUS=503 make smoke
fi

make security-check
echo "local CI equivalent: passed"
