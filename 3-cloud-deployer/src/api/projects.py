"""Bounded project boundary for one Twin deployment operation.

The Deployer keeps a secret-free working definition and short-lived runtime
state for each Twin. It does not expose project browsing, arbitrary imports,
file editing, snapshots, or a second portable-project abstraction.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

import file_manager
from src.api.dependencies import check_template_protection
from src.api.error_handling import internal_server_error, safe_error_detail
from src.api.error_models import ERROR_RESPONSES
from src.api.functions import clear_all_function_metadata
from src.api.upload_limits import read_upload_bounded
from src.core.project_storage import get_project_storage
from src.operation_packages import (
    OperationPackageInUseError,
    get_operation_package_store,
)
from src.project_archive.policy import MAX_COMPRESSED_ARCHIVE_BYTES
from src.runtime_state import get_runtime_state_store

router = APIRouter()


@router.post(
    "/projects/{project_name}/operation-package",
    operation_id="stageDeploymentOperationPackage",
    tags=["Operations"],
    summary="Stage one short-lived Twin deployment package",
    responses={
        200: {"description": "Operation package staged"},
        400: ERROR_RESPONSES[400],
        413: ERROR_RESPONSES[413],
        500: ERROR_RESPONSES[500],
    },
)
async def stage_operation_package(
    project_name: str,
    file: UploadFile = File(..., description="Generated Twin deployment package"),
):
    """Validate one generated package and stage its secrets for one operation."""
    check_template_protection(project_name, "stage an operation package for")
    store = get_operation_package_store()
    staged = None
    try:
        content = await read_upload_bounded(
            file,
            max_bytes=MAX_COMPRESSED_ARCHIVE_BYTES,
        )
        staged = store.stage(project_name, content)
        if get_project_storage().exists(project_name):
            result = file_manager.update_project_from_zip(project_name, content)
            clear_all_function_metadata(project_name)
        else:
            result = file_manager.create_project_from_zip(project_name, content)
        response = {
            "project_name": project_name,
            "operation_token": staged.token,
            "expires_at": staged.expires_at.isoformat(),
            "warnings": sorted(set([*staged.warnings, *result.get("warnings", [])])),
        }
        graph_evidence = getattr(staged, "graph_evidence", None)
        if graph_evidence is not None:
            response["graph_evidence"] = graph_evidence
        return response
    except ValueError as exc:
        if staged is not None:
            store.discard(staged.token)
        raise HTTPException(
            status_code=400,
            detail=safe_error_detail(exc),
        ) from exc
    except HTTPException:
        if staged is not None:
            store.discard(staged.token)
        raise
    except Exception as exc:
        if staged is not None:
            store.discard(staged.token)
        raise internal_server_error("Stage operation package", exc) from exc


@router.delete(
    "/projects/{project_name}",
    operation_id="deleteDeploymentWorkspace",
    tags=["Operations"],
    summary="Delete one Twin deployment workspace",
    responses={
        200: {"description": "Deployment workspace deleted"},
        409: {"description": "Deployment operation is active"},
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    },
)
def delete_project_endpoint(project_name: str):
    """Remove durable definition, runtime state, and unused staged packages."""
    check_template_protection(project_name, "delete")
    try:
        get_operation_package_store().discard_project(project_name)
        file_manager.delete_project(project_name)
        get_runtime_state_store().delete(project_name)
        return {"message": f"Deployment workspace '{project_name}' deleted."}
    except OperationPackageInUseError as exc:
        raise HTTPException(
            status_code=409,
            detail=safe_error_detail(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=safe_error_detail(exc),
        ) from exc
    except Exception as exc:
        raise internal_server_error("Delete deployment workspace", exc) from exc
