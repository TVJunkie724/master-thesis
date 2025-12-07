from fastapi import APIRouter, HTTPException, Query
import file_manager
import src.validator as validator
import deployers.core_deployer as core_deployer
import deployers.iot_deployer as iot_deployer
import deployers.additional_deployer as hierarchy_deployer
import deployers.event_action_deployer as event_action_deployer
from api.dependencies import validate_project_context
from logger import print_stack_trace, logger

router = APIRouter()

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
        provider = provider.lower()
        core_deployer.deploy(provider)
        iot_deployer.deploy(provider)
        hierarchy_deployer.deploy(provider)
        event_action_deployer.deploy(provider)
        return {"message": "Core and IoT services deployed successfully"}
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
        event_action_deployer.redeploy(provider)
        core_deployer.redeploy_l2_event_checker(provider)
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
        event_action_deployer.destroy(provider)
        hierarchy_deployer.destroy(provider)
        iot_deployer.destroy(provider)
        core_deployer.destroy(provider)
        return {"message": "Core and IoT services destroyed successfully"}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deploy_l1", tags=["Deployment"])
def deploy_l1_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Deploy Level 1 (L1) – IoT Dispatcher Layer."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.deploy_l1(provider)
        return {"message": "L1 deployment (IoT Dispatcher Layer) completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/destroy_l1", tags=["Destroy"])
def destroy_l1_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Destroy Level 1 (L1) – IoT Dispatcher Layer."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.destroy_l1(provider)
        return {"message": "L1 destruction (IoT Dispatcher Layer) completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deploy_l2", tags=["Deployment"])
def deploy_l2_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Deploy Level 2 (L2) – Persister / Processor Layer."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.deploy_l2(provider)
        return {"message": "L2 deployment (Persister Layer) completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/destroy_l2", tags=["Destroy"])
def destroy_l2_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Destroy Level 2 (L2) – Persister / Processor Layer."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.destroy_l2(provider)
        return {"message": "L2 destruction (Persister Layer) completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deploy_l3", tags=["Deployment"])
def deploy_l3_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Deploy Level 3 (L3) – Storage Layers."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.deploy_l3_hot(provider)
        core_deployer.deploy_l3_cold(provider)
        core_deployer.deploy_l3_archive(provider)
        return {"message": "L3 deployment (Hot, Cold, Archive Storage) completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/destroy_l3", tags=["Destroy"])
def destroy_l3_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Destroy Level 3 (L3) – Storage Layers."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.destroy_l3_hot(provider)
        core_deployer.destroy_l3_cold(provider)
        core_deployer.destroy_l3_archive(provider)
        return {"message": "L3 destruction (Hot, Cold, Archive Storage) completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deploy_l4", tags=["Deployment"])
def deploy_l4_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Deploy Level 4 (L4) – TwinMaker Layer."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.deploy_l4(provider)
        return {"message": "L4 TwinMaker deployment completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/destroy_l4", tags=["Destroy"])
def destroy_l4_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Destroy Level 4 (L4) – TwinMaker Layer."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.destroy_l4(provider)
        return {"message": "L4 TwinMaker destruction completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deploy_l5", tags=["Deployment"])
def deploy_l5_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Deploy Level 5 (L5) – Visualization Layer."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.deploy_l5(provider)
        return {"message": "L5 Grafana deployment completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/destroy_l5", tags=["Destroy"])
def destroy_l5_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Destroy Level 5 (L5) – Visualization Layer."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        core_deployer.destroy_l5(provider)
        return {"message": "L5 Grafana destruction completed successfully."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
