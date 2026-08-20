from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from zhiban.api.router import api_router
from zhiban.core.config import Settings, get_settings
from zhiban.core.errors import install_exception_handlers
from zhiban.core.request_context import request_context_middleware
from zhiban.core.resources import AppResources
from zhiban.observability.logging import configure_logging


def create_app(
    settings: Settings | None = None,
    resources: AppResources | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(
        log_level=resolved_settings.log_level,
        service="api",
        environment=resolved_settings.app_env,
        version=resolved_settings.app_version,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_resources = resources is None
        app.state.resources = resources or AppResources.from_settings(resolved_settings)
        try:
            yield
        finally:
            if owns_resources:
                await app.state.resources.close()

    app = FastAPI(
        title="知伴 API",
        version=resolved_settings.app_version,
        docs_url="/api/docs" if resolved_settings.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if resolved_settings.app_env != "production" else None,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.dependency_overrides[get_settings] = lambda: resolved_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Idempotency-Key",
            "X-CSRF-Token",
            "X-Request-ID",
        ],
    )
    app.middleware("http")(request_context_middleware)
    install_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
