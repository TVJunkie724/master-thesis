"""Authenticated canonical architecture and resolution APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.architecture_profile import (
    ArchitectureProfileDetailResponse,
    ArchitectureErrorResponse,
    ResolvedArchitectureReadResponse,
    TwinArchitectureSelectionResponse,
)
from src.services.architecture_profile_service import ArchitectureProfileService
from src.services.resolved_architecture_service import ResolvedArchitectureService


router = APIRouter(tags=["architecture-contract"])
ARCHITECTURE_ERROR_RESPONSES = {
    status: {
        "description": description,
        "model": ArchitectureErrorResponse,
    }
    for status, description in {
        404: "The owner-scoped architecture resource was not found",
        409: "The architecture state conflicts with the requested operation",
    }.items()
}


@router.get(
    "/architecture-contract",
    response_model=ArchitectureProfileDetailResponse,
    operation_id="getCanonicalArchitectureContract",
    summary="Get the fixed Six-layer architecture contract",
    responses={
        401: ERROR_RESPONSES[401],
        404: ARCHITECTURE_ERROR_RESPONSES[404],
        409: ARCHITECTURE_ERROR_RESPONSES[409],
    },
)
async def get_architecture_contract(
    _current_user: User = Depends(get_current_user),
) -> ArchitectureProfileDetailResponse:
    return ArchitectureProfileService().get_profile()


@router.get(
    "/twins/{twin_id}/architecture-contract",
    response_model=TwinArchitectureSelectionResponse,
    operation_id="getTwinArchitectureContract",
    summary="Get the canonical architecture contract pinned to a Twin",
    responses={
        401: ERROR_RESPONSES[401],
        404: ARCHITECTURE_ERROR_RESPONSES[404],
    },
)
async def get_twin_architecture_contract(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwinArchitectureSelectionResponse:
    return ArchitectureProfileService(db).get_selection(
        twin_id=twin_id,
        user_id=current_user.id,
    )


@router.get(
    "/twins/{twin_id}/resolved-architecture",
    response_model=ResolvedArchitectureReadResponse,
    operation_id="getSelectedTwinResolvedArchitecture",
    summary="Get the immutable architecture of the selected calculation run",
    responses={
        401: ERROR_RESPONSES[401],
        404: ARCHITECTURE_ERROR_RESPONSES[404],
        409: ARCHITECTURE_ERROR_RESPONSES[409],
    },
)
async def get_selected_twin_resolved_architecture(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResolvedArchitectureReadResponse:
    return ResolvedArchitectureService(db).get_for_selected_twin(
        twin_id=twin_id,
        user_id=current_user.id,
    )


@router.get(
    "/optimizer-runs/{run_id}/resolved-architecture",
    response_model=ResolvedArchitectureReadResponse,
    operation_id="getOptimizerRunResolvedArchitecture",
    summary="Get the immutable architecture of one owner-scoped calculation run",
    responses={
        401: ERROR_RESPONSES[401],
        404: ARCHITECTURE_ERROR_RESPONSES[404],
        409: ARCHITECTURE_ERROR_RESPONSES[409],
    },
)
async def get_optimizer_run_resolved_architecture(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResolvedArchitectureReadResponse:
    return ResolvedArchitectureService(db).get_for_run(
        calculation_run_id=run_id,
        user_id=current_user.id,
    )
