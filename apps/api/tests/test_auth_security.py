"""Unit tests for auth security primitives (no database)."""

from zhiban.auth.security import (
    generate_session_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)


def test_password_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_password_hashes_use_distinct_salts() -> None:
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second


def test_needs_rehash_accepts_current_argon2() -> None:
    assert not needs_rehash(hash_password("new-password"))


def test_needs_rehash_flags_non_argon2() -> None:
    assert needs_rehash("$2b$12$notargon2")


def test_session_token_is_random_and_hashable() -> None:
    first = generate_session_token()
    second = generate_session_token()
    assert first != second
    assert len(first) >= 40
    assert hash_token(first) != hash_token(second)
    assert hash_token(first) == hash_token(first)
