from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = 400
    retryable: bool = False
    details: Sequence[dict[str, Any]] = field(default_factory=tuple)


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: Sequence[dict[str, Any]] = (),
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "req_unknown")
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": list(details),
                "retryable": retryable,
            },
            "request_id": request_id,
        },
        headers={"x-request-id": request_id},
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        return error_response(
            request,
            status_code=error.status_code,
            code=error.code,
            message=error.message,
            retryable=error.retryable,
            details=error.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in item["loc"]),
                "reason": item["type"],
            }
            for item in error.errors()
        ]
        return error_response(
            request,
            status_code=422,
            code="validation_error",
            message="请求参数不合法",
            details=details,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        await logger.aexception(
            "unhandled_exception",
            request_id=getattr(request.state, "request_id", None),
            error_type=type(error).__name__,
        )
        return error_response(
            request,
            status_code=500,
            code="internal_error",
            message="服务暂时无法处理该请求",
            retryable=False,
        )
