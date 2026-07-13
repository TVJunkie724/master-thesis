import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.clients.optimizer_client import OptimizerClient
from src.models.database import get_db
from src.models.user import User
from src.schemas.pricing_refresh import (
    PricingRefreshRunResponse,
    PricingRefreshStartRequest,
)
from src.services.errors import (
    PricingRefreshConnectionNotFound,
    PricingRefreshRequestError,
    PricingRefreshRunNotFound,
)
from src.services.pricing_refresh_run_service import PricingRefreshRunService


router = APIRouter(prefix="/optimizer/pricing-refresh", tags=["optimizer"])


def get_optimizer_client() -> OptimizerClient:
    return OptimizerClient()


def get_pricing_refresh_run_service(
    db: Session = Depends(get_db),
    optimizer_client: OptimizerClient = Depends(get_optimizer_client),
) -> PricingRefreshRunService:
    return PricingRefreshRunService(db, optimizer_client=optimizer_client)


@router.post(
    "/{provider}",
    response_model=PricingRefreshRunResponse,
    operation_id="startPricingRefreshRun",
    summary="Start a typed provider pricing refresh run",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def start_pricing_refresh_run(
    provider: str,
    request: PricingRefreshStartRequest,
    service: PricingRefreshRunService = Depends(get_pricing_refresh_run_service),
    current_user: User = Depends(get_current_user),
):
    try:
        run = await service.create_run(provider, current_user.id, request)
        return service.to_response(run)
    except PricingRefreshConnectionNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except PricingRefreshRequestError as exc:
        raise HTTPException(status_code=400, detail=exc.message)


@router.get(
    "/runs/{refresh_run_id}",
    response_model=PricingRefreshRunResponse,
    operation_id="getPricingRefreshRun",
    summary="Get a typed provider pricing refresh run",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def get_pricing_refresh_run(
    refresh_run_id: str,
    service: PricingRefreshRunService = Depends(get_pricing_refresh_run_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return service.to_response(service.get_run(refresh_run_id, current_user.id))
    except PricingRefreshRunNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.get(
    "/runs/{refresh_run_id}/stream",
    operation_id="streamPricingRefreshRun",
    summary="Stream the current state of a typed provider pricing refresh run",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def stream_pricing_refresh_run(
    refresh_run_id: str,
    service: PricingRefreshRunService = Depends(get_pricing_refresh_run_service),
    current_user: User = Depends(get_current_user),
):
    try:
        response = service.to_response(service.get_run(refresh_run_id, current_user.id))
    except PricingRefreshRunNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)

    async def event_generator():
        payload = response.model_dump(mode="json")
        yield f"event: refresh_status\ndata: {json.dumps(payload)}\n\n"
        final_event = "error" if response.status == "failed" else "complete"
        yield f"event: {final_event}\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
