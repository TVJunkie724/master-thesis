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
    List all available projects with metadata.
    Returns project names, descriptions, and version counts.
    """
    try:
        project_names = file_manager.list_projects()
        projects = []
        
        for name in project_names:
            project_info = {"name": name, "description": None, "version_count": 0}
            
            # Read project_info.json if exists
            project_dir = os.path.join(
                state.get_project_base_path(), 
                CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
                name
            )
            info_path = os.path.join(project_dir, CONSTANTS.PROJECT_INFO_FILE)
            if os.path.exists(info_path):
                try:
                    with open(info_path, 'r') as f:
                        info = json.load(f)
                        project_info["description"] = info.get("description")
                except Exception:
                    pass
            
            # Count versions
            versions_dir = os.path.join(project_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)
            if os.path.exists(versions_dir):
                project_info["version_count"] = len([
                    f for f in os.listdir(versions_dir) if f.endswith('.zip')
                ])
            
            projects.append(project_info)
        
        return {"projects": projects, "active_project": state.get_active_project()}
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects", tags=["Projects"])
async def create_project(
    request: Request, 
    project_name: str = Query(..., description="Name of the new project"),
    description: str = Query(None, description="Optional project description")
):
    """
    Upload a new project zip file with optional description.
    If description is not provided, it will be auto-generated from digital_twin_name.
    Supports Multipart (binary) or JSON (Base64).
    """
    try:
        content = await extract_file_content(request)
        result = file_manager.create_project_from_zip(project_name, content, description=description)
        return result
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
        ConfigType.aws_hierarchy: "twin_hierarchy/aws_hierarchy.json",
        ConfigType.azure_hierarchy: "twin_hierarchy/azure_hierarchy.json",
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
async def update_project_zip(
    project_name: str, 
    request: Request,
    description: str = Query(None, description="Optional project description update")
):
    """
    Updates an existing project by overwriting it with a new validated zip file.
    Archives the new version before extracting.
    Supports Multipart (binary) or JSON (Base64).
    """
    try:
        content = await extract_file_content(request)
        result = file_manager.update_project_from_zip(project_name, content, description=description)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_name}", tags=["Projects"])
def delete_project_endpoint(project_name: str):
    """
    Deletes a project and all its versions.
    If the deleted project was active, resets to default project.
    """
    try:
        # Check if active project and reset to default if needed
        if state.get_active_project() == project_name:
            state.reset_state()
        
        file_manager.delete_project(project_name)
        return {"message": f"Project '{project_name}' deleted successfully."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/projects/{project_name}/info", tags=["Projects"])
async def update_project_info_endpoint(project_name: str, request: Request):
    """
    Updates project metadata (description only, without re-uploading zip).
    Body: {"description": "New description"}
    """
    try:
        body = await request.json()
        description = body.get("description")
        if not description:
            raise HTTPException(status_code=400, detail="Missing 'description' field in request body.")
        
        file_manager.update_project_info(project_name, description)
        return {"message": f"Project info updated for '{project_name}'."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
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

@router.put("/projects/{project_name}/simulator/payloads", tags=["Projects"])
async def upload_simulator_payloads(project_name: str, request: Request):
    """
    Uploads payloads.json for the simulator (provider-agnostic).
    Validates structure before saving to iot_device_simulator/payloads.json.
    """
    try:
        content = await extract_file_content(request)
        content_str = content.decode('utf-8')
        
        is_valid, errors, warnings = validator.validate_simulator_payloads(content_str, project_name=project_name)
        
        if not is_valid:
            raise ValueError(f"Payload validation failed: {errors}")
            
        # Save to iot_device_simulator root (provider-agnostic)
        path = os.path.join(
            state.get_project_base_path(), 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            project_name, 
            CONSTANTS.IOT_DEVICE_SIMULATOR_DIR_NAME
        )
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, CONSTANTS.PAYLOADS_FILE), "w") as f:
            f.write(content_str)
            
        return {"message": "Payloads uploaded successfully.", "warnings": warnings}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
