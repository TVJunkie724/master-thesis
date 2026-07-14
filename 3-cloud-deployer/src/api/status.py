"""HTTP transport for deployment status and infrastructure verification."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.error_models import ERROR_RESPONSES
from logger import logger
from src.core.observability import redact_sensitive
from src.core.paths import resolve_project_context_path
from src.core.config_loader import normalize_provider_name
from src.status.metadata import check_code_hashes
from src.status.sdk import check_sdk_managed
from src.status.terraform import check_terraform_drift, check_terraform_state
from src.status.verification import verify_infrastructure

router = APIRouter()


def _validate_request(project_name: str, provider: str) -> str:
    if not resolve_project_context_path(project_name).is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found",
        )
    normalized = normalize_provider_name(provider)
    if normalized not in {"aws", "azure", "gcp"}:
        raise HTTPException(
            status_code=400,
            detail="Provider must be aws, azure, gcp, or google",
        )
    return normalized


@router.get(
    "/infrastructure/status",
    operation_id="getDeploymentStatus",
    tags=["Infrastructure"],
    summary="Check deployment status across managed resource boundaries",
    responses={
        200: {"description": "Status check successful"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    },
)
def check_endpoint(
    provider: str = Query(..., description="Cloud provider: aws, azure, or gcp"),
    project_name: str = Query(..., min_length=1, max_length=128),
    detailed: bool = Query(False, description="Include live drift detection"),
):
    normalized_provider = _validate_request(project_name, provider)
    try:
        result = {
            "project": project_name,
            "provider": normalized_provider,
            "infrastructure": check_terraform_state(project_name),
            "user_functions": check_code_hashes(project_name),
            "sdk_managed": check_sdk_managed(project_name, normalized_provider),
        }
        if detailed:
            result["drift_detection"] = check_terraform_drift(project_name)
        return result
    except Exception as exc:
        logger.error("Status operation failed: %s", redact_sensitive(exc))
        raise HTTPException(
            status_code=500,
            detail="Status operation failed. Check logs.",
        ) from exc


@router.post(
    "/infrastructure/verify",
    operation_id="verifyInfrastructure",
    tags=["Infrastructure"],
    summary="Verify configured infrastructure across L0-L5",
    responses={
        200: {"description": "Verification complete"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    },
)
def verify_endpoint(
    provider: str = Query(..., description="Primary cloud provider"),
    project_name: str = Query(..., min_length=1, max_length=128),
):
    normalized_provider = _validate_request(project_name, provider)
    try:
        return verify_infrastructure(project_name, normalized_provider)
    except Exception as exc:
        logger.error("Infrastructure verification failed: %s", redact_sensitive(exc))
        raise HTTPException(
            status_code=500,
            detail="Verification failed. Check logs.",
        ) from exc
