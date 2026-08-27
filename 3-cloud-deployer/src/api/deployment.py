"""
Infrastructure API endpoints.

All deployment is now handled by TerraformDeployerStrategy.
This module provides REST API endpoints for infrastructure operations.
"""

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

import src.providers.deployer as core_deployer
from logger import logger
from src.api.dependencies import check_template_protection, validate_provider
from src.api.models.deployment import (
    DeploymentAccessCredentialResult,
    DeploymentOperation,
    DeploymentRequest,
    DeploymentResult,
    DeploymentStreamEvent,
    DestroyResult,
)
from src.api.operation_context import operation_project_path
from src.core.config_loader import ProjectConfigLoader
from src.core.deployment_errors import (
    DeploymentBoundaryError,
    DeploymentErrorCode,
    client_error_payload,
)
from src.core.factory import create_context
from src.core.observability import OperationContext, operation_step
from src.core.project_storage import get_project_storage
from src.deployment_access import (
    GcpViewerRotationError,
    project_deployment_access_evidence,
    rotate_gcp_grafana_viewer,
)
from src.runtime_outputs import load_terraform_outputs
from src.validation.directory_validator import validate_project_directory

router = APIRouter(prefix="/infrastructure")


@router.post(
    "/deployment-access/l5/credentials:rotate",
    response_model=DeploymentAccessCredentialResult,
    tags=["Infrastructure"],
    summary="Rotate the deployed GCP Grafana Viewer credential once",
    responses={
        200: {"description": "One-time Viewer credential"},
        400: {"description": "Invalid or expired operation package"},
        502: {"description": "Bounded GKE rotation failed"},
    },
)
async def rotate_deployment_access_credential(
    operation_token: Annotated[str, Header(alias="X-Operation-Package", min_length=1)],
    project_name: str = Query(..., description="Name of the project context"),
):
    operation_context = OperationContext.create(
        operation="rotate_gcp_grafana_viewer",
        project_name=project_name,
        provider="gcp",
    )
    try:
        with operation_project_path(project_name, operation_token) as project_path:
            _request, context = _prepare_deployment_context(
                project_name,
                "gcp",
                "rotate GCP Grafana Viewer credential in",
                operation_context,
                project_path,
            )
            outputs = load_terraform_outputs(project_name, project_path)
            result = await asyncio.to_thread(
                rotate_gcp_grafana_viewer,
                context,
                outputs,
            )
        return DeploymentAccessCredentialResult.model_validate(result)
    except HTTPException:
        raise
    except GcpViewerRotationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _prepare_deployment_context(
    project_name: str,
    provider: str,
    operation: str,
    operation_context: OperationContext,
    project_path: Path | None = None,
):
    """Validate request boundaries and create the canonical DeploymentContext."""
    check_template_protection(project_name, operation)
    normalized_provider = validate_provider(provider)
    project_dir = (
        project_path or get_project_storage().context(project_name).project_path
    )
    validate_project_directory(
        project_dir,
        require_deployment_manifest=True,
    )
    if project_path is None:
        context = create_context(
            project_name,
            normalized_provider,
            operation_id=operation_context.operation_id,
        )
    else:
        context = ProjectConfigLoader().create_context_from_path(
            project_name,
            project_dir,
            normalized_provider,
            operation_id=operation_context.operation_id,
        )
    if operation != "destroy" and context.resolved_deployment_graph is None:
        raise ValueError(
            "DEPLOYMENT_MANIFEST_VERSION_UNSUPPORTED: "
            "new deployment operations require DeploymentManifest v4"
        )
    return DeploymentRequest(
        project_name=project_name, provider=normalized_provider
    ), context


def _raise_structured_http_error(
    exc: HTTPException,
    operation_context: OperationContext,
) -> None:
    """Convert request-boundary HTTP errors to the deployment error contract."""
    boundary_error = DeploymentBoundaryError(
        str(exc.detail),
        code=DeploymentErrorCode.validation_error,
        status_code=exc.status_code,
    )
    detail = client_error_payload(
        boundary_error,
        operation_context,
        fallback_message=str(exc.detail),
    )
    raise HTTPException(status_code=exc.status_code, detail=detail)


# --------- Core Deploy/Destroy ----------
@router.post(
    "/deploy",
    tags=["Infrastructure"],
    summary="Deploy full digital twin environment",
    responses={
        200: {"description": "Deployment successful"},
        400: {"description": "Invalid project or provider"},
        500: {"description": "Deployment failed"},
    },
)
def deploy_all(
    operation_token: Annotated[str, Header(alias="X-Operation-Package", min_length=1)],
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context"),
):
    """
    Deploys the full digital twin environment using Terraform.

    **Deployment process:**
    1. Validates project structure and configuration
    2. Runs `terraform init` (if needed) and `terraform apply`
    3. Deploys all configured layers based on config_providers.json

    **Layers deployed:**
    - **L1** (IoT Ingestion): IoT Hub/Core, Dispatcher Lambda/Function
    - **L2** (Processing): Persister, Event Checker, State Machine
    - **L3** (Storage): Hot storage (DynamoDB/CosmosDB), Cold storage (S3/Blob)
    - **L4** (Digital Twin): TwinMaker/ADT entities
    - **L5** (Visualization): Grafana dashboards

    **Note:** Long-running operation (2-10 minutes depending on resources).
    """
    operation_context = OperationContext.create(
        operation=DeploymentOperation.deploy.value,
        project_name=project_name,
        provider=provider,
    )
    try:
        with operation_project_path(project_name, operation_token) as project_path:
            with operation_step(logger, operation_context, "request_prepare"):
                request, context = _prepare_deployment_context(
                    project_name,
                    provider,
                    "deploy",
                    operation_context,
                    project_path,
                )
            operation_context = operation_context.with_provider(request.provider)

            outputs = core_deployer.deploy_all(
                context,
                request.provider,
                operation_context=operation_context,
            )
            access_evidence = project_deployment_access_evidence(context, outputs)

        return DeploymentResult(
            project_name=request.project_name,
            provider=request.provider,
            operation_id=operation_context.operation_id,
            terraform_outputs=outputs,
            deployment_access_evidence=access_evidence,
        ).model_dump(mode="json", exclude_none=True)
    except HTTPException as e:
        _raise_structured_http_error(e, operation_context)
    except ValueError as e:
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)
    except Exception as e:
        logger.error(
            "Deployment operation failed",
            extra=operation_context.log_extra(
                phase="route_deploy",
                error_type=type(e).__name__,
            ),
        )
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)


@router.post(
    "/destroy",
    tags=["Infrastructure"],
    summary="Destroy full digital twin environment",
    responses={
        200: {"description": "Destruction successful"},
        500: {"description": "Destruction failed - may need force cleanup"},
    },
)
def destroy_all(
    operation_token: Annotated[str, Header(alias="X-Operation-Package", min_length=1)],
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context"),
):
    """
    Destroys the full digital twin environment using Terraform.

    **Destruction process:**
    1. Runs `terraform destroy` to remove all infrastructure
    2. Cleans up SDK-managed resources (IoT devices, Digital Twin entities)

    **If destruction fails for AWS TwinMaker:**
    Use `DELETE /projects/{name}/cleanup/aws-twinmaker` to manually clean entities first.

    **Note:** This operation cannot be undone. All data will be lost.
    """
    operation_context = OperationContext.create(
        operation=DeploymentOperation.destroy.value,
        project_name=project_name,
        provider=provider,
    )
    try:
        with operation_project_path(project_name, operation_token) as project_path:
            with operation_step(logger, operation_context, "request_prepare"):
                request, context = _prepare_deployment_context(
                    project_name,
                    provider,
                    "destroy",
                    operation_context,
                    project_path,
                )
            operation_context = operation_context.with_provider(request.provider)

            core_deployer.destroy_all(
                context,
                request.provider,
                operation_context=operation_context,
            )

        return DestroyResult(
            project_name=request.project_name,
            provider=request.provider,
            operation_id=operation_context.operation_id,
        ).model_dump(mode="json")
    except HTTPException as e:
        _raise_structured_http_error(e, operation_context)
    except ValueError as e:
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)
    except Exception as e:
        logger.error(
            "Destruction operation failed",
            extra=operation_context.log_extra(
                phase="route_destroy",
                error_type=type(e).__name__,
            ),
        )
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)


# --------- SSE Streaming Endpoints ----------


@router.post(
    "/deploy/stream",
    tags=["Infrastructure"],
    summary="Deploy with SSE streaming logs",
    responses={
        200: {"description": "SSE stream of deployment logs"},
        400: {"description": "Invalid project or provider"},
        500: {"description": "Deployment failed"},
    },
)
async def deploy_stream(
    operation_token: Annotated[str, Header(alias="X-Operation-Package", min_length=1)],
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context"),
):
    """
    Deploy with Server-Sent Events streaming.

    Returns an SSE stream with real-time deployment logs.
    """
    operation_context = OperationContext.create(
        operation=DeploymentOperation.deploy.value,
        project_name=project_name,
        provider=provider,
    )
    package_scope = operation_project_path(project_name, operation_token)
    package_entered = False
    try:
        stream_outputs: dict = {}
        project_path = package_scope.__enter__()
        package_entered = True
        with operation_step(logger, operation_context, "request_prepare"):
            request, context = _prepare_deployment_context(
                project_name,
                provider,
                "deploy",
                operation_context,
                project_path,
            )
        stream_context = operation_context.with_provider(request.provider)

        async def generate():
            scope_closed = False
            try:
                async for line in core_deployer.deploy_all_stream(
                    context,
                    output_sink=stream_outputs,
                    operation_context=stream_context,
                ):
                    yield DeploymentStreamEvent.log(
                        DeploymentOperation.deploy,
                        line,
                        operation_id=stream_context.operation_id,
                    ).to_sse()
                try:
                    package_scope.__exit__(None, None, None)
                finally:
                    scope_closed = True
                outputs = stream_outputs.get("outputs", {})
                access_evidence = project_deployment_access_evidence(
                    context,
                    outputs,
                )
                yield DeploymentStreamEvent.complete(
                    DeploymentOperation.deploy,
                    outputs=outputs,
                    deployment_access_evidence=access_evidence,
                    operation_id=stream_context.operation_id,
                ).to_sse()
            except BaseException as e:
                if not scope_closed:
                    try:
                        package_scope.__exit__(type(e), e, e.__traceback__)
                    finally:
                        scope_closed = True
                if not isinstance(e, Exception):
                    raise
                detail = client_error_payload(e, operation_context)
                yield DeploymentStreamEvent.failure(
                    DeploymentOperation.deploy,
                    detail["message"],
                    error_code=detail["error_code"],
                    operation_id=operation_context.operation_id,
                ).to_sse()

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException as e:
        if package_entered:
            package_scope.__exit__(type(e), e, e.__traceback__)
        _raise_structured_http_error(e, operation_context)
    except ValueError as e:
        if package_entered:
            package_scope.__exit__(type(e), e, e.__traceback__)
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)
    except Exception as e:
        if package_entered:
            package_scope.__exit__(type(e), e, e.__traceback__)
        logger.error(
            "Deployment stream setup failed",
            extra=operation_context.log_extra(
                phase="route_deploy_stream",
                error_type=type(e).__name__,
            ),
        )
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)


@router.post(
    "/destroy/stream",
    tags=["Infrastructure"],
    summary="Destroy with SSE streaming logs",
    responses={
        200: {"description": "SSE stream of destruction logs"},
        500: {"description": "Destruction failed"},
    },
)
async def destroy_stream(
    operation_token: Annotated[str, Header(alias="X-Operation-Package", min_length=1)],
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context"),
):
    """
    Destroy with Server-Sent Events streaming.

    Returns an SSE stream with real-time destruction logs.
    """
    operation_context = OperationContext.create(
        operation=DeploymentOperation.destroy.value,
        project_name=project_name,
        provider=provider,
    )
    package_scope = operation_project_path(project_name, operation_token)
    package_entered = False
    try:
        project_path = package_scope.__enter__()
        package_entered = True
        with operation_step(logger, operation_context, "request_prepare"):
            request, context = _prepare_deployment_context(
                project_name,
                provider,
                "destroy",
                operation_context,
                project_path,
            )
        stream_context = operation_context.with_provider(request.provider)

        async def generate():
            scope_closed = False
            try:
                async for line in core_deployer.destroy_all_stream(
                    context,
                    operation_context=stream_context,
                ):
                    yield DeploymentStreamEvent.log(
                        DeploymentOperation.destroy,
                        line,
                        operation_id=stream_context.operation_id,
                    ).to_sse()
                try:
                    package_scope.__exit__(None, None, None)
                finally:
                    scope_closed = True
                yield DeploymentStreamEvent.complete(
                    DeploymentOperation.destroy,
                    operation_id=stream_context.operation_id,
                ).to_sse()
            except BaseException as e:
                if not scope_closed:
                    try:
                        package_scope.__exit__(type(e), e, e.__traceback__)
                    finally:
                        scope_closed = True
                if not isinstance(e, Exception):
                    raise
                detail = client_error_payload(e, operation_context)
                yield DeploymentStreamEvent.failure(
                    DeploymentOperation.destroy,
                    detail["message"],
                    error_code=detail["error_code"],
                    operation_id=operation_context.operation_id,
                ).to_sse()

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException as e:
        if package_entered:
            package_scope.__exit__(type(e), e, e.__traceback__)
        _raise_structured_http_error(e, operation_context)
    except ValueError as e:
        if package_entered:
            package_scope.__exit__(type(e), e, e.__traceback__)
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)
    except Exception as e:
        if package_entered:
            package_scope.__exit__(type(e), e, e.__traceback__)
        logger.error(
            "Destruction stream setup failed",
            extra=operation_context.log_extra(
                phase="route_destroy_stream",
                error_type=type(e).__name__,
            ),
        )
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)
