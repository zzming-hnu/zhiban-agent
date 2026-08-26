#!/bin/sh
# Start API (uvicorn) and Worker (background) in the same container to save
# memory on small (2C2G) hosts. The worker consumes jobs/outbox; its load is
# low for single-user deployments.
set -e

# Run database migrations before serving.
alembic -c apps/api/alembic.ini upgrade head

# Start the background job worker (memory extraction, reminders).
python -m zhiban.workers.main &
WORKER_PID=$!

# Ensure the worker is stopped when the container's main process exits.
trap 'kill $WORKER_PID 2>/dev/null || true' EXIT INT TERM

# Start the API in the foreground (container's main process).
exec uvicorn zhiban.main:app --app-dir apps/api/src --host 0.0.0.0 --port 8000
