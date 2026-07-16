"""Authenticated platform provider capability read endpoint."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.dependencies import get_current_user
from src.models.user import User
from src.schemas.provider_capability import PlatformProviderCapabilities
from src.security.request_context import current_request_id
from src.services.errors import (
    ExternalServiceError,
    ExternalServiceUnavailable,
    ProviderCapabilityContractInvalid,
)
from src.services.provider_capability_service import ProviderCapabilityService


router = APIRouter(prefix="/platform/provider-capabilities", tags=["platform"])


def get_provider_capability_service() -> ProviderCapabilityService:
    return ProviderCapabilityService()


@router.get(
    "",
    response_model=PlatformProviderCapabilities,
    operation_id="getPlatformProviderCapabilities",
    summary="Get aggregate provider-layer platform capabilities",
    responses={502: {"description": "Invalid upstream capability contract"},
               503: {"description": "Capability source unavailable"}},
)
async def get_platform_provider_capabilities(
    _current_user: User = Depends(get_current_user),
):
    try:
        return await get_provider_capability_service().get_platform_capabilities()
    except ProviderCapabilityContractInvalid:
        return _error_response(
            status_code=502,
            error_code="PROVIDER_CAPABILITY_CONTRACT_INVALID",
            message="A provider capability source returned an invalid contract.",
            fix_suggestion="Retry after the platform operator reconciles service capability contracts.",
        )
    except ExternalServiceUnavailable:
        return _error_response(
            status_code=503,
            error_code="PROVIDER_CAPABILITY_SOURCE_UNAVAILABLE",
            message="Provider capability information is temporarily unavailable.",
            fix_suggestion="Retry after the Optimizer and Deployer services are available.",
        )
    except ExternalServiceError:
        return _error_response(
            status_code=502,
            error_code="PROVIDER_CAPABILITY_SOURCE_ERROR",
            message="A provider capability source could not be validated.",
            fix_suggestion="Retry after the platform operator checks the internal service response.",
        )


def _error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    fix_suggestion: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "fix_suggestion": fix_suggestion,
            "http_status": status_code,
            "request_id": current_request_id(),
        },
    )
