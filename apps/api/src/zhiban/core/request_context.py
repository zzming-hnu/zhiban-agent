import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from fastapi import Request, Response

logger = structlog.get_logger(__name__)

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def resolve_request_id(candidate: str | None) -> str:
    if candidate and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return f"req_{uuid4().hex}"


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.method == "OPTIONS":
        return await call_next(request)

    request_id = resolve_request_id(request.headers.get("x-request-id"))
    request.state.request_id = request_id
    started = time.perf_counter()

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    try:
        response = await call_next(request)
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        await logger.ainfo(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
        )
        structlog.contextvars.clear_contextvars()

    response.headers["x-request-id"] = request_id
    return response
