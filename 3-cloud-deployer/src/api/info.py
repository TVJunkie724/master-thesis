"""
API Info Endpoints - Configuration viewing endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
import json
import os
from util import pretty_json
from logger import logger, print_stack_trace
import src.core.state as state

router = APIRouter()

def _get_config_path(filename: str) -> str:
    """Resolve path to a config file for the active project."""
    project = state.get_active_project()
    base_path = state.get_project_upload_path()
    return os.path.join(base_path, project, filename)

def _read_json_file(filename: str):
    """Read a JSON file from the active project."""
    try:
        path = _get_config_path(filename)
        if not os.path.exists(path):
             raise FileNotFoundError(f"File not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading {filename}: {e}")
        raise

@router.get("/", tags=["Info"])
def read_root():
    """
    Check if the API is running.
    """
    return {"status": "API is running", "active_project": state.get_active_project()}

@router.get("/info/config", tags=["Info"])
def get_main_config():
    """
    Retrieve the main configuration of the digital twin environment.
    """
    try:
        return pretty_json(_read_json_file("config.json"))
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/info/config_iot_devices", tags=["Info"])
def get_iot_config():
    """
    Retrieve the configuration for all IoT devices.
    """
    try:
        return pretty_json(_read_json_file("config_iot_devices.json"))
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/info/config_providers", tags=["Info"])
def get_providers_config():
    """
    Retrieve the cloud provider configuration for each deployment layer.
    """
    try:
        return pretty_json(_read_json_file("config_providers.json"))
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

# @router.get("/info/config_credentials", tags=["Info"])
# def get_credentials_config():
#     """
#     Retrieve the cloud credentials configuration.
#     """
#     try:
#         return pretty_json(_read_json_file("config_credentials.json"))
#     except Exception as e:
#         print_stack_trace()
#         logger.error(str(e))
#         raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/info/config_hierarchy", tags=["Info"])
def get_config_hierarchy(provider: str = Query("aws", description="Provider: aws or azure")):
    """
    Retrieve the hierarchical entity configuration for the specified provider.
    
    Args:
        provider: The cloud provider (aws or azure). Defaults to aws.
        
    Raises:
        HTTPException 400: If provider is not 'aws' or 'azure'
    """
    provider_lower = provider.lower()
    
    # Only aws and azure have hierarchy files
    if provider_lower not in ("aws", "azure"):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid provider '{provider}'. Hierarchy is only available for 'aws' or 'azure'."
        )
    
    try:
        if provider_lower == "azure":
            return pretty_json(_read_json_file("twin_hierarchy/azure_hierarchy.json"))
        else:
            return pretty_json(_read_json_file("twin_hierarchy/aws_hierarchy.json"))
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/info/config_events", tags=["Info"])
def get_config_events():
    """
    Retrieve the event-driven automation configuration of the digital twin environment.
    """
    try:
        return pretty_json(_read_json_file("config_events.json"))
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
