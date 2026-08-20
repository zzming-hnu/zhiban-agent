"""Create LLM adapters based on settings (main chat + summary + embedding)."""

from zhiban.core.config import Settings
from zhiban.llm.base import LLMAdapter
from zhiban.llm.embedding import EmbeddingAdapter
from zhiban.llm.mock import MockLLMAdapter
from zhiban.llm.openai_adapter import OpenAIAdapter


def _build_openai(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout_seconds: float,
    max_retries: int,
    reasoning_effort: str | None = None,
) -> OpenAIAdapter:
    return OpenAIAdapter(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout_seconds,
        max_retries=max_retries,
        reasoning_effort=reasoning_effort,
    )


def available_models(settings: Settings) -> list[str]:
    """Return the list of models the user may select (used by /models and validation)."""
    models = [m.strip() for m in settings.llm_models.split(",") if m.strip()]
    if settings.llm_model and settings.llm_model not in models:
        models.append(settings.llm_model)
    return models


def _resolve_model(settings: Settings, model: str | None) -> str:
    """Resolve the requested model against the configured allow-list."""
    allowed = available_models(settings)
    if model and model in allowed:
        return model
    return settings.llm_model


def create_llm_adapter(settings: Settings, model: str | None = None) -> LLMAdapter:
    if settings.llm_provider == "mock":
        return MockLLMAdapter()

    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
    resolved = _resolve_model(settings, model)
    return _build_openai(
        api_key=api_key,
        base_url=settings.llm_base_url,
        model=resolved,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        reasoning_effort=settings.llm_reasoning_effort,
    )


def create_summary_adapter(settings: Settings, model: str | None = None) -> LLMAdapter:
    """Create the adapter used for rolling-summary compaction.

    Falls back to the main chat model when no summary model is configured.
    When the main chat model is selected (no dedicated summary model), it
    follows the per-run model so summaries match the user's chosen model.
    """
    if settings.summary_llm_model is None:
        return create_llm_adapter(settings, model=model)

    if settings.llm_provider == "mock":
        return MockLLMAdapter()

    api_key = (
        settings.summary_llm_api_key.get_secret_value()
        if settings.summary_llm_api_key
        else (settings.llm_api_key.get_secret_value() if settings.llm_api_key else "")
    )
    base_url = settings.summary_llm_base_url or settings.llm_base_url
    return _build_openai(
        api_key=api_key,
        base_url=base_url,
        model=settings.summary_llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        reasoning_effort=settings.llm_reasoning_effort,
    )


def create_embedding_adapter(settings: Settings) -> EmbeddingAdapter:
    """Create the embedding adapter for semantic memory retrieval.

    The API key falls back to the main LLM key (same gateway) when not set.
    """
    api_key = (
        settings.embedding_api_key.get_secret_value()
        if settings.embedding_api_key
        else (settings.llm_api_key.get_secret_value() if settings.llm_api_key else "")
    )
    return EmbeddingAdapter(
        api_key=api_key,
        base_url=settings.embedding_base_url,
        model=settings.embedding_model,
    )
