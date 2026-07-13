from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.pricing_review_contracts import (
    PricingCandidateReportListResponse,
    PricingCandidateReportResponse,
    PricingReviewDecisionCreate,
    PricingReviewDecisionListResponse,
    PricingReviewDecisionResponse,
    PricingTraceResponse,
)
from src.services.errors import (
    PricingRefreshRunNotFound,
    PricingReviewReportNotFound,
    PricingReviewRequestError,
)
from src.services.pricing_review_service import PricingReviewService


router = APIRouter(prefix="/optimizer/pricing-review", tags=["optimizer"])


def get_pricing_review_service(db: Session = Depends(get_db)) -> PricingReviewService:
    return PricingReviewService(db)


@router.get(
    "/{provider}/candidate-reports",
    response_model=PricingCandidateReportListResponse,
    operation_id="listPricingCandidateReports",
    summary="List secret-free pricing candidate reports for a refresh run",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def list_pricing_candidate_reports(
    provider: str,
    refresh_run_id: str = Query(..., description="Pricing refresh run id"),
    service: PricingReviewService = Depends(get_pricing_review_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return service.list_candidate_reports(provider, refresh_run_id, current_user.id)
    except PricingRefreshRunNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except PricingReviewRequestError as exc:
        raise HTTPException(status_code=400, detail=exc.message)


@router.get(
    "/candidate-reports/{report_id}",
    response_model=PricingCandidateReportResponse,
    operation_id="getPricingCandidateReport",
    summary="Get one secret-free pricing candidate report",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def get_pricing_candidate_report(
    report_id: str,
    service: PricingReviewService = Depends(get_pricing_review_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return service.get_candidate_report(report_id, current_user.id)
    except PricingReviewReportNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.get(
    "/candidate-reports/{report_id}/trace",
    response_model=PricingTraceResponse,
    operation_id="getPricingCandidateReportTrace",
    summary="Get the sanitized pricing intent-to-result trace for one report",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def get_pricing_candidate_report_trace(
    report_id: str,
    service: PricingReviewService = Depends(get_pricing_review_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return service.get_trace(report_id, current_user.id)
    except PricingReviewReportNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.post(
    "/decisions",
    response_model=PricingReviewDecisionResponse,
    operation_id="createPricingReviewDecision",
    summary="Persist a user-reviewed pricing candidate decision",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def create_pricing_review_decision(
    request: PricingReviewDecisionCreate,
    service: PricingReviewService = Depends(get_pricing_review_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return service.create_decision(request, current_user.id)
    except PricingReviewReportNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except PricingReviewRequestError as exc:
        raise HTTPException(status_code=400, detail=exc.message)


@router.get(
    "/decisions",
    response_model=PricingReviewDecisionListResponse,
    operation_id="listPricingReviewDecisions",
    summary="List user-reviewed pricing candidate decisions",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
    },
)
async def list_pricing_review_decisions(
    provider: str | None = Query(default=None, description="Optional provider filter"),
    service: PricingReviewService = Depends(get_pricing_review_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return service.list_decisions(current_user.id, provider=provider)
    except PricingReviewRequestError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
