"""Stable validation API facade composed from focused endpoint domains."""

from fastapi import APIRouter
from pydantic import BaseModel

from api.dependencies import ProviderEnum
from api.validation_archive import router as archive_validation_router
from api.validation_artifacts import router as artifact_validation_router
from api.validation_complete import (
    DeployerCompleteValidation,
    DeployerValidationResponse,
    ValidationError,
    router as complete_validation_router,
)
from api.validation_extract import router as extraction_router
from api.validation_payloads import router as payload_validation_router
from api.validation_twin import router as twin_validation_router


class FunctionCodeValidationRequest(BaseModel):
    """Compatibility schema retained for API consumers importing this type."""

    provider: ProviderEnum
    code: str


router = APIRouter()
router.include_router(archive_validation_router)
router.include_router(artifact_validation_router)
router.include_router(payload_validation_router)
router.include_router(twin_validation_router)
router.include_router(extraction_router)
router.include_router(complete_validation_router)

__all__ = [
    "DeployerCompleteValidation",
    "DeployerValidationResponse",
    "FunctionCodeValidationRequest",
    "ValidationError",
    "router",
]

