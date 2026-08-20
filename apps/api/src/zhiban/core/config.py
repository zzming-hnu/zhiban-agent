from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated process settings shared by the API and worker."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    demo_mode: bool = True

    web_origin: str = "http://localhost:3000"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)

    session_secret: SecretStr = SecretStr("development-only-change-me-32-chars")
    database_url: SecretStr | None = None
    redis_url: SecretStr | None = None
    alembic_config_path: str = "apps/api/alembic.ini"
    readiness_timeout_seconds: float = Field(default=1.0, gt=0, le=5)

    llm_provider: str = "mock"
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    # Comma-separated selectable models (e.g. "deepseek-v4-flash,deepseek-v4-pro").
    llm_models: str = ""
    # Reasoning effort: "low" | "medium" | "high", or None for provider default.
    llm_reasoning_effort: str | None = None
    llm_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    # Summary model (rolling summary / compaction) is independently configurable
    # so a faster/cheaper model can be used without changing the main chat model.
    summary_llm_model: str | None = None
    summary_llm_base_url: str | None = None
    summary_llm_api_key: SecretStr | None = None

    # Embedding model for semantic memory retrieval.
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str = "https://qproxy.gtimg.com/v1"
    embedding_api_key: SecretStr | None = None

    # Bounded agent loop.
    agent_total_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    agent_max_tool_rounds: int = Field(default=4, ge=1, le=20)
    agent_max_tool_calls_per_run: int = Field(default=8, ge=1, le=50)
    agent_final_round_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    # Sub-agent routing: when enabled, memory operations are delegated to the
    # MemoryAgent instead of being handled by the main agent's own tools.
    agent_use_subagent: bool = True

    # Context budget (conservative approximation, no external tokenizer).
    model_context_window: int = Field(default=32768, ge=1024)
    output_reserve_tokens: int = Field(default=4096, ge=256)
    context_soft_threshold_ratio: float = Field(default=0.70, gt=0, le=1)
    context_hard_threshold_ratio: float = Field(default=0.85, gt=0, le=1)
    context_compact_target_ratio: float = Field(default=0.65, gt=0, le=1)
    context_keep_recent_turns: int = Field(default=4, ge=1, le=20)
    summary_budget_tokens: int = Field(default=1800, ge=256)
    tool_results_budget_tokens: int = Field(default=2200, ge=256)

    search_provider: str = "mock"
    search_api_key: SecretStr | None = None
    search_base_url: str = "http://localhost:8888"

    # Email (SMTP) delivery for reminders. When smtp_enabled is False (default),
    # reminder delivery stays in-app only (toast + browser notification).
    smtp_enabled: bool = False
    smtp_host: str = "smtp.example.com"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "知伴 <no-reply@example.com>"
    smtp_use_tls: bool = True

    @model_validator(mode="after")
    def validate_thresholds(self) -> "Settings":
        if not (
            self.context_compact_target_ratio
            < self.context_soft_threshold_ratio
            < self.context_hard_threshold_ratio
        ):
            raise ValueError("context thresholds must satisfy compact_target < soft < hard")
        return self

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env != "production":
            return self

        session_secret = self.session_secret.get_secret_value()
        if len(session_secret) < 32 or session_secret.startswith("development-only"):
            raise ValueError(
                "SESSION_SECRET must be a production secret with at least 32 characters"
            )
        if self.database_url is None:
            raise ValueError("DATABASE_URL is required in production")
        if self.redis_url is None:
            raise ValueError("REDIS_URL is required in production")
        if self.llm_provider != "mock" and self.llm_api_key is None:
            raise ValueError("LLM_API_KEY is required for a non-mock LLM provider")
        if self.search_provider not in ("mock", "searxng") and self.search_api_key is None:
            raise ValueError("SEARCH_API_KEY is required for this search provider")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
