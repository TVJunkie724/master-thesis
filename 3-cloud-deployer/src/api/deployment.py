"""
Infrastructure API endpoints.

All deployment is now handled by TerraformDeployerStrategy.
This module provides REST API endpoints for infrastructure operations.
"""

from fastapi import APIRouter, HTTPException, Query, Path
import src.validator as validator
from api.dependencies import validate_project_context, validate_provider, check_template_protection
from logger import print_stack_trace, logger

import providers.deployer as core_deployer
from src.core.factory import create_context


router = APIRouter(prefix="/infrastructure")


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))
