from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Path, Request
import json
import os
import file_manager
import src.validator as validator
from api.dependencies import ConfigType, ProviderEnum
import constants as CONSTANTS
from logger import logger
from api.utils import extract_file_content

import src.core.state as state

router = APIRouter()

# ==========================================
# 1. Project Management
# ==========================================
@router.get("/projects", tags=["Projects"])
def list_projects():
    """
    List all available projects.
    """
    try:
        projects = file_manager.list_projects()
        return {"projects": projects, "active_project": state.get_active_project()}
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects", tags=["Projects"])
async def create_project(request: Request, project_name: str = Query(..., description="Name of the new project")):
    """
    Upload a new project zip file.
    Supports Multipart (binary) or JSON (Base64).
    """
    try:
        content = await extract_file_content(request)
        file_manager.create_project_from_zip(project_name, content)
        return {"message": f"Project '{project_name}' created successfully."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/projects/{project_name}/activate", tags=["Projects"])
def activate_project(project_name: str):
    """
    Switch the active project.
    """
    try:
        state.set_active_project(project_name)
        # Note: Global AWS client initialization is removed as we move to per-request DeploymentContext
        return {"message": f"Active project switched to '{project_name}'."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_name}/validate", tags=["Projects"])
def validate_project_structure(project_name: str = Path(..., description="Name of the project structure to validate")):
    """
    Triggers a full validation of the project structure.
    Checks:
    - Required files presence.
    - Content validity of configs.
    - Consistency of optimization flags (e.g., dependencies like code presence).
    
    Returns:
        JSON message indicating validity.
    """
    try:
        validator.verify_project_structure(project_name)
        return {"message": f"Project structure for '{project_name}' is valid."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. Config & Code Updates
# ==========================================
@router.put("/projects/{project_name}/config/{config_type}", tags=["Projects"])
async def update_config(project_name: str, config_type: ConfigType, request: Request):
    """
    Update a specific configuration file for a project.
    config_type: Select from the dropdown.
    Supports Multipart (binary) or JSON (Base64).
    """
    config_map = {
        ConfigType.config: "config.json",
        ConfigType.iot: "config_iot_devices.json",
        ConfigType.events: "config_events.json",
        ConfigType.hierarchy: "config_hierarchy.json",
        ConfigType.credentials: "config_credentials.json",
        ConfigType.providers: "config_providers.json",
        ConfigType.optimization: "config_optimization.json"
    }
    
    filename = config_map[config_type]
    
    try:
        content = await extract_file_content(request)
        json_content = json.loads(content)
        file_manager.update_config_file(project_name, filename, json_content)
        return {"message": f"Configuration '{filename}' updated for project '{project_name}'."}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON content.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_name}/upload/zip", tags=["Projects"])
async def update_project_zip(project_name: str, request: Request):
    """
    Updates an existing project by overwriting it with a new validated zip file.
    Supports Multipart (binary) or JSON (Base64).
    """
    try:
        content = await extract_file_content(request)
        file_manager.update_project_from_zip(project_name, content)
        return {"message": f"Project '{project_name}' updated successfully from zip."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_name}/functions/{function_name}/file", tags=["Projects"])
async def update_function_file(
    project_name: str, 
    function_name: str, 
    request: Request,
    target_filename: str = Query(..., description="Target filename (e.g., lambda_function.py)")
):
    """
    Uploads and updates a specific code file for a function.
    Strictly validates code based on the function's provider.
    Supports Multipart (binary) or JSON (Base64).
    """
    try:
        content = await extract_file_content(request)
        content_str = content.decode('utf-8')
        
        file_manager.update_function_code_file(project_name, function_name, target_filename, content_str)
        return {"message": f"File '{target_filename}' updated for function '{function_name}'."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/projects/{project_name}/state_machines/{provider}", tags=["Projects"])
async def upload_state_machine(
    project_name: str,
    provider: ProviderEnum,
    request: Request
):
    """
    Uploads and validates a state machine definition file for a specific provider.
    Supports Multipart (binary) or JSON (Base64).
    """
    try:
        provider_value = provider.value.lower()
        target_filename = None
        if provider_value == "aws":
            target_filename = CONSTANTS.AWS_STATE_MACHINE_FILE
        elif provider_value == "azure":
             target_filename = CONSTANTS.AZURE_STATE_MACHINE_FILE
        elif provider_value == "google":
             target_filename = CONSTANTS.GOOGLE_STATE_MACHINE_FILE
        else:
             raise ValueError("Invalid provider. Must be 'aws', 'azure', or 'google'.")

        content = await extract_file_content(request)
        content_str = content.decode('utf-8')
        
        # 1. Validate Content matches Provider Signature
        validator.validate_state_machine_content(target_filename, content_str)
        
        # 2. Save File
        upload_dir = os.path.join(state.get_project_base_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name)
        sm_dir = os.path.join(upload_dir, CONSTANTS.STATE_MACHINES_DIR_NAME)
        
        if not os.path.exists(sm_dir):
             os.makedirs(sm_dir)   
             
        target_file = os.path.join(sm_dir, target_filename)
        with open(target_file, 'w') as f:
            f.write(content_str)
            
        return {"message": f"State machine '{target_filename}' uploaded and verified for provider '{provider_value}'."}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/projects/{project_name}/simulator/{provider}/payloads", tags=["Projects"])
async def upload_simulator_payloads(project_name: str, provider: str, request: Request):
    """
    Uploads payloads.json for the simulator.
    Validates structure before saving.
    """
    if provider != "aws":
        raise HTTPException(status_code=400, detail="Only 'aws' provider is currently supported.")

    try:
        content = await extract_file_content(request)
        content_str = content.decode('utf-8')
        
        is_valid, errors, warnings = validator.validate_simulator_payloads(content_str, project_name=project_name)
        
        if not is_valid:
            raise ValueError(f"Payload validation failed: {errors}")
            
        # Save
        path = os.path.join(state.get_project_base_path(), "upload", project_name, "iot_device_simulator", provider)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "payloads.json"), "w") as f:
            f.write(content_str)
            
        return {"message": "Payloads uploaded successfully.", "warnings": warnings}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
