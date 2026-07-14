"""Aggregate deployer validation HTTP boundary."""

from fastapi import APIRouter

from src.api.models.complete_validation import (
    DeployerCompleteValidation,
    DeployerValidationResponse,
    ValidationError,
)
from src.configuration_validation.complete import validate_complete_configuration


router = APIRouter()


@router.post(
    "/validate/deployer-complete",
    operation_id="validateDeployerComplete",
    response_model=DeployerValidationResponse,
    tags=["Validation"],
    summary="Validate complete deployer configuration",
    description=(
        "Validates all deployer wizard fields, cross-field references, provider-specific "
        "function contracts, optional capabilities, and platform-user configuration. "
        "Returns all deterministic field errors without provider fallbacks."
    ),
)
def validate_deployer_complete(
    config: DeployerCompleteValidation,
) -> DeployerValidationResponse:
    return validate_complete_configuration(config)


__all__ = [
    "DeployerCompleteValidation",
    "DeployerValidationResponse",
    "ValidationError",
    "router",
]
