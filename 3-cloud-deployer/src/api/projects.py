from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Path, Request
import json
import os
import file_manager
import src.validator as validator
from api.dependencies import ConfigType, ProviderEnum, check_template_protection
import constants as CONSTANTS
from logger import logger
from api.utils import extract_file_content
from api.functions import invalidate_function_cache, clear_all_hash_metadata

import src.core.state as state

router = APIRouter()





# ==========================================
# 1. Project Management
# ==========================================
@router.get(
    "/projects", 
    tags=["Projects"],
    summary="List all projects",
    responses={200: {"description": "Project list retrieved successfully"}}
)
def list_projects():
    """
    List all available projects with metadata.
    
    **Returns:**
    - Project names, descriptions, and version counts
    - Currently active project name
    
    **Use case:** Dashboard project selector, project overview.
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

@router.post(
    "/projects", 
    tags=["Projects"],
    summary="Create new project from zip",
    responses={
        200: {"description": "Project created successfully"},
        400: {"description": "Invalid zip file or validation failed"}
    }
)
async def create_project(
    request: Request, 
    project_name: str = Query(..., description="Name of the new project"),
    description: str = Query(None, description="Optional project description")
):
    """
    Upload a new project zip file with optional description.
    
    **Accepts:** Multipart (binary) or JSON (Base64 encoded).
    
    **Validation performed:**
    - Zip structure validation (required files)
    - Config schema validation
    - Cross-config consistency checks (payloads ↔ devices, credentials ↔ providers)
    
    **If description not provided:** Auto-generated from digital_twin_name in config.json.
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

@router.get(
    "/projects/{project_name}/validate", 
    tags=["Projects"],
    summary="Validate project structure",
    responses={
        200: {"description": "Project structure is valid"},
        400: {"description": "Validation failed with details"}
    }
)
def validate_project_structure(project_name: str = Path(..., description="Name of the project structure to validate")):
    """
    Validates an existing project's structure on disk.
    
    **Checks performed:**
    - Required files presence (config.json, config_providers.json, etc.)
    - Config content validity (schema validation)
    - Optimization flag dependencies (event_actions, feedback functions, state machines)
    - Cross-config consistency (payloads ↔ devices, credentials ↔ providers)
    
    **Use case:** Pre-deployment readiness check for existing projects.
    """
    try:
        validator.verify_project_structure(project_name, state.get_project_base_path())
        return {"message": f"Project structure for '{project_name}' is valid."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. Config Reading (Stateless)
# ==========================================
@router.get(
    "/projects/{project_name}/config/{config_type}",
    tags=["Projects"],
    summary="Get project configuration",
    responses={
        200: {"description": "Configuration retrieved successfully"},
        404: {"description": "Project or config file not found"}
    }
)
def get_project_config(
    project_name: str = Path(..., description="Project name"),
    config_type: ConfigType = Path(..., description="Type of configuration to retrieve")
):
    """
    Retrieve a specific configuration file from a project.
    
    **Config types:**
    - `config`: Main config.json (digital twin settings)
    - `iot`: IoT devices configuration
    - `events`: Event-driven automation rules
    - `providers`: Cloud provider per layer
    - `aws_hierarchy`: AWS TwinMaker hierarchy
    - `azure_hierarchy`: Azure Digital Twins hierarchy
    - `credentials`: Cloud credentials (sensitive --> only example file returned)
    - `optimization`: Optimization flags
    
    **Note:** This endpoint replaces the deprecated `/info/config*` endpoints
    with explicit project parameter for stateless API design.
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
    
    is_template_project = project_name == CONSTANTS.DEFAULT_PROJECT_NAME
    do_return_credentials_file = False
    try:
        if config_type == ConfigType.credentials:
            do_return_credentials_file = True


        project_path = os.path.join(
            state.get_project_base_path(),
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            project_name
        )
        
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
        
        if not do_return_credentials_file:
            file_path = os.path.join(project_path, filename)
        else:
            file_path = os.path.join(project_path, filename + ".example")

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404, 
                detail=f"Config file '{filename}' not found in project '{project_name}'"
            )
        
        print(is_template_project, do_return_credentials_file)
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 3. Config Updates
# ==========================================
@router.put("/projects/{project_name}/config/{config_type}", tags=["Projects"])
async def update_config(project_name: str, config_type: ConfigType, request: Request):
    """
    Update a specific configuration file for a project.
    config_type: Select from the dropdown.
    Supports Multipart (binary) or JSON (Base64).
    """
    check_template_protection(project_name, "update config for")
    
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

@router.post("/projects/{project_name}/import", tags=["Projects"])
async def import_project(
    project_name: str, 
    file: UploadFile = File(..., description="Project zip file"),
    description: str = Query(None, description="Optional project description update")
):
    """
    Import/update a project from a zip file.
    
    **Prerequisite:** Project must exist or be created via POST /projects first.
    
    **Validation performed:**
    - Project existence check
    - Zip structure validation
    - Config schema validation
    """
    check_template_protection(project_name, "import to")
    
    # Check project exists first
    project_path = os.path.join(state.get_project_upload_path(), project_name)
    if not os.path.exists(project_path):
        raise HTTPException(
            status_code=400, 
            detail=f"Project '{project_name}' does not exist. Create it first with POST /projects"
        )
    
    try:
        content = await file.read()
        result = file_manager.update_project_from_zip(project_name, content, description=description)
        
        # Clear all hash metadata since project ZIP is fully replaced
        clear_all_hash_metadata(project_name)
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/projects/{project_name}/export",
    tags=["Projects"],
    summary="Export project as zip",
    responses={
        200: {"description": "Project zip file"},
        404: {"description": "Project not found"}
    }
)
async def export_project(
    project_name: str = Path(..., description="Name of the project to export")
):
    """
    Export a project as a downloadable zip file.
    
    **Package contents:**
    - All configuration files (config.json, config_*.json)
    - Twin hierarchy definitions
    - State machines, user functions, IoT payloads, 3D assets
    
    **Use case:** Backup, share, or migrate projects.
    """
    from fastapi.responses import StreamingResponse
    
    try:
        zip_buffer = file_manager.export_project_to_zip(project_name)
        
        filename = f"{project_name}_export.zip"
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/projects/{project_name}/summary",
    tags=["Projects"],
    summary="Get project dashboard summary"
)
def get_project_summary(
    project_name: str = Path(..., description="Project name")
):
    """
    Dashboard overview for Flutter frontend integration.
    
    Returns:
    - name, description
    - providers (from config_providers.json)
    - deployment_status (local check)
    - validation_status (structure check)
    """
    project_path = os.path.join(state.get_project_upload_path(), project_name)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    summary = {
        "name": project_name,
        "description": None,
        "providers": {},
        "deployment_status": "unknown", # placeholder, implement real logic if needed
        "validation_status": "unknown"
    }

    # 1. Description
    info_path = os.path.join(project_path, CONSTANTS.PROJECT_INFO_FILE)
    if os.path.exists(info_path):
        try:
            with open(info_path, 'r') as f:
                info = json.load(f)
                summary["description"] = info.get("description")
        except: pass

    # 2. Providers
    prov_path = os.path.join(project_path, CONSTANTS.CONFIG_PROVIDERS_FILE)
    if os.path.exists(prov_path):
        try:
            with open(prov_path, 'r') as f:
                summary["providers"] = json.load(f)
        except: pass

    # 3. Validation Status
    try:
        validator.verify_project_structure(project_name, state.get_project_base_path())
        summary["validation_status"] = "valid"
    except Exception as e:
        summary["validation_status"] = "invalid"
        summary["validation_error"] = str(e)
        
    return summary


@router.get(
    "/projects/{project_name}/files",
    tags=["Projects"],
    summary="Get project file tree"
)
def get_project_files(
    project_name: str = Path(..., description="Project name")
):
    """
    Returns a recursive file tree structure for the project.
    Used for file browsing in the frontend.
    """
    try:
        files = file_manager.get_project_file_tree(project_name)
        return {"files": files}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/projects/{project_name}/files/{file_path:path}",
    tags=["Projects"],
    summary="Get project file content"
)
def get_project_file_content_endpoint(
    project_name: str = Path(..., description="Project name"),
    file_path: str = Path(..., description="Relative path to file")
):
    """
    Returns the content of a specific file.
    """
    try:
        content = file_manager.get_project_file_content(project_name, file_path)
        return content
    except ValueError as e:
        if "not found" in str(e):
             raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_name}", tags=["Projects"])
def delete_project_endpoint(project_name: str):
    """
    Deletes a project and all its versions.
    If the deleted project was active, resets to default project.
    """
    check_template_protection(project_name, "delete")
    
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
    check_template_protection(project_name, "update info for")
    
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
    check_template_protection(project_name, "upload state machine to")
    
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
    check_template_protection(project_name, "upload payloads to")
    
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


# ==========================================
# 4. Project Cleanup (AWS-specific)
# ==========================================
@router.delete(
    "/projects/{project_name}/cleanup/aws-twinmaker",
    tags=["Projects"],
    summary="Force delete AWS TwinMaker workspace",
    responses={
        200: {"description": "TwinMaker workspace deleted"},
        500: {"description": "Deletion failed"}
    }
)
def cleanup_aws_twinmaker(
    project_name: str = Path(..., description="Name of the project")
):
    """
    Force delete AWS TwinMaker workspace when Terraform destroy fails.
    
    **Use case:** When `terraform destroy` fails because TwinMaker contains entities.
    
    **Deletion order:**
    1. Delete all entities
    2. Delete all component types
    3. Delete workspace
    
    **Note:** AWS-specific operation. Only works for projects using AWS for L4.
    """
    from api.dependencies import validate_project_context
    validate_project_context(project_name)
    try:
        from src.providers.aws.provider import AWSProvider
        from src.providers.aws.layers.layer_4_twinmaker import force_delete_twinmaker_workspace
        from src.core.config_loader import load_project_config, load_credentials
        from pathlib import Path as PathLib
        from logger import print_stack_trace
        
        project_path = PathLib("upload") / project_name
        config = load_project_config(project_path)
        credentials = load_credentials(project_path)
        
        provider = AWSProvider()
        provider.initialize_clients(credentials.get("aws", {}), config.digital_twin_name)
        
        result = force_delete_twinmaker_workspace(provider)
        
        return {
            "message": "TwinMaker workspace deletion complete",
            "result": result
        }
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
