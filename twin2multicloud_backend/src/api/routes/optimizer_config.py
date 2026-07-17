from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import NoReturn

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.optimizer_config import (
    CheapestPathResponse,
    OptimizerConfigResponse,
    OptimizerParamsUpdate,
    OptimizerResultUpdate,
)
from src.services.optimizer_configuration_service import OptimizerConfigurationService
from src.services.errors import (
    ExternalServiceError,
    ExternalServiceUnavailable,
    OptimizerContractError,
    PricingCatalogUnavailable,
)
from src.services.service_errors import EntityNotFoundError

router = APIRouter(prefix="/twins/{twin_id}/optimizer-config", tags=["optimizer-config"])


def _get_service(db: Session) -> OptimizerConfigurationService:
    return OptimizerConfigurationService(db, TwinRepository(db))


def _raise_optimizer_config_error(exc: EntityNotFoundError) -> NoReturn:
    raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/",
    response_model=OptimizerConfigResponse,
    operation_id="getOptimizerConfig",
    summary="Get optimizer config for a twin",
    description=(
        "**Purpose:** Retrieve the full optimizer configuration including saved parameters, calculation results, and cheapest path.\n\n"
        "**When to call:** When loading Step 2 (Optimizer) screen to restore previous calculation state.\n\n"
        "**Response fields:**\n"
        "- `params`: The canonical calculation parameters last used\n"
        "- `result`: Full calculation result JSON (costs per provider/layer)\n"
        "- `cheapest_path`: Optimal provider per layer (l1, l2, l3_hot, l3_cool, l3_archive, l4, l5)\n"
        "- `pricing_catalog_context`: Exact immutable pricing references used\n"
        "- `calculated_at`: Timestamp of last calculation\n\n"
        "**Note:** Creates empty config if none exists."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def get_optimizer_config(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get optimizer config including params, result, and cheapest path."""
    try:
        return _get_service(db).get_config(twin_id, current_user.id)
    except EntityNotFoundError as exc:
        _raise_optimizer_config_error(exc)


@router.put(
    "/params",
    response_model=OptimizerConfigResponse,
    operation_id="updateOptimizerParams",
    summary="Save calculation params before Calculate is clicked",
    description=(
        "**Purpose:** Persist the canonical optimizer parameters without triggering calculation.\n\n"
        "**When to call:** When user changes any parameter in Step 2 (auto-save on blur/change).\n\n"
        "**Request body:**\n"
        "- `params`: Complete validated calculation input (numberOfDevices, hotStorageDurationInMonths, etc.)\n\n"
        "**Behavior:** Saves params but does NOT run calculation. Call `calculateOptimalDistribution` separately."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def update_params(
    twin_id: str,
    update: OptimizerParamsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save calculation params (before Calculate is clicked)."""
    try:
        return _get_service(db).update_params(twin_id, current_user.id, update)
    except EntityNotFoundError as exc:
        _raise_optimizer_config_error(exc)


@router.put(
    "/result",
    response_model=OptimizerConfigResponse,
    operation_id="saveOptimizerResult",
    summary="Save full calculation result with cheapest path",
    description=(
        "**Purpose:** Persist the complete optimization result after `calculateOptimalDistribution` returns.\n\n"
        "**When to call:** Immediately after receiving successful response from `calculateOptimalDistribution`.\n\n"
        "**Request body:**\n"
        "- `params`: The parameters used for this calculation\n"
        "- `result`: Full calculation response (awsCosts, azureCosts, gcpCosts, combinationTables)\n"
        "- `cheapest_path`: Object with l1, l2, l3_hot, l3_cool, l3_archive, l4, l5 provider names\n"
        "- `result.pricingCatalogs`: Exact references returned by the Optimizer\n\n"
        "**Important:** This enables Step 3 (Deployer) by storing the cheapest_path used for deployment."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        422: ERROR_RESPONSES[422],
    }
)
async def save_result(
    twin_id: str,
    update: OptimizerResultUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save a calculation result bound to exact immutable catalog references."""
    try:
        return await _get_service(db).save_result(
            twin_id,
            current_user.id,
            update,
        )
    except EntityNotFoundError as exc:
        _raise_optimizer_config_error(exc)
    except PricingCatalogUnavailable as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": exc.error_code,
                "message": exc.message,
            },
        ) from exc
    except (ExternalServiceError, ExternalServiceUnavailable) as exc:
        raise HTTPException(
            status_code=503 if isinstance(exc, ExternalServiceUnavailable) else 502,
            detail="Optimizer pricing catalog verification failed.",
        ) from exc
    except OptimizerContractError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc


@router.get(
    "/cheapest-path",
    response_model=CheapestPathResponse,
    operation_id="getCheapestPath",
    summary="Get cheapest path only for deployment logic",
    description=(
        "**Purpose:** Retrieve just the cheapest provider selection per layer - used by deployment logic.\n\n"
        "**When to call:** When preparing deployment to determine which cloud providers to deploy to.\n\n"
        "**Prerequisite:** Must have run `calculateOptimalDistribution` and saved via `saveOptimizerResult` first.\n\n"
        "**Response fields:**\n"
        "- `l1`: IoT layer provider (aws, azure, gcp)\n"
        "- `l2`: Orchestration layer provider\n"
        "- `l3_hot`, `l3_cool`, `l3_archive`: Storage layer providers\n"
        "- `l4`: Analytics layer provider\n"
        "- `l5`: Visualization layer provider\n\n"
        "**Error 404:** Returned if calculation has not been run yet."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def get_cheapest_path(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get cheapest path only (for deployment logic)."""
    try:
        return _get_service(db).get_cheapest_path(twin_id, current_user.id)
    except EntityNotFoundError as exc:
        _raise_optimizer_config_error(exc)
