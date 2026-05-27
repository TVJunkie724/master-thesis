"""
Infrastructure API endpoints.

All deployment is now handled by TerraformDeployerStrategy.
This module provides REST API endpoints for infrastructure operations.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from api.dependencies import validate_provider, check_template_protection
from src.api.models.deployment import (
    DeploymentOperation,
    DeploymentRequest,
    DeploymentResult,
    DeploymentStreamEvent,
    DestroyResult,
)
from src.core.deployment_errors import (
    DeploymentBoundaryError,
    DeploymentErrorCode,
    client_error_payload,
)
from src.core.observability import OperationContext, operation_step
from src.core.project_storage import get_project_storage
from src.validation.directory_validator import validate_project_directory
from logger import logger

import providers.deployer as core_deployer
from src.core.factory import create_context


router = APIRouter(prefix="/infrastructure")


def _prepare_deployment_context(
    project_name: str,
    provider: str,
    operation: str,
    operation_context: OperationContext,
):
    """Validate request boundaries and create the canonical DeploymentContext."""
    check_template_protection(project_name, operation)
    normalized_provider = validate_provider(provider)
    project_dir = get_project_storage().context(project_name).project_path
    validate_project_directory(project_dir)
    context = create_context(
        project_name,
        normalized_provider,
        operation_id=operation_context.operation_id,
    )
    return DeploymentRequest(project_name=project_name, provider=normalized_provider), context


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


# --------- Cooldown Check ----------
@router.get(
    "/cooldown-check",
    tags=["Infrastructure"],
    summary="Check GCP Firestore deployment cooldown",
    responses={
        200: {"description": "Cooldown status returned"}
    }
)
def check_cooldown(
    destroyed_at: Optional[str] = Query(None, description="ISO timestamp of last destroy"),
    uses_gcp_firestore: bool = Query(True, description="Whether deployment uses GCP Firestore")
):
    """
    Check if redeployment is allowed (GCP Firestore 5-min cooldown).
    
    **Zero cloud costs:** Pure calculation with hardcoded 5-min limit. No cloud API calls.
    
    Args:
        destroyed_at: ISO timestamp from Management API
        uses_gcp_firestore: Whether deployment uses GCP as L3-Hot provider
    
    Returns:
        ready: True if deployment can proceed
        remaining_seconds: Seconds until ready (0 if ready)
    """
    FIRESTORE_COOLDOWN = 300  # 5 minutes
    
    # No cooldown needed if not using GCP Firestore
    if not uses_gcp_firestore:
        return {"ready": True, "remaining_seconds": 0}
    
    # No prior destroy = first deployment
    if not destroyed_at:
        return {"ready": True, "remaining_seconds": 0}
    
    try:
        # Parse ISO timestamp (handle Z suffix)
        destroy_time = datetime.fromisoformat(destroyed_at.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - destroy_time).total_seconds()
        
        if elapsed >= FIRESTORE_COOLDOWN:
            return {"ready": True, "remaining_seconds": 0}
        else:
            remaining = int(FIRESTORE_COOLDOWN - elapsed)
            return {
                "ready": False, 
                "remaining_seconds": remaining,
                "reason": f"GCP Firestore cooldown: {remaining}s remaining"
            }
    except (ValueError, TypeError):
        # Malformed timestamp - safe fallback
        return {"ready": True, "remaining_seconds": 0}


# --------- Core Deploy/Destroy ----------
@router.post(
    "/deploy", 
    tags=["Infrastructure"],
    summary="Deploy full digital twin environment",
    responses={
        200: {"description": "Deployment successful"},
        400: {"description": "Invalid project or provider"},
        500: {"description": "Deployment failed"}
    }
)
def deploy_all(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
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
        with operation_step(logger, operation_context, "request_prepare"):
            request, context = _prepare_deployment_context(
                project_name,
                provider,
                "deploy",
                operation_context,
            )
        operation_context = operation_context.with_provider(request.provider)
        
        # TerraformDeployerStrategy handles validation + deployment
        outputs = core_deployer.deploy_all(
            context,
            request.provider,
            operation_context=operation_context,
        )
        
        return DeploymentResult(
            project_name=request.project_name,
            provider=request.provider,
            operation_id=operation_context.operation_id,
            terraform_outputs=outputs,
        ).model_dump(mode="json")
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
        500: {"description": "Destruction failed - may need force cleanup"}
    }
)
def destroy_all(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
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
        with operation_step(logger, operation_context, "request_prepare"):
            request, context = _prepare_deployment_context(
                project_name,
                provider,
                "destroy",
                operation_context,
            )
        operation_context = operation_context.with_provider(request.provider)
        
        # TerraformDeployerStrategy handles all destruction
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
from fastapi.responses import StreamingResponse


@router.post(
    "/deploy/stream", 
    tags=["Infrastructure"],
    summary="Deploy with SSE streaming logs",
    responses={
        200: {"description": "SSE stream of deployment logs"},
        400: {"description": "Invalid project or provider"},
        500: {"description": "Deployment failed"}
    }
)
async def deploy_stream(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
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
    try:
        with operation_step(logger, operation_context, "request_prepare"):
            request, context = _prepare_deployment_context(
                project_name,
                provider,
                "deploy",
                operation_context,
            )
        operation_context = operation_context.with_provider(request.provider)
        stream_outputs: dict = {}
        
        async def generate():
            try:
                async for line in core_deployer.deploy_all_stream(
                    context,
                    output_sink=stream_outputs,
                    operation_context=operation_context,
                ):
                    yield DeploymentStreamEvent.log(
                        DeploymentOperation.deploy,
                        line,
                        operation_id=operation_context.operation_id,
                    ).to_sse()
                # Final success event
                outputs = stream_outputs.get("outputs", {})
                yield DeploymentStreamEvent.complete(
                    DeploymentOperation.deploy,
                    outputs=outputs,
                    operation_id=operation_context.operation_id,
                ).to_sse()
            except Exception as e:
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
                "X-Accel-Buffering": "no"
            }
        )
    except HTTPException as e:
        _raise_structured_http_error(e, operation_context)
    except ValueError as e:
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)
    except Exception as e:
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
        500: {"description": "Destruction failed"}
    }
)
async def destroy_stream(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
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
    try:
        with operation_step(logger, operation_context, "request_prepare"):
            request, context = _prepare_deployment_context(
                project_name,
                provider,
                "destroy",
                operation_context,
            )
        operation_context = operation_context.with_provider(request.provider)
        
        async def generate():
            try:
                async for line in core_deployer.destroy_all_stream(
                    context,
                    operation_context=operation_context,
                ):
                    yield DeploymentStreamEvent.log(
                        DeploymentOperation.destroy,
                        line,
                        operation_id=operation_context.operation_id,
                    ).to_sse()
                yield DeploymentStreamEvent.complete(
                    DeploymentOperation.destroy,
                    operation_id=operation_context.operation_id,
                ).to_sse()
            except Exception as e:
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
                "X-Accel-Buffering": "no"
            }
        )
    except HTTPException as e:
        _raise_structured_http_error(e, operation_context)
    except ValueError as e:
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)
    except Exception as e:
        logger.error(
            "Destruction stream setup failed",
            extra=operation_context.log_extra(
                phase="route_destroy_stream",
                error_type=type(e).__name__,
            ),
        )
        detail = client_error_payload(e, operation_context)
        raise HTTPException(status_code=detail["http_status"], detail=detail)
