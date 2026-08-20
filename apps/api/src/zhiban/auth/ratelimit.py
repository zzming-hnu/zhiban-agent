"""Simple fixed-window rate limiting with in-process fallback."""

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import Request

from zhiban.core.errors import AppError

logger = structlog.get_logger(__name__)

# In-process fallback state used when Redis is unavailable.
_fallback: dict[str, deque[float]] = defaultdict(deque)


@dataclass(frozen=True, slots=True)
class RateRule:
    key: str
    limit: int
    window_seconds: int


def _redis_client(request: Request) -> Any:
    return request.app.state.resources.redis._client


async def _check_redis(rule: RateRule, request: Request) -> bool:
    client = _redis_client(request)
    if client is None:
        return False
    now = time.time()
    key = f"rate:{rule.key}:{int(now // rule.window_seconds)}"
    try:
        count = int(await client.incr(key))
        if count == 1:
            await client.expire(key, rule.window_seconds + 60)
        return count <= rule.limit
    except Exception as error:  # Redis failure degrades to in-process counting.
        await logger.awarning("rate_limit_redis_failed", error_type=type(error).__name__)
        return False


def _check_in_process(rule: RateRule) -> bool:
    now = time.time()
    window = _fallback[rule.key]
    while window and now - window[0] > rule.window_seconds:
        window.popleft()
    if len(window) >= rule.limit:
        return False
    window.append(now)
    return True


async def enforce(rule: RateRule, request: Request) -> None:
    allowed = await _check_redis(rule, request)
    if allowed:
        return
    # Redis unavailable (not over-limit): fall back to in-process counting.
    if _check_in_process(rule):
        return
    raise AppError(
        code="rate_limited",
        message="请求过于频繁，请稍后再试",
        status_code=429,
        retryable=True,
    )
