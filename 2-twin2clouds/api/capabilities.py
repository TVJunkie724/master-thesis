"""Read-only Optimizer capability endpoints."""

from fastapi import APIRouter

from backend.provider_capabilities import (
    ServiceProviderCapabilities,
    get_provider_capabilities,
)


router = APIRouter(prefix="/capabilities", tags=["Capabilities"])


@router.get(
    "/providers",
    response_model=ServiceProviderCapabilities,
    operation_id="getOptimizerProviderCapabilities",
    summary="Get provider-layer calculation capabilities",
)
def get_optimizer_provider_capabilities() -> ServiceProviderCapabilities:
    return get_provider_capabilities()
