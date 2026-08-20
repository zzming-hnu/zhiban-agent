FROM ghcr.io/astral-sh/uv:0.11.11 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH="/app/apps/api/src" \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY apps/api ./apps/api

EXPOSE 8000

CMD ["uvicorn", "zhiban.main:app", "--app-dir", "apps/api/src", "--host", "0.0.0.0", "--port", "8000"]
