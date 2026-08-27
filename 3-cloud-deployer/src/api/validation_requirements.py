"""Pure deployment-graph requirement inspection endpoint."""

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from src.api.error_handling import internal_server_error, safe_error_detail
from src.api.error_models import ERROR_RESPONSES
from src.api.upload_limits import read_upload_bounded
from src.operation_packages import inspect_deployment_requirements
from src.account_preparation import execute_account_preparation
from src.project_archive.policy import MAX_COMPRESSED_ARCHIVE_BYTES


router = APIRouter()


@router.post(
    "/validate/deployment-requirements",
    operation_id="inspectDeploymentRequirements",
    tags=["Validation"],
    summary="Resolve exact deployment prerequisites without cloud mutation",
    responses={
        200: {"description": "Graph requirements resolved"},
        400: ERROR_RESPONSES[400],
        413: ERROR_RESPONSES[413],
        500: ERROR_RESPONSES[500],
    },
)
async def inspect_requirements(
    project_name: str = Query(..., min_length=1, max_length=128),
    file: UploadFile = File(..., description="Generated deployment package"),
):
    """Return only digest-bound graph evidence and secret-free requirements."""

    try:
        content = await read_upload_bounded(
            file,
            max_bytes=MAX_COMPRESSED_ARCHIVE_BYTES,
        )
        inspection = inspect_deployment_requirements(project_name, content)
        return {
            "project_name": inspection.project_name,
            "warnings": list(inspection.warnings),
            "graph_evidence": inspection.graph_evidence,
            "requirements": list(inspection.requirements),
            "preparation_plan": inspection.preparation_plan,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=safe_error_detail(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_server_error("Inspect deployment requirements", exc) from exc


@router.post(
    "/infrastructure/account-preparation",
    operation_id="prepareDeploymentAccountPrerequisites",
    tags=["Infrastructure"],
    summary="Apply the confirmed graph-derived account preparation plan",
    responses={
        200: {"description": "Preparation completed or returned partial evidence"},
        400: ERROR_RESPONSES[400],
        413: ERROR_RESPONSES[413],
        500: ERROR_RESPONSES[500],
    },
)
async def prepare_account(
    project_name: str = Query(..., min_length=1, max_length=128),
    expected_plan_digest: str = Form(...),
    confirmed: bool = Form(...),
    file: UploadFile = File(..., description="Generated deployment package"),
):
    """Apply only Azure RP and GCP API actions bound to the reviewed digest."""

    try:
        content = await read_upload_bounded(
            file,
            max_bytes=MAX_COMPRESSED_ARCHIVE_BYTES,
        )
        result = execute_account_preparation(
            project_name,
            content,
            expected_plan_digest=expected_plan_digest,
            confirmed=confirmed,
        )
        return {
            "project_name": result.project_name,
            "plan_digest": result.plan_digest,
            "requirements_digest": result.requirements_digest,
            "status": result.status,
            "completed_actions": list(result.completed_actions),
            "failed_actions": list(result.failed_actions),
            "remaining_actions": list(result.remaining_actions),
            "retry_safe": result.retry_safe,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=safe_error_detail(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_server_error("Prepare deployment account", exc) from exc
