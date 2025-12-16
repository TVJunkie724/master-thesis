"""
Deployment API endpoints.

All deployment is now handled by TerraformDeployerStrategy.
This module provides REST API endpoints for deployment operations.
"""

from fastapi import APIRouter, HTTPException, Query
import src.validator as validator
from api.dependencies import validate_project_context, validate_provider
from logger import print_stack_trace, logger

import providers.deployer as core_deployer
from src.core.factory import create_context


router = APIRouter()


# --------- Core Deploy/Destroy ----------
@router.post("/deploy", tags=["Deployment"])
def deploy_all(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """
    Deploys the full digital twin environment.
    
    All deployment (infrastructure, Lambda code, TwinMaker entities, IoT registration)
    is handled by TerraformDeployerStrategy.
    """
    validate_project_context(project_name)
    try:
        validator.verify_project_structure(project_name)
        provider = validate_provider(provider)
        
        context = create_context(project_name, provider)
        
        # TerraformDeployerStrategy handles all deployment
        core_deployer.deploy_all(context, provider)
        
        return {"message": "Core and IoT services deployed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/destroy", tags=["Destroy"])
def destroy_all(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """
    Destroys the full digital twin environment.
    
    All destruction is handled by TerraformDeployerStrategy (terraform destroy).
    """
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
