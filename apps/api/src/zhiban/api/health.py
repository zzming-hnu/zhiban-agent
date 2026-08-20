from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict

from zhiban.core.config import Settings, get_settings
from zhiban.core.readiness import CheckState, evaluate_readiness
from zhiban.core.resources import AppResources

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["api"] = "api"
    version: str


class ReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckState]


@router.get("/live", response_model=LiveResponse)
async def live(settings: Annotated[Settings, Depends(get_settings)]) -> LiveResponse:
    return LiveResponse(version=settings.app_version)


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
async def ready(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadyResponse:
    resources: AppResources = request.app.state.resources
    snapshot = await evaluate_readiness(
        resources,
        timeout_seconds=settings.readiness_timeout_seconds,
    )
    response.status_code = (
        status.HTTP_200_OK if snapshot.ready else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return ReadyResponse(
        status="ready" if snapshot.ready else "not_ready",
        checks=snapshot.checks,
    )
