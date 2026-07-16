"""Read-only Deployer capability endpoints."""

from fastapi import APIRouter

from src.provider_capabilities import (
    ServiceProviderCapabilities,
    get_provider_capabilities,
)


router = APIRouter(prefix="/capabilities", tags=["Capabilities"])


@router.get(
    "/providers",
    response_model=ServiceProviderCapabilities,
    operation_id="getDeployerProviderCapabilities",
    summary="Get provider-layer deployment capabilities",
)
def get_deployer_provider_capabilities() -> ServiceProviderCapabilities:
    return get_provider_capabilities()
