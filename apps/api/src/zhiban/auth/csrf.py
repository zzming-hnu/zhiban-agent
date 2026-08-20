"""CSRF/Origin protection for cookie-authenticated state-changing requests."""

import secrets
from urllib.parse import urlparse

from fastapi import Request

from zhiban.core.errors import AppError

CSRF_COOKIE = "zhiban_csrf"
CSRF_HEADER = "X-CSRF-Token"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _origin_matches(request: Request, allowed_origin: str) -> bool:
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return False
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    return f"{parsed.scheme}://{parsed.netloc}" == allowed_origin


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf(request: Request, allowed_origin: str) -> None:
    """Reject cookie-authenticated state changes without a valid origin/token.

    Browsers always send an Origin header on cross-origin requests and on most
    same-origin state-changing requests. We require a matching Origin AND a
    matching double-submit CSRF token for cookie-authenticated writes.
    """
    if request.method in SAFE_METHODS:
        return

    if not _origin_matches(request, allowed_origin):
        raise AppError(code="csrf_origin_mismatch", message="请求来源不被允许", status_code=403)

    token = request.headers.get(CSRF_HEADER)
    cookie_token = request.cookies.get(CSRF_COOKIE)
    if not token or not cookie_token or not secrets.compare_digest(token, cookie_token):
        raise AppError(code="csrf_token_mismatch", message="CSRF 校验失败", status_code=403)
