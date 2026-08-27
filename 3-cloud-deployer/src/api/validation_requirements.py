"""Pure deployment-graph requirement inspection endpoint."""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from src.api.error_handling import internal_server_error, safe_error_detail
from src.api.error_models import ERROR_RESPONSES
from src.api.upload_limits import read_upload_bounded
from src.operation_packages import inspect_deployment_requirements
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
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=safe_error_detail(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_server_error("Inspect deployment requirements", exc) from exc
