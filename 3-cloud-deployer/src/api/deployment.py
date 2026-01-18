"""
Infrastructure API endpoints.

All deployment is now handled by TerraformDeployerStrategy.
This module provides REST API endpoints for infrastructure operations.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Path
import src.validator as validator
from api.dependencies import validate_project_context, validate_provider, check_template_protection
from logger import print_stack_trace, logger

import providers.deployer as core_deployer
from src.core.factory import create_context


router = APIRouter(prefix="/infrastructure")


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
    check_template_protection(project_name, "deploy")
    validate_project_context(project_name)
    try:
        provider = validate_provider(provider)
        
        context = create_context(project_name, provider)
        
        # TerraformDeployerStrategy handles validation + deployment
        core_deployer.deploy_all(context, provider)
        
        return {"message": "Core and IoT services deployed successfully"}
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
    check_template_protection(project_name, "destroy")
    validate_project_context(project_name)
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
