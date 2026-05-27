"""
Project Management API endpoints for the Deployer.

This module provides CRUD operations for deployment projects. Projects contain
all configuration, credentials, state machines, and IoT payloads needed for
Digital Twin deployment.

**Key concepts:**
- Projects are stored as directories with configuration files
- The 'template' project is read-only and serves as a reference
- Projects can be imported/exported as ZIP files
"""
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Path, Request
import json
import file_manager
import src.validator as validator
from src.validation.directory_validator import validate_project_directory
from src.core.project_storage import (
    ProjectFileAccessDenied,
    ProjectStorageError,
    get_project_storage,
)
from api.dependencies import ConfigType, ProviderEnum, check_template_protection
import constants as CONSTANTS
from logger import logger
from api.utils import extract_file_content
from api.functions import invalidate_function_cache, clear_all_hash_metadata
from api.error_models import ERROR_RESPONSES

import src.core.state as state

router = APIRouter()





# ==========================================
# 1. Project Management
# ==========================================
@router.get(
    "/projects", 
    operation_id="listDeploymentProjects",
    tags=["Projects"],
    summary="List all deployment projects with metadata",
    description=(
        "**Purpose:** Returns all available projects for the project selector UI.\n\n"
        "**Response includes:**\n"
        "- Project names and descriptions\n"
        "- Version counts (saved ZIP snapshots)\n"
        "- Currently active project name"
    ),
    responses={
        200: {"description": "Project list retrieved successfully"},
        500: ERROR_RESPONSES[500],
    }
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
        storage = get_project_storage()
        project_names = storage.list_projects()
        projects = []
        
        for name in project_names:
            project_info = {"name": name, "description": None, "version_count": 0}
            
            # Read project_info.json if exists
            try:
                info = storage.read_json_optional(name, CONSTANTS.PROJECT_INFO_FILE)
                if isinstance(info, dict):
                    project_info["description"] = info.get("description")
            except (ProjectFileAccessDenied, ProjectStorageError, json.JSONDecodeError):
                pass
            
            # Count versions
            project_info["version_count"] = storage.version_count(name)
            
            projects.append(project_info)
        
        return {"projects": projects, "active_project": state.get_active_project()}
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")

@router.post(
    "/projects", 
    operation_id="createDeploymentProject",
    tags=["Projects"],
    summary="Create new project from uploaded ZIP file",
    description=(
        "**Purpose:** Creates a new deployment project from a ZIP file.\n\n"
        "**ZIP structure expected:**\n"
        "- config.json (required)\n"
        "- config_providers.json (required)\n"
        "- config_credentials.json (required)\n"
        "- config_iot_devices.json, config_events.json, etc.\n\n"
        "**Validation performed:**\n"
        "- ZIP structure validation\n"
        "- Config schema validation\n"
        "- Cross-config consistency checks"
    ),
    responses={
        200: {"description": "Project created successfully"},
        400: ERROR_RESPONSES[400],
        422: ERROR_RESPONSES[422],
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
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")

@router.get(
    "/projects/{project_name}/validate", 
    operation_id="validateProjectStructure",
    tags=["Projects"],
    summary="Validate project structure and configuration",
    description=(
        "**Purpose:** Pre-deployment readiness check for existing projects.\n\n"
        "**Checks performed:**\n"
        "- Required files presence\n"
        "- Config content validity (schema validation)\n"
        "- Optimization flag dependencies\n"
        "- Cross-config consistency (payloads ↔ devices, credentials ↔ providers)"
    ),
    responses={
        200: {"description": "Project structure is valid"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
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
        project_dir = get_project_storage().context(project_name).project_path
        validate_project_directory(project_dir)
        return {
            "message": f"Project structure for '{project_name}' is valid.",
            "manifest": _build_manifest_summary(project_dir),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")


def _build_manifest_summary(project_dir) -> dict:
    """Return safe manifest metadata for API callers."""
    manifest_path = project_dir / CONSTANTS.DEPLOYMENT_MANIFEST_FILE
    if not manifest_path.exists():
        return {"manifest_backed": False}

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    twin = manifest.get("twin") if isinstance(manifest, dict) else {}
    if not isinstance(twin, dict):
        twin = {}

    return {
        "manifest_backed": True,
        "manifest_version": manifest.get("manifest_version"),
        "producer": manifest.get("producer"),
        "resource_name": twin.get("resource_name"),
    }

# ==========================================
# 2. Config Reading (Stateless)
# ==========================================
@router.get(
    "/projects/{project_name}/config/{config_type}",
    operation_id="getProjectConfig",
    tags=["Projects"],
    summary="Get project configuration",
    description=(
        "**Purpose:** Retrieve a specific configuration file from a project.\n\n"
        "**When to call:** To load config for editing in wizard or display.\n\n"
        "**Path params:** config_type = config|iot|events|providers|credentials|optimization|aws_hierarchy|azure_hierarchy"
    ),
    responses={
        200: {"description": "Configuration retrieved successfully"},
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
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
    
    do_return_credentials_file = False
    try:
        if config_type == ConfigType.credentials:
            do_return_credentials_file = True


        storage = get_project_storage()
        project_path = storage.context(project_name).project_path
        
        if not project_path.exists():
            raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

        relative_path = filename if not do_return_credentials_file else filename + ".example"
        try:
            return storage.read_json(project_name, relative_path)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404, 
                detail=f"Config file '{filename}' not found in project '{project_name}'"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")

# ==========================================
# 3. Config Updates
# ==========================================
@router.put(
    "/projects/{project_name}/config/{config_type}",
    operation_id="updateProjectConfig",
    tags=["Projects"],
    summary="Update a configuration file",
    description=(
        "**Purpose:** Update a specific config file (config.json, config_iot_devices.json, etc).\n\n"
        "**When to call:** After wizard field changes to persist configuration.\n\n"
        "**Accepts:** Multipart (binary) or JSON (Base64)."
    ),
    responses={
        200: {"description": "Configuration updated"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    }
)
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
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")

@router.post(
    "/projects/{project_name}/import",
    operation_id="importProjectZip",
    tags=["Projects"],
    summary="Import/update project from zip",
    description=(
        "**Purpose:** Upload a complete project zip to update an existing project.\n\n"
        "**Prerequisite:** Project must already exist (create via POST /projects first).\n\n"
        "**Validation:** Zip structure and config schema validation performed."
    ),
    responses={
        200: {"description": "Project imported successfully"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    }
)
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
    if not get_project_storage().exists(project_name):
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
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")


@router.get(
    "/projects/{project_name}/export",
    operation_id="exportProjectZip",
    tags=["Projects"],
    summary="Export project as zip",
    description=(
        "**Purpose:** Download a complete project as a ZIP file.\n\n"
        "**When to call:** For backup, sharing, or migrating projects.\n\n"
        "**Contents:** All configs, hierarchies, state machines, payloads, 3D assets."
    ),
    responses={
        200: {"description": "Project zip file"},
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
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
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")


@router.get(
    "/projects/{project_name}/summary",
    operation_id="getProjectSummary",
    tags=["Projects"],
    summary="Get project dashboard summary",
    description=(
        "**Purpose:** Dashboard overview for Flutter frontend.\n\n"
        "**When to call:** When displaying project cards or details.\n\n"
        "**Returns:** name, description, providers, deployment/validation status."
    ),
    responses={
        200: {"description": "Project summary"},
        404: ERROR_RESPONSES[404],
    }
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
    storage = get_project_storage()
    project_path = storage.context(project_name).project_path
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    summary = {
        "name": project_name,
        "description": None,
        "providers": {},
        "deployment_status": "unknown", # placeholder, implement real logic if needed
        "validation_status": "unknown"
    }

    # 1. Description
    try:
        info = storage.read_json_optional(project_name, CONSTANTS.PROJECT_INFO_FILE)
        if isinstance(info, dict):
            summary["description"] = info.get("description")
    except (ProjectFileAccessDenied, ProjectStorageError, json.JSONDecodeError):
        pass

    # 2. Providers
    try:
        providers = storage.read_json_optional(project_name, CONSTANTS.CONFIG_PROVIDERS_FILE)
        if isinstance(providers, dict):
            summary["providers"] = providers
    except (ProjectFileAccessDenied, ProjectStorageError, json.JSONDecodeError):
        pass

    # 3. Validation Status
    try:
        validate_project_directory(project_path)
        summary["validation_status"] = "valid"
    except Exception as e:
        summary["validation_status"] = "invalid"
        summary["validation_error"] = str(e)
        
    return summary


@router.get(
    "/projects/{project_name}/files",
    operation_id="getProjectFileTree",
    tags=["Projects"],
    summary="Get project file tree",
    description=(
        "**Purpose:** Returns recursive file tree for file browser UI.\n\n"
        "**When to call:** When displaying project contents in explorer view."
    ),
    responses={
        200: {"description": "File tree structure"},
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    }
)
def get_project_files(
    project_name: str = Path(..., description="Project name")
):
    """
    Returns a recursive file tree structure for the project.
    Used for file browsing in the frontend.
    """
    try:
        files = get_project_storage().file_tree(project_name)
        return {"files": files}
    except (FileNotFoundError, ProjectStorageError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")


@router.get(
    "/projects/{project_name}/files/{file_path:path}",
    operation_id="getProjectFile",
    tags=["Projects"],
    summary="Get file content",
    description=(
        "**Purpose:** Read a specific file from a project.\n\n"
        "**When to call:** When opening a file in the editor.\n\n"
        "**Supports:** JSON files return parsed content; others return raw."
    ),
    responses={
        200: {"description": "File content"},
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    }
)
def get_project_file_content_endpoint(
    project_name: str = Path(..., description="Project name"),
    file_path: str = Path(..., description="Relative path to file")
):
    """
    Returns the content of a specific file.
    """
    try:
        content = get_project_storage().file_content(project_name, file_path)
        return content
    except ProjectFileAccessDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    except (FileNotFoundError, ProjectStorageError) as e:
        if "not found" in str(e):
             raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")


@router.delete(
    "/projects/{project_name}",
    operation_id="deleteProject",
    tags=["Projects"],
    summary="Delete a project",
    description=(
        "**Purpose:** Permanently delete a project and all saved versions.\n\n"
        "**Side effect:** If this was the active project, resets to default.\n\n"
        "**Protected:** Cannot delete the 'template' project."
    ),
    responses={
        200: {"description": "Project deleted"},
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    }
)
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
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")


@router.patch(
    "/projects/{project_name}/info",
    operation_id="updateProjectInfo",
    tags=["Projects"],
    summary="Update project metadata",
    description=(
        "**Purpose:** Update project description without re-uploading zip.\n\n"
        "**Body:** `{\"description\": \"New description\"}`"
    ),
    responses={
        200: {"description": "Project info updated"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    }
)
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
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")

@router.put(
    "/projects/{project_name}/state_machines/{provider}",
    operation_id="uploadStateMachine",
    tags=["Projects"],
    summary="Upload state machine definition",
    description=(
        "**Purpose:** Upload AWS Step Function, Azure Logic App, or GCP Workflow.\n\n"
        "**Path param:** provider = aws|azure|google\n\n"
        "**Validation:** Schema validation performed before saving."
    ),
    responses={
        200: {"description": "State machine uploaded"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    }
)
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
        get_project_storage().write_text(
            project_name,
            f"{CONSTANTS.STATE_MACHINES_DIR_NAME}/{target_filename}",
            content_str,
        )
            
        return {"message": f"State machine '{target_filename}' uploaded and verified for provider '{provider_value}'."}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")

@router.put(
    "/projects/{project_name}/simulator/payloads",
    operation_id="uploadSimulatorPayloads",
    tags=["Projects"],
    summary="Upload IoT simulator payloads",
    description=(
        "**Purpose:** Upload payloads.json for the IoT simulator.\n\n"
        "**Validation:** Structure and iotDeviceId validation performed.\n\n"
        "**Location:** Saved to iot_device_simulator/payloads.json"
    ),
    responses={
        200: {"description": "Payloads uploaded"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
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
        get_project_storage().write_text(
            project_name,
            f"{CONSTANTS.IOT_DEVICE_SIMULATOR_DIR_NAME}/{CONSTANTS.PAYLOADS_FILE}",
            content_str,
        )
            
        return {"message": "Payloads uploaded successfully.", "warnings": warnings}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")


# ==========================================
# 4. Project Cleanup (AWS-specific)
# ==========================================
@router.delete(
    "/projects/{project_name}/cleanup/aws-twinmaker",
    operation_id="cleanupAwsTwinmaker",
    tags=["Projects"],
    summary="Force delete AWS TwinMaker workspace",
    description=(
        "**Purpose:** Force delete TwinMaker workspace when Terraform destroy fails.\n\n"
        "**When to call:** When `terraform destroy` fails due to existing entities.\n\n"
        "**Deletion order:** Entities → Component Types → Workspace"
    ),
    responses={
        200: {"description": "TwinMaker workspace deleted"},
        500: ERROR_RESPONSES[500],
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
    # NOTE: validate_project_context removed - blocking production use
    try:
        from src.providers.aws.provider import AWSProvider
        from src.providers.aws.layers.layer_4_twinmaker import force_delete_twinmaker_workspace
        from src.core.config_loader import load_project_config, load_credentials
        from logger import print_stack_trace
        
        project_path = get_project_storage().context(project_name).project_path
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
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")
