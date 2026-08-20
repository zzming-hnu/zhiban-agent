#!/usr/bin/env bash

set -euo pipefail

WEB_URL="${WEB_URL:-http://localhost:3000}"
API_URL="${API_URL:-http://localhost:8000/api/v1}"
EXPECTED_READY_STATUS="${EXPECTED_READY_STATUS:-503}"

echo "Checking Web: $WEB_URL"
curl --fail --silent --show-error "$WEB_URL" >/dev/null

echo "Checking API live: $API_URL/health/live"
curl --fail --silent --show-error "$API_URL/health/live" >/dev/null

echo "Checking API ready status: expected $EXPECTED_READY_STATUS"
READY_STATUS="$(curl --silent --output /dev/null --write-out "%{http_code}" "$API_URL/health/ready")"
if [[ "$READY_STATUS" != "$EXPECTED_READY_STATUS" ]]; then
  echo "Expected ready status $EXPECTED_READY_STATUS, got $READY_STATUS" >&2
  exit 1
fi

echo "Smoke checks passed"
