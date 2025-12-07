from fastapi import APIRouter, HTTPException
import json
import globals
from util import pretty_json
from logger import logger, print_stack_trace

router = APIRouter()

@router.get("/", tags=["Info"])
def read_root():
    """
    Check if the API is running.
    """
    return {"status": "API is running", "active_project": globals.CURRENT_PROJECT}

@router.get("/info/config", tags=["Info"])
def get_main_config():
    """
    Retrieve the main configuration of the digital twin environment.
    """
    try:
        return pretty_json(globals.config)
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
        return pretty_json(globals.config_iot_devices)
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
        return pretty_json(globals.config_providers)
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
#         return pretty_json(globals.config_credentials)
#     except Exception as e:
#         print_stack_trace()
#         logger.error(str(e))
#         raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/info/config_hierarchy", tags=["Info"])
def get_config_hierarchy():
    """
    Retrieve the hierarchical entity configuration of the digital twin environment.
    """
    try:
        with open("config_hierarchy.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return pretty_json(data)
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
        with open("config_events.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return pretty_json(data)
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
