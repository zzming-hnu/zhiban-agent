"""Password hashing and session token primitives."""

import hashlib
import hmac
import secrets

from passlib.hash import argon2  # type: ignore[import-untyped]


def hash_password(plain: str) -> str:
    """Hash a password with Argon2id (the project-standard scheme)."""
    return argon2.hash(plain)  # type: ignore[no-any-return]


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against an Argon2id hash."""
    if not hashed.startswith("$argon2"):
        return False
    try:
        return argon2.verify(plain, hashed)  # type: ignore[no-any-return]
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed: str) -> bool:
    """Return True when a stored hash is not the current preferred scheme."""
    if not hashed.startswith("$argon2"):
        return True
    return bool(argon2.needs_update(hashed))


def generate_session_token() -> str:
    """Generate a URL-safe random session token (32 bytes, base64url)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a session/refresh token with SHA-256 for at-rest storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
