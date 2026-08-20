SHELL := /bin/bash

PNPM := corepack pnpm
UV := uv
COMPOSE := docker compose -f infra/compose/compose.yml

.DEFAULT_GOAL := help

.PHONY: help setup dev dev-web dev-api dev-worker format lint typecheck test build \
	db-upgrade db-downgrade db-current db-offline-sql infra-up infra-down infra-logs \
	infra-reset stack-build stack-up stack-down contracts contracts-check security-check ci smoke \
	seed-demo reset-demo e2e

help:
	@echo "知伴开发命令"
	@echo "  make setup         安装并同步 Node/Python 依赖"
	@echo "  make dev           启动本地开发进程（T2/T3 完成后可用）"
	@echo "  make lint          运行 TypeScript/Python Lint"
	@echo "  make typecheck     运行 TypeScript/Python 类型检查"
	@echo "  make test          运行全部自动化测试"
	@echo "  make build         构建 Web 并验证 Python 应用"
	@echo "  make db-upgrade    升级数据库到最新迁移"
	@echo "  make db-downgrade  回退一版数据库迁移"
	@echo "  make db-current    显示当前数据库迁移版本"
	@echo "  make db-offline-sql 生成离线迁移 SQL"
	@echo "  make infra-up      启动 PostgreSQL/pgvector 与 Redis"
	@echo "  make infra-down    停止本地基础设施"
	@echo "  make infra-logs    查看本地基础设施日志"
	@echo "  make stack-build   构建 Web/API/Worker 镜像"
	@echo "  make stack-up      启动并等待完整容器栈健康"
	@echo "  make stack-down    停止完整容器栈"
	@echo "  make contracts     重新生成 OpenAPI 与 TypeScript 契约"
	@echo "  make contracts-check 检查契约漂移"
	@echo "  make security-check 运行 Secret 与依赖审计"
	@echo "  make ci            运行本地 CI 等价检查"
	@echo "  make smoke         运行最小冒烟测试"
	@echo "  make seed-demo     创建演示账号与数据"
	@echo "  make reset-demo    清空演示账号与数据"
	@echo "  make e2e           运行浏览器端到端测试"

setup:
	$(PNPM) install --frozen-lockfile
	$(UV) sync --all-groups --frozen

dev:
	@test -x scripts/dev.sh || { echo "scripts/dev.sh 将在 Web/API 骨架完成后提供"; exit 2; }
	./scripts/dev.sh

dev-web:
	@test -f apps/web/package.json || { echo "apps/web 尚未初始化"; exit 2; }
	$(PNPM) --dir apps/web dev

dev-api:
	@test -f apps/api/src/zhiban/main.py || { echo "FastAPI 尚未初始化"; exit 2; }
	$(UV) run uvicorn zhiban.main:app --app-dir apps/api/src --reload --port 8000

dev-worker:
	@test -f apps/api/src/zhiban/workers/main.py || { echo "Worker 尚未初始化"; exit 2; }
	PYTHONPATH=apps/api/src $(UV) run python -m zhiban.workers.main

format:
	$(PNPM) -r --if-present format
	$(UV) run ruff format apps/api scripts

lint:
	$(PNPM) lint
	$(UV) run ruff check .
	$(UV) run ruff format --check apps/api scripts

typecheck:
	$(PNPM) typecheck
	$(UV) run mypy apps/api/src

test:
	$(PNPM) test
	$(UV) run pytest

build:
	$(PNPM) build
	$(UV) run python -c "import sys; sys.path.insert(0, 'apps/api/src'); import zhiban"

db-upgrade:
	$(UV) run alembic -c apps/api/alembic.ini upgrade head

db-downgrade:
	$(UV) run alembic -c apps/api/alembic.ini downgrade -1

db-current:
	$(UV) run alembic -c apps/api/alembic.ini current

db-offline-sql:
	$(UV) run alembic -c apps/api/alembic.ini upgrade head --sql

infra-up:
	@command -v docker >/dev/null || { echo "未安装 Docker；请安装后再运行基础设施"; exit 2; }
	$(COMPOSE) up -d postgres redis

infra-down:
	@command -v docker >/dev/null || { echo "未安装 Docker"; exit 2; }
	$(COMPOSE) down

infra-logs:
	@command -v docker >/dev/null || { echo "未安装 Docker"; exit 2; }
	$(COMPOSE) logs -f postgres redis

infra-reset:
	@command -v docker >/dev/null || { echo "未安装 Docker"; exit 2; }
	@test "$${APP_ENV:-development}" != "production" || { echo "拒绝清理生产环境"; exit 2; }
	$(COMPOSE) down --volumes

stack-build:
	@command -v docker >/dev/null || { echo "未安装 Docker"; exit 2; }
	$(COMPOSE) build api worker web

stack-up:
	@command -v docker >/dev/null || { echo "未安装 Docker"; exit 2; }
	$(COMPOSE) up -d --wait

stack-down:
	@command -v docker >/dev/null || { echo "未安装 Docker"; exit 2; }
	$(COMPOSE) down

contracts:
	$(UV) run python scripts/export_openapi.py
	$(PNPM) --filter @zhiban/contracts generate

contracts-check:
	$(UV) run python scripts/check_contracts.py

security-check:
	$(UV) run python scripts/check_secrets.py
	$(UV) run pip-audit --timeout 15
	$(PNPM) audit --audit-level=high --registry=https://registry.npmjs.org

ci:
	./scripts/ci.sh

smoke:
	@test -x scripts/smoke.sh || { echo "scripts/smoke.sh 将在健康接口完成后提供"; exit 2; }
	./scripts/smoke.sh

seed-demo:
	PYTHONPATH=apps/api/src $(UV) run python scripts/seed_demo.py

reset-demo:
	PYTHONPATH=apps/api/src $(UV) run python scripts/reset_demo.py

e2e:
	$(PNPM) --dir apps/web e2e
