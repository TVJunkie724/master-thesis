from fastapi import APIRouter, HTTPException, Query
import info
import deployers.additional_deployer as hierarchy_deployer
import deployers.event_action_deployer as event_action_deployer
import file_manager
import src.validator as validator
from api.dependencies import validate_project_context
from logger import print_stack_trace, logger

router = APIRouter()

@router.get("/check", tags=["Status"])
def check_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Runs all checks (L1 to L5) for the specified provider."""
    validate_project_context(project_name)
    try:
        validator.verify_project_structure(project_name)
        provider = provider.lower()
        info.check(provider)
        hierarchy_deployer.info(provider)
        event_action_deployer.info(provider)
        return {"message": f"System check (all layers) completed for provider '{provider}'. See logs for detailed status."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check_l1", tags=["Status"])
def check_l1_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Check Level 1 (IoT Dispatcher Layer) for the specified provider."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        info.check_l1(provider)
        return {"message": f"Check L1 completed for provider '{provider}'."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check_l2", tags=["Status"])
def check_l2_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Check Level 2 (Persister & Processor Layer) for the specified provider."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        info.check_l2(provider)
        return {"message": f"Check L2 completed for provider '{provider}'."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check_l3", tags=["Status"])
def check_l3_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Check Level 3 (Hot, Cold, Archive Storage) for the specified provider."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        info.check_l3(provider)
        return {"message": f"Check L3 completed for provider '{provider}'."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check_l4", tags=["Status"])
def check_l4_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Check Level 4 (TwinMaker Layer) for the specified provider."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        info.check_l4(provider)
        return {"message": f"Check L4 completed for provider '{provider}'."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check_l5", tags=["Status"])
def check_l5_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Check Level 5 (Grafana / Visualization Layer) for the specified provider."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        info.check_l5(provider)
        return {"message": f"Check L5 completed for provider '{provider}'."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
