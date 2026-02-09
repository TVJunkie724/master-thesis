"""
Infrastructure Deployment API endpoints.

This module provides REST API endpoints for deploying and destroying Digital Twin
infrastructure using Terraform. All operations are project-scoped and provider-aware.

**Key operations:**
- Deploy/Destroy: Full infrastructure lifecycle
- SSE Streaming: Real-time deployment logs
- Cooldown Check: GCP Firestore 5-minute redeployment limit

**IMPORTANT:** Deploy operations are long-running (2-10 minutes). Use the SSE
streaming endpoints for real-time progress updates.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Path
import src.validator as validator
from api.dependencies import validate_project_context, validate_provider, check_template_protection
from logger import print_stack_trace, logger
from api.error_models import ERROR_RESPONSES

import providers.deployer as core_deployer
from src.core.factory import create_context


router = APIRouter(prefix="/infrastructure")


# --------- Cooldown Check ----------
@router.get(
    "/cooldown-check",
    operation_id="checkGcpFirestoreCooldown",
    tags=["Infrastructure"],
    summary="Check if GCP Firestore cooldown period has elapsed",
    description=(
        "**Purpose:** Determines if a re-deployment is allowed after a destroy.\n\n"
        "**Why needed:** GCP Firestore has a 5-minute cooldown after deletion.\n"
        "Attempting to redeploy during this window will fail.\n\n"
        "**Zero cloud costs:** Pure local timestamp calculation."
    ),
    responses={
        200: {
            "description": "Cooldown status",
            "content": {"application/json": {"example": {
                "ready": True,
                "remaining_seconds": 0
            }}}
        }
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
    operation_id="deployDigitalTwinInfrastructure",
    tags=["Infrastructure"],
    summary="Deploy complete Digital Twin infrastructure via Terraform",
    description=(
        "**Purpose:** Deploys all configured layers of the Digital Twin environment.\n\n"
        "**IMPORTANT:** This is a long-running operation (2-10 minutes).\n"
        "For real-time progress, use `/infrastructure/deploy/stream` instead.\n\n"
        "**Deployment process:**\n"
        "1. Validates project structure and configuration\n"
        "2. Runs `terraform init` and `terraform apply`\n"
        "3. Deploys all configured layers\n\n"
        "**Layers deployed (based on config_providers.json):**\n"
        "- L1 (Ingestion): IoT Hub/Core, Dispatcher\n"
        "- L2 (Processing): Persister, Event Checker\n"
        "- L3 (Storage): Hot/Cold storage\n"
        "- L4 (Digital Twin): TwinMaker/ADT\n"
        "- L5 (Visualization): Grafana"
    ),
    responses={
        200: {"description": "Deployment successful with Terraform outputs"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
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
    check_template_protection(project_name, "deploy")
    # NOTE: validate_project_context removed - was blocking production use.
    # Project existence is validated by create_context() which loads files from disk.
    try:
        provider = validate_provider(provider)
        
        context = create_context(project_name, provider)
        
        # TerraformDeployerStrategy handles validation + deployment
        outputs = core_deployer.deploy_all(context, provider)
        
        return {
            "message": "Core and IoT services deployed successfully",
            "terraform_outputs": outputs
        }
    except HTTPException:
        raise
    except ValueError as e:
        # Validation errors get 400, not 500
        raise HTTPException(status_code=400, detail=f"Validation failed: {e}")
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Deployment operation failed. Check logs.")


@router.post(
    "/destroy", 
    operation_id="destroyDigitalTwinInfrastructure",
    tags=["Infrastructure"],
    summary="Destroy all deployed infrastructure via Terraform",
    description=(
        "**Purpose:** Destroys all resources created by deploy.\n\n"
        "**WARNING:** This operation cannot be undone. All data will be lost.\n\n"
        "**Destruction process:**\n"
        "1. Runs `terraform destroy`\n"
        "2. Cleans up SDK-managed resources\n\n"
        "**If AWS TwinMaker fails:** Use `DELETE /projects/{name}/cleanup/aws-twinmaker`"
    ),
    responses={
        200: {"description": "Destruction successful"},
        500: ERROR_RESPONSES[500],
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
    check_template_protection(project_name, "destroy")
    # NOTE: validate_project_context removed - see deploy() comment
    try:
        provider = provider.lower()
        context = create_context(project_name, provider)
        
        # TerraformDeployerStrategy handles all destruction
        core_deployer.destroy_all(context, provider)
        
        return {"message": "Core and IoT services destroyed successfully"}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Deployment operation failed. Check logs.")


# --------- SSE Streaming Endpoints ----------
from fastapi.responses import StreamingResponse


@router.post(
    "/deploy/stream", 
    operation_id="deployWithSseStreaming",
    tags=["Infrastructure"],
    summary="Deploy with real-time SSE streaming logs",
    description=(
        "**Purpose:** Deploy with Server-Sent Events for real-time log streaming.\n\n"
        "**Recommended for UI:** Use this endpoint instead of `/deploy` for progress updates.\n\n"
        "**SSE events:**\n"
        "- `data:` lines contain log output\n"
        "- `event: complete` signals success with outputs\n"
        "- `event: error` signals failure with error details"
    ),
    responses={
        200: {"description": "SSE stream of deployment logs"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
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
    from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
    from pathlib import Path
    
    check_template_protection(project_name, "deploy")
    # NOTE: validate_project_context removed - see deploy() comment
    
    try:
        provider = validate_provider(provider)
        context = create_context(project_name, provider)
        
        terraform_dir = Path("/app/src/terraform")
        project_path = Path(f"/app/upload/{project_name}")
        strategy = TerraformDeployerStrategy(str(terraform_dir), str(project_path))
        
        async def generate():
            import json
            errors = []
            in_error_block = False
            current_error = []
            resource_count = 0
            
            try:
                async for line in strategy.deploy_all_async(context):
                    yield f"data: {line}\n\n"
                    
                    # Track Terraform errors
                    stripped = line.strip()
                    if stripped.startswith("Error:") or stripped.startswith("│ Error:"):
                        in_error_block = True
                        current_error = [stripped]
                    elif in_error_block:
                        if stripped == "" or stripped == "│":
                            # End of error block
                            errors.append("\n".join(current_error))
                            current_error = []
                            in_error_block = False
                        else:
                            current_error.append(stripped)
                    
                    # Count resources created
                    if "Creation complete" in line or "Apply complete!" in line:
                        resource_count += 1
                
                # Flush any remaining error block
                if current_error:
                    errors.append("\n".join(current_error))
                
                # Emit deployment summary
                yield f"data: \n\n"
                yield f"data: {'=' * 60}\n\n"
                if errors:
                    yield f"data:   DEPLOYMENT SUMMARY — {len(errors)} ERROR(S)\n\n"
                    yield f"data: {'=' * 60}\n\n"
                    for i, err in enumerate(errors, 1):
                        yield f"data: [{i}] {err}\n\n"
                else:
                    yield f"data:   DEPLOYMENT SUMMARY — SUCCESS\n\n"
                    yield f"data: {'=' * 60}\n\n"
                    if resource_count > 0:
                        yield f"data: Resources provisioned: {resource_count}\n\n"
                
                # Final SSE event
                outputs = strategy.get_outputs()
                yield f"event: complete\ndata: {json.dumps({'success': len(errors) == 0, 'outputs': outputs, 'errors': errors})}\n\n"
            except Exception as e:
                # Flush any remaining error block
                if current_error:
                    errors.append("\n".join(current_error))
                
                yield f"data: \n\n"
                yield f"data: {'=' * 60}\n\n"
                yield f"data:   DEPLOYMENT FAILED\n\n"
                yield f"data: {'=' * 60}\n\n"
                yield f"data: {str(e)}\n\n"
                if errors:
                    yield f"data: \n\n"
                    yield f"data: Terraform errors encountered:\n\n"
                    for i, err in enumerate(errors, 1):
                        yield f"data: [{i}] {err}\n\n"
                yield f"event: error\ndata: {json.dumps({'success': False, 'error': str(e), 'errors': errors})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {e}")
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Deployment operation failed. Check logs.")


@router.post(
    "/destroy/stream", 
    operation_id="destroyWithSseStreaming",
    tags=["Infrastructure"],
    summary="Destroy with real-time SSE streaming logs",
    description=(
        "**Purpose:** Destroy with SSE streaming for real-time progress.\n\n"
        "**SSE events:**\n"
        "- `data:` lines contain log output\n"
        "- `event: complete` signals success\n"
        "- `event: error` signals failure"
    ),
    responses={
        200: {"description": "SSE stream of destruction logs"},
        500: ERROR_RESPONSES[500],
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
    from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
    from pathlib import Path
    
    check_template_protection(project_name, "destroy")
    # NOTE: validate_project_context removed - see deploy() comment
    
    try:
        provider = provider.lower()
        context = create_context(project_name, provider)
        
        terraform_dir = Path("/app/src/terraform")
        project_path = Path(f"/app/upload/{project_name}")
        strategy = TerraformDeployerStrategy(str(terraform_dir), str(project_path))
        
        async def generate():
            import json
            errors = []
            in_error_block = False
            current_error = []
            resource_count = 0
            
            try:
                async for line in strategy.destroy_all_async(context):
                    yield f"data: {line}\n\n"
                    
                    # Track Terraform errors
                    stripped = line.strip()
                    if stripped.startswith("Error:") or stripped.startswith("│ Error:"):
                        in_error_block = True
                        current_error = [stripped]
                    elif in_error_block:
                        if stripped == "" or stripped == "│":
                            errors.append("\n".join(current_error))
                            current_error = []
                            in_error_block = False
                        else:
                            current_error.append(stripped)
                    
                    # Count resources destroyed
                    if "Destruction complete" in line or "Destroy complete!" in line:
                        resource_count += 1
                
                # Flush any remaining error block
                if current_error:
                    errors.append("\n".join(current_error))
                
                # Emit destruction summary
                yield f"data: \n\n"
                yield f"data: {'=' * 60}\n\n"
                if errors:
                    yield f"data:   DESTROY SUMMARY — {len(errors)} ERROR(S)\n\n"
                    yield f"data: {'=' * 60}\n\n"
                    for i, err in enumerate(errors, 1):
                        yield f"data: [{i}] {err}\n\n"
                else:
                    yield f"data:   DESTROY SUMMARY — SUCCESS\n\n"
                    yield f"data: {'=' * 60}\n\n"
                    if resource_count > 0:
                        yield f"data: Resources destroyed: {resource_count}\n\n"
                
                yield f"event: complete\ndata: {json.dumps({'success': len(errors) == 0, 'errors': errors})}\n\n"
            except Exception as e:
                if current_error:
                    errors.append("\n".join(current_error))
                
                yield f"data: \n\n"
                yield f"data: {'=' * 60}\n\n"
                yield f"data:   DESTROY FAILED\n\n"
                yield f"data: {'=' * 60}\n\n"
                yield f"data: {str(e)}\n\n"
                if errors:
                    yield f"data: \n\n"
                    yield f"data: Terraform errors encountered:\n\n"
                    for i, err in enumerate(errors, 1):
                        yield f"data: [{i}] {err}\n\n"
                yield f"event: error\ndata: {json.dumps({'success': False, 'error': str(e), 'errors': errors})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Destruction operation failed. Check logs.")

