from fastapi import APIRouter, HTTPException, Query
import src.validator as validator
from api.dependencies import validate_project_context, validate_provider
from logger import print_stack_trace, logger

# New Provider Deployers
import providers.deployer as core_deployer

# AWS Specific Deployers (Direct import until Provider Pattern is fully implemented for these)
import src.providers.aws.layers.layer_4_twinmaker as hierarchy_deployer_aws
import src.providers.aws.layers.layer_2_compute as event_action_deployer_aws
import src.providers.aws.layers.layer_1_iot as init_values_deployer_aws

from src.core.factory import create_context



router = APIRouter()

# Helper dispatcher functions to replicate facade logic inline
def _deploy_hierarchy(context, provider: str):
    if provider == "aws":
        hierarchy_deployer_aws.create_twinmaker_hierarchy(
            provider=context.providers["aws"],
            hierarchy=context.config.hierarchy,
            config={"digital_twin_name": context.config.digital_twin_name}
        )
    else:
        raise NotImplementedError(f"{provider} hierarchy deployment not implemented.")

def _destroy_hierarchy(context, provider: str):
    if provider == "aws":
        hierarchy_deployer_aws.destroy_twinmaker_hierarchy(
            provider=context.providers["aws"],
            hierarchy=context.config.hierarchy
        )
    else:
        raise NotImplementedError(f"{provider} hierarchy destruction not implemented.")

def _deploy_event_actions(context, provider: str):
    if provider == "aws":
        # Construct digital_twin_info for Lambda environment
        digital_twin_info = {
            "config": {
                "digital_twin_name": context.config.digital_twin_name,
                "hot_storage_size_in_days": context.config.hot_storage_size_in_days,
                "cold_storage_size_in_days": context.config.cold_storage_size_in_days,
                "mode": context.config.mode,
            },
            "config_iot_devices": context.config.iot_devices,
            "config_events": context.config.events
        }
        
        event_action_deployer_aws.deploy_lambda_actions(
            provider=context.providers["aws"],
            events=context.config.events,
            project_path=str(context.project_path),
            digital_twin_info=digital_twin_info
        )
    else:
        raise NotImplementedError(f"{provider} event action deployment not implemented.")

def _destroy_event_actions(context, provider: str):
    if provider == "aws":
        event_action_deployer_aws.destroy_lambda_actions(
            provider=context.providers["aws"],
            events=context.config.events
        )
    else:
        raise NotImplementedError(f"{provider} event action destruction not implemented.")

def _redeploy_event_actions(context, provider: str):
    if provider == "aws":
        _destroy_event_actions(context, provider)
        _deploy_event_actions(context, provider)
    else:
        raise NotImplementedError(f"{provider} event action redeployment not implemented.")

def _deploy_init_values(context, provider: str):
    if provider == "aws":
        # Assuming provider naming is available on the provider instance
        init_values_deployer_aws.post_init_values_to_iot_core(
            provider=context.providers["aws"],
            iot_devices=context.config.iot_devices
        )
    else:
        raise NotImplementedError(f"{provider} init values deployment not implemented.")


# --------- Core + IoT Deploy/Destroy ----------
@router.post("/deploy", tags=["Deployment"])
def deploy_all(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """
    Deploys the full digital twin environment including IoT devices, processors, and TwinMaker components.
    """
    validate_project_context(project_name)
    try:
        validator.verify_project_structure(project_name)
        provider = validate_provider(provider)
        
        context = create_context(project_name, provider)
        
        # Core layers deploy all resources including per-device components
        core_deployer.deploy_all(context, provider)
        
        # Additional layers
        _deploy_hierarchy(context, provider)
        _deploy_event_actions(context, provider)
        _deploy_init_values(context, provider)
        
        return {"message": "Core and IoT services deployed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recreate_updated_events", tags=["Deployment"])
def recreate_updated_events(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """
    Redeploys the events (event_actions and event_checker).
    """
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        context = create_context(project_name, provider)
        
        _redeploy_event_actions(context, provider)
        
        # Redeploy L2 event checker
        if provider == "aws":
            core_deployer.redeploy_event_checker(context, provider)
        else:
            raise NotImplementedError(f"{provider} redeployment not implemented.")

        return {"message": "Events recreated successfully"}
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
    """
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        context = create_context(project_name, provider)
        
        # Destroy in reverse order
        _destroy_event_actions(context, provider)
        _destroy_hierarchy(context, provider)
        # Per-device resources destroyed by layer adapters within destroy_all()
        core_deployer.destroy_all(context, provider)
        
        return {"message": "Core and IoT services destroyed successfully"}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
