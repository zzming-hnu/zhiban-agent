import pytest
from pydantic import ValidationError
from zhiban.core.config import Settings


def test_mock_providers_do_not_require_external_keys() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        llm_provider="mock",
        llm_api_key=None,
        search_provider="mock",
        search_api_key=None,
    )

    assert settings.llm_api_key is None
    assert settings.search_api_key is None


def test_production_rejects_development_secret() -> None:
    with pytest.raises(ValidationError, match="SESSION_SECRET"):
        Settings(
            _env_file=None,
            app_env="production",
            session_secret="development-only-change-me-32-chars",
            database_url="postgresql://example.invalid/zhiban",
            redis_url="redis://example.invalid/0",
        )
