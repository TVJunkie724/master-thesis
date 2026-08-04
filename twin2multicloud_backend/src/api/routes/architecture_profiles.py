"""Authenticated architecture profile, selection, and resolution APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.architecture_profile import (
    ArchitectureProfileChangePreviewResponse,
    ArchitectureProfileChangeRequest,
    ArchitectureProfileDetailResponse,
    ArchitectureErrorResponse,
    ArchitectureProfileSelectionRequest,
    ArchitectureProfileSelectionResult,
    ArchitectureProfileSummaryResponse,
    ResolvedArchitectureReadResponse,
    TwinArchitectureSelectionResponse,
)
from src.services.architecture_profile_service import ArchitectureProfileService
from src.services.resolved_architecture_service import ResolvedArchitectureService


router = APIRouter(tags=["architecture-profiles"])
ARCHITECTURE_ERROR_RESPONSES = {
    status: {
        "description": description,
        "model": ArchitectureErrorResponse,
    }
    for status, description in {
        403: "The architecture selection cannot be changed in its current state",
        404: "The owner-scoped architecture resource was not found",
        409: "The architecture state conflicts with the requested operation",
    }.items()
}


@router.get(
    "/architecture-profiles",
    response_model=list[ArchitectureProfileSummaryResponse],
    operation_id="listArchitectureProfiles",
    summary="List active reviewed architecture profile versions",
    responses={401: ERROR_RESPONSES[401]},
)
async def list_architecture_profiles(
    _current_user: User = Depends(get_current_user),
) -> list[ArchitectureProfileSummaryResponse]:
    return ArchitectureProfileService().list_profiles()


@router.get(
    "/architecture-profiles/{profile_id}/versions/{profile_version}",
    response_model=ArchitectureProfileDetailResponse,
    operation_id="getArchitectureProfileVersion",
    summary="Get one active reviewed architecture profile version",
    responses={
        401: ERROR_RESPONSES[401],
        404: ARCHITECTURE_ERROR_RESPONSES[404],
        409: ARCHITECTURE_ERROR_RESPONSES[409],
    },
)
async def get_architecture_profile(
    profile_id: str,
    profile_version: str,
    _current_user: User = Depends(get_current_user),
) -> ArchitectureProfileDetailResponse:
    return ArchitectureProfileService().get_profile(
        profile_id,
        profile_version,
    )


@router.get(
    "/twins/{twin_id}/architecture-profile",
    response_model=TwinArchitectureSelectionResponse,
    operation_id="getTwinArchitectureProfile",
    summary="Get the pinned architecture profile selected for a Twin",
    responses={
        401: ERROR_RESPONSES[401],
        404: ARCHITECTURE_ERROR_RESPONSES[404],
    },
)
async def get_twin_architecture_profile(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwinArchitectureSelectionResponse:
    return ArchitectureProfileService(db).get_selection(
        twin_id=twin_id,
        user_id=current_user.id,
    )


@router.post(
    "/twins/{twin_id}/architecture-profile/change-preview",
    response_model=ArchitectureProfileChangePreviewResponse,
    operation_id="previewTwinArchitectureProfileChange",
    summary="Preview exact server-derived profile-change invalidations",
    responses={
        401: ERROR_RESPONSES[401],
        404: ARCHITECTURE_ERROR_RESPONSES[404],
        409: ARCHITECTURE_ERROR_RESPONSES[409],
    },
)
async def preview_twin_architecture_profile_change(
    twin_id: str,
    request: ArchitectureProfileChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArchitectureProfileChangePreviewResponse:
    return ArchitectureProfileService(db).preview_change(
        twin_id=twin_id,
        user_id=current_user.id,
        profile_id=request.profile_id,
        profile_version=request.profile_version,
        expected_revision=request.expected_revision,
    )


@router.put(
    "/twins/{twin_id}/architecture-profile",
    response_model=ArchitectureProfileSelectionResult,
    operation_id="selectTwinArchitectureProfile",
    summary="Select an active profile using revision and preview digest",
    responses={
        401: ERROR_RESPONSES[401],
        403: ARCHITECTURE_ERROR_RESPONSES[403],
        404: ARCHITECTURE_ERROR_RESPONSES[404],
        409: ARCHITECTURE_ERROR_RESPONSES[409],
    },
)
async def select_twin_architecture_profile(
    twin_id: str,
    request: ArchitectureProfileSelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArchitectureProfileSelectionResult:
    return ArchitectureProfileService(db).select_profile(
        twin_id=twin_id,
        user_id=current_user.id,
        profile_id=request.profile_id,
        profile_version=request.profile_version,
        expected_revision=request.expected_revision,
        invalidation_digest=request.invalidation_digest,
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
