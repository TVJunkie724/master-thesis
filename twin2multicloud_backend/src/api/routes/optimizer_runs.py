from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.clients.optimizer_client import OptimizerClient
from src.models.cost_calculation import CostCalculationResultItem, CostCalculationRun
from src.models.database import get_db
from src.models.user import User
from src.schemas.cost_calculation import (
    CostCalculationResultItemResponse,
    CostCalculationRunCreate,
    CostCalculationRunDetailResponse,
    CostCalculationRunSelectResponse,
    CostCalculationRunSummaryResponse,
    PricingEvidenceDetailResponse,
)
from src.schemas.resolved_deployment_specification import (
    ResolvedDeploymentSpecification,
)
from src.services.cost_calculation_run_service import (
    CostCalculationRunService,
    _json_loads,
    safe_pricing_catalog_context,
    validate_persisted_run_deployment_specification,
)
from src.services.errors import (
    CostCalculationRunSelectionError,
    ExternalServiceError,
    ExternalServiceUnavailable,
    OptimizerContractError,
    PricingCatalogUnavailable,
    TwinNotFound,
)


router = APIRouter(prefix="/twins/{twin_id}/optimizer-runs", tags=["optimizer-runs"])


def get_optimizer_client() -> OptimizerClient:
    return OptimizerClient()


def get_cost_calculation_run_service(
    db: Session = Depends(get_db),
    optimizer_client: OptimizerClient = Depends(get_optimizer_client),
) -> CostCalculationRunService:
    return CostCalculationRunService(db, optimizer_client=optimizer_client)


@router.post(
    "/",
    response_model=CostCalculationRunDetailResponse,
    operation_id="createOptimizerRun",
    summary="Run optimizer calculation and persist typed history",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        502: {"description": "Optimizer contract or service error"},
        503: {"description": "Optimizer unavailable"},
    },
)
async def create_optimizer_run(
    twin_id: str,
    request: CostCalculationRunCreate,
    service: CostCalculationRunService = Depends(get_cost_calculation_run_service),
    current_user: User = Depends(get_current_user),
):
    try:
        run = await service.create_run(
            twin_id,
            current_user.id,
            request.params,
            pricing_evidence_version=request.pricing_evidence_version,
        )
        return _run_detail_response(run)
    except TwinNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ExternalServiceUnavailable:
        raise HTTPException(
            status_code=503,
            detail=_error_detail("OPTIMIZER_UNAVAILABLE", "Optimizer service is unavailable."),
        )
    except ExternalServiceError:
        raise HTTPException(
            status_code=502,
            detail=_error_detail("OPTIMIZER_ERROR", "Optimizer service returned an error."),
        )
    except OptimizerContractError as exc:
        raise HTTPException(
            status_code=502,
            detail=_error_detail("OPTIMIZER_CONTRACT_INVALID", exc.message, exc.errors),
        )
    except PricingCatalogUnavailable as exc:
        raise HTTPException(
            status_code=409,
            detail=_error_detail(exc.error_code, exc.message),
        )


@router.get(
    "/",
    response_model=list[CostCalculationRunSummaryResponse],
    operation_id="listOptimizerRuns",
    summary="List persisted optimizer calculation runs for a twin",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def list_optimizer_runs(
    twin_id: str,
    service: CostCalculationRunService = Depends(get_cost_calculation_run_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return [_run_summary_response(run) for run in service.list_runs(twin_id, current_user.id)]
    except TwinNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.get(
    "/{run_id}",
    response_model=CostCalculationRunDetailResponse,
    operation_id="getOptimizerRun",
    summary="Get one persisted optimizer calculation run",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def get_optimizer_run(
    twin_id: str,
    run_id: str,
    service: CostCalculationRunService = Depends(get_cost_calculation_run_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return _run_detail_response(service.get_run(twin_id, current_user.id, run_id))
    except TwinNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.get(
    "/{run_id}/pricing-evidence",
    response_model=PricingEvidenceDetailResponse,
    operation_id="getOptimizerRunPricingEvidence",
    summary="Get persisted pricing evidence and intent trace for one optimizer run",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def get_optimizer_run_pricing_evidence(
    twin_id: str,
    run_id: str,
    service: CostCalculationRunService = Depends(get_cost_calculation_run_service),
    current_user: User = Depends(get_current_user),
):
    try:
        run = service.get_run(twin_id, current_user.id, run_id)
        detail = service.build_pricing_evidence_detail(run)
        return PricingEvidenceDetailResponse(
            **detail,
            result_items=[_result_item_response(item) for item in run.result_items],
        )
    except TwinNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.post(
    "/{run_id}/select-for-deployment",
    response_model=CostCalculationRunSelectResponse,
    operation_id="selectOptimizerRunForDeployment",
    summary="Select a successful optimizer run as deployment handoff source",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        409: ERROR_RESPONSES[409],
        502: {"description": "Pricing catalog verification failed"},
        503: {"description": "Optimizer unavailable"},
    },
)
async def select_optimizer_run_for_deployment(
    twin_id: str,
    run_id: str,
    service: CostCalculationRunService = Depends(get_cost_calculation_run_service),
    current_user: User = Depends(get_current_user),
):
    try:
        run = await service.select_for_deployment(
            twin_id,
            current_user.id,
            run_id,
        )
        return CostCalculationRunSelectResponse(
            run=_run_summary_response(run),
            selected_for_deployment_at=run.selected_for_deployment_at,
            resolved_deployment_specification=(
                validate_persisted_run_deployment_specification(
                    run
                ).specification
            ),
        )
    except TwinNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except CostCalculationRunSelectionError as exc:
        raise HTTPException(
            status_code=409,
            detail=_error_detail(exc.error_code, exc.message),
        )
    except ExternalServiceUnavailable:
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "OPTIMIZER_UNAVAILABLE",
                "Optimizer service is unavailable.",
            ),
        )
    except ExternalServiceError:
        raise HTTPException(
            status_code=502,
            detail=_error_detail(
                "OPTIMIZER_ERROR",
                "Optimizer service returned an error.",
            ),
        )
    except OptimizerContractError as exc:
        raise HTTPException(
            status_code=502,
            detail=_error_detail(
                "OPTIMIZER_CONTRACT_INVALID",
                exc.message,
                exc.errors,
            ),
        )


def _run_summary_response(run: CostCalculationRun) -> CostCalculationRunSummaryResponse:
    return CostCalculationRunSummaryResponse(
        id=run.id,
        twin_id=run.twin_id,
        user_id=run.user_id,
        optimizer_config_id=run.optimizer_config_id,
        status=run.status,
        cheapest_path=_json_loads(run.cheapest_path_json),
        total_monthly_cost=run.total_monthly_cost,
        currency=run.currency,
        optimization_profile_id=run.optimization_profile_id,
        optimization_profile_version=run.optimization_profile_version,
        scoring_strategy_id=run.scoring_strategy_id,
        calculation_model_version=run.calculation_model_version,
        pricing_registry_version=run.pricing_registry_version,
        pricing_evidence_version=run.pricing_evidence_version,
        pricing_run_reference=run.pricing_run_reference,
        pricing_catalog_context=safe_pricing_catalog_context(
            run.pricing_catalog_context_json
        ),
        deployment_specification_digest=run.deployment_specification_digest,
        deployment_specification_version=run.deployment_specification_version,
        deployment_compatibility_status=(
            run.deployment_compatibility_status or "legacy_not_deployable"
        ),
        created_at=run.created_at,
        completed_at=run.completed_at,
        selected_for_deployment_at=run.selected_for_deployment_at,
        error_code=run.error_code,
        error_message=run.error_message,
    )


def _run_detail_response(run: CostCalculationRun) -> CostCalculationRunDetailResponse:
    return CostCalculationRunDetailResponse(
        **_run_summary_response(run).model_dump(),
        params=_json_loads(run.params_json) or {},
        result_summary=_json_loads(run.result_summary_json),
        resolved_deployment_specification=_safe_deployment_specification(run),
        result_items=[_result_item_response(item) for item in run.result_items],
    )


def _safe_deployment_specification(
    run: CostCalculationRun,
) -> ResolvedDeploymentSpecification | None:
    raw = _json_loads(run.deployment_specification_json)
    if raw is None:
        return None
    try:
        return ResolvedDeploymentSpecification.model_validate(raw)
    except ValidationError:
        return None


def _result_item_response(
    item: CostCalculationResultItem,
) -> CostCalculationResultItemResponse:
    return CostCalculationResultItemResponse(
        id=item.id,
        run_id=item.run_id,
        layer=item.layer,
        component=item.component,
        provider=item.provider,
        service_intent_id=item.service_intent_id,
        cost_amount=item.cost_amount,
        currency=item.currency,
        unit=item.unit,
        quantity=item.quantity,
        unit_price=item.unit_price,
        evidence_id=item.evidence_id,
        service_model_id=item.service_model_id,
        calculation_notes=_json_loads(item.calculation_notes_json),
        review_status=item.review_status,
        created_at=item.created_at,
    )


def _error_detail(
    code: str,
    message: str,
    field_errors: list[dict] | None = None,
) -> dict:
    return {
        "error_code": code,
        "message": message,
        "fix_suggestion": "Check the optimizer service contract and retry the calculation.",
        "field_errors": field_errors or [],
    }
