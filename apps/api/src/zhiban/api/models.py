"""Model listing endpoint: exposes the selectable chat models to the frontend."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from zhiban.core.config import Settings, get_settings
from zhiban.llm.factory import available_models

router = APIRouter(prefix="/models", tags=["models"])


class ModelView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str


class ModelsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ModelView]
    default: str


def _label(model: str) -> str:
    labels = {
        "deepseek-v4-flash": "DeepSeek V4 Flash（快）",
        "deepseek-v4-pro": "DeepSeek V4 Pro（强）",
        "deepseek-chat": "DeepSeek Chat",
        "deepseek-reasoner": "DeepSeek Reasoner",
        "kimi-k2.5": "Kimi K2.5",
        "gpt-4o-mini": "GPT-4o mini",
    }
    return labels.get(model, model)


@router.get("", response_model=ModelsResponse)
async def list_models(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ModelsResponse:
    models = available_models(settings)
    return ModelsResponse(
        data=[ModelView(id=m, label=_label(m)) for m in models],
        default=settings.llm_model,
    )
