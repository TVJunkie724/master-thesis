from fastapi import FastAPI, HTTPException, Query, Depends, UploadFile, File
import json
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import os
import sys 
import traceback

import globals
import aws.globals_aws as globals_aws
import deployers.core_deployer as core_deployer
import deployers.iot_deployer as iot_deployer
import info
import deployers.additional_deployer as hierarchy_deployer
import deployers.event_action_deployer as event_action_deployer
import aws.lambda_manager as lambda_manager
import file_manager
from aws.api_lambda_schemas import LambdaUpdateRequest, LambdaLogsRequest, LambdaInvokeRequest
from util import pretty_json

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from logger import logger, print_stack_trace

# --------- Initialize FastAPI app ----------
app = FastAPI(
    title="Digital Twin Manager API",
    version="1.2",
    description=(
        "API for deploying, destroying, and inspecting Digital Twin environment resources."
        "<h3>🔗 Useful Links</h3>"
        "<h4>📘 Documentation</h4>"
        "<ul><li><a href=\"/documentation/docs-overview.html\" target=\"_blank\"><strong>Documentation Overview</strong></a></li></ul>"
        ),
    openapi_tags=[
        {"name": "Projects", "description": "Endpoints to manage Digital Twin projects (upload, switch, list)."},
        {"name": "Info", "description": "Endpoints to check system status and configurations."},
        {"name": "Deployment", "description": "Endpoints to deploy core and IoT services."},
        {"name": "Destroy", "description": "Endpoints to destroy core and IoT services."},
        {"name": "Status", "description": "Endpoints to inspect the deployment status of all layers and configured resources."},
        {"name": "AWS", "description": "Endpoints to update and fetch logs from Lambda functions."}
    ]
)

app.mount("/documentation", StaticFiles(directory="docs"), name="docs")

# --------- Initialize configuration once ----------
@app.on_event("startup")
def startup_event():
    globals.initialize_all()
    # globals_aws.initialize_aws_clients() # Lazy init is safer or move after project set?
    # globals_aws clients depend on region from config?
    # Actually clients are initialized with empty config first or default?
    # If config changes (project switch), we might need to re-init clients if region changes.
    # But for now, let's stick to existing logic.
    globals_aws.initialize_aws_clients()
    
    logger.info("✅ Globals initialized. API ready.")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("docs/references/favicon.ico")
    
# --------- Root endpoint ----------
@app.get("/", tags=["Info"])
def read_root():
    """
    Check if the API is running.
    """
    return {"status": "API is running", "active_project": globals.CURRENT_PROJECT}

# --------- Project Management ----------

@app.get("/projects", tags=["Projects"])
def list_projects():
    """
    List all available projects.
    """
    try:
        projects = file_manager.list_projects()
        return {"projects": projects, "active_project": globals.CURRENT_PROJECT}
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/projects", tags=["Projects"])
async def create_project(project_name: str = Query(..., description="Name of the new project"), file: UploadFile = File(...)):
    """
    Upload a new project zip file.
    """
    try:
        content = await file.read()
        file_manager.create_project_from_zip(project_name, content)
        return {"message": f"Project '{project_name}' created successfully."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/projects/{project_name}/activate", tags=["Projects"])
def activate_project(project_name: str):
    """
    Switch the active project.
    """
    try:
        globals.set_active_project(project_name)
        # Re-init clients might be needed if region changed? 
        # For now assuming clients handle it or region is same. 
        # But rigorous way: globals_aws.initialize_aws_clients()
        globals_aws.initialize_aws_clients()
        return {"message": f"Active project switched to '{project_name}'."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

from enum import Enum

class ConfigType(str, Enum):
    config = "config"
    iot = "iot"
    events = "events"
    hierarchy = "hierarchy"
    credentials = "credentials"
    providers = "providers"
    optimization = "optimization" # Added optimization

@app.put("/projects/{project_name}/config/{config_type}", tags=["Projects"])
async def update_config(project_name: str, config_type: ConfigType, file: UploadFile = File(...)):
    """
    Update a specific configuration file for a project.
    config_type: Select from the dropdown.
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
    
    # Enum ensures valid value, so specific check is redundant but safe
    filename = config_map[config_type]
    
    try:
        content = await file.read()
        # Parse JSON to validate
        json_content = json.loads(content)
        file_manager.update_config_file(project_name, filename, json_content)
        return {"message": f"Configuration '{filename}' updated for project '{project_name}'."}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON content.")
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


# --------- Validation Endpoints ----------

@app.post("/validate/zip", tags=["Validation"])
async def validate_zip(file: UploadFile = File(...)):
    """
    Validates a project zip file without extracting it.
    
    Checks performed:
    - Zip integrity.
    - Presence of all required configuration files.
    - Path traversal safety (Zip Slip).
    - Content schema validation for all config files.
    
    Returns:
        JSON message indicating validity.
    """
    try:
        content = await file.read()
        file_manager.validate_project_zip(content)
        return {"message": "Project zip is valid and secure."}
    except ValueError as e:
        # Return 400 for validation errors (client side error)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/validate/config/{config_type}", tags=["Validation"])
async def validate_config(config_type: ConfigType, file: UploadFile = File(...)):
    """
    Validates a specific configuration file against its schema.
    
    Args:
        config_type: Select from the dropdown.
        file (UploadFile): The configuration file to validate.
        
    Returns:
        JSON message indicating validity.
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
        content = await file.read()
        content_str = content.decode('utf-8')
        file_manager.validate_config_content(filename, content_str)
        return {"message": f"Configuration '{filename}' is valid."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

class FunctionValidationRequest(BaseModel):
    project_name: str
    function_name: str
    filename: str
    code: str

@app.post("/validate/function", tags=["Validation"])
def validate_function(req: FunctionValidationRequest):
    """
    Validates Python code for a specific function based on its provider.
    
    Prerequisites:
        - The project's 'config_providers.json' must be uploaded to determine the target provider.
        
    Args:
        req (FunctionValidationRequest): JSON body containing project context and code.
        
    Returns:
        JSON message indicating validity.
    """
    try:
        # Determine provider first to check for dependency errors
        provider = file_manager.get_provider_for_function(req.project_name, req.function_name)
        
        # Select appropriate validator
        if provider == "aws":
            file_manager.validate_python_code_aws(req.code)
        elif provider == "azure":
            file_manager.validate_python_code_azure(req.code)
        elif provider == "google":
            file_manager.validate_python_code_google(req.code)
            
        return {"message": f"Function code is valid for provider '{provider}'."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


# --------- Upload Endpoints ----------

@app.post("/projects/{project_name}/upload/zip", tags=["Projects"])
async def update_project_zip(project_name: str, file: UploadFile = File(...)):
    """
    Updates an existing project by overwriting it with a new validated zip file.
    
    Process:
    1. Validates the zip format, integrity, and safety (Zip Slip).
    2. Validates content of all config files inside.
    3. Overwrites existing project files.
    
    Args:
        project_name (str): The project to update.
        file (UploadFile): The zip file.
    """
    # Enforce active project check? Or allow updating inactive projects?
    # Logic in file_manager doesn't strictly depend on active status, only hot-reload does.
    # But for safety, updates usually happen on active or inactive. Let's allow any.
    
    try:
        content = await file.read()
        file_manager.update_project_from_zip(project_name, content)
        return {"message": f"Project '{project_name}' updated successfully from zip."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/projects/{project_name}/functions/{function_name}/file", tags=["Projects"])
async def update_function_file(
    project_name: str, 
    function_name: str, 
    target_filename: str = Query(..., description="Target filename (e.g., lambda_function.py)"), 
    file: UploadFile = File(...)
):
    """
    Uploads and updates a specific code file for a function.
    
    Crucial:
    - This endpoint performs strict provider-specific code validation before saving.
    - 'target_filename' ensures the file is saved with the correct system name, regardless of the uploaded filename.
    
    Args:
        project_name (str): Project context.
        function_name (str): Function directory (e.g., 'persister').
        target_filename (str): Name to save the file as (MUST be provided).
        file (UploadFile): The code file.
    """
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        
        file_manager.update_function_code_file(project_name, function_name, target_filename, content_str)
        return {"message": f"File '{target_filename}' updated for function '{function_name}'."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


def validate_project_context(project_name: str):
    """
    Validates that the requested project name matches the active project.
    If project_name is None, defaults to 'template' path implicitly, 
    but here we enforce explicit match if provided, or default check.
    """
    # If user provided a project name, it MUST match current project.
    # If they didn't provide one, we assume they mean current project?
    # User requirement: "specify the project name to be sure the correct project is deployed"
    # So we should probably require it or match it against default.
    
    # Let's align with CLI: accept param, if no match -> error.
    if project_name != globals.CURRENT_PROJECT:
         raise HTTPException(status_code=409, detail=f"SAFETY ERROR: Requested project '{project_name}' does not match active project '{globals.CURRENT_PROJECT}'. Please switch active project first.")

# --------- Core + IoT Deploy/Destroy ----------
# Core and IoT deployment
@app.post("/deploy", tags=["Deployment"])
def deploy_all(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """
    Deploys the full digital twin environment including IoT devices, processors, and TwinMaker components.
    """
    validate_project_context(project_name)
    try:
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

@app.post("/recreate_updated_events", tags=["Deployment"])
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

@app.post("/destroy", tags=["Destroy"])
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
        event_action_deployer.destroy(provider),
        hierarchy_deployer.destroy(provider),
        iot_deployer.destroy(provider), 
        core_deployer.destroy(provider)
        return {"message": "Core and IoT services destroyed successfully"}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deploy_l1", tags=["Deployment"])
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

@app.post("/destroy_l1", tags=["Destroy"])
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

@app.post("/deploy_l2", tags=["Deployment"])
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

@app.post("/destroy_l2", tags=["Destroy"])
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

@app.post("/deploy_l3", tags=["Deployment"])
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

@app.post("/destroy_l3", tags=["Destroy"])
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

@app.post("/deploy_l4", tags=["Deployment"])
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

@app.post("/destroy_l4", tags=["Destroy"])
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

@app.post("/deploy_l5", tags=["Deployment"])
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

@app.post("/destroy_l5", tags=["Destroy"])
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

# --------- Check/Info Deployment Status ----------
@app.get("/check", tags=["Status"])
def check_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context")
):
    """Runs all checks (L1 to L5) for the specified provider."""
    validate_project_context(project_name)
    try:
        provider = provider.lower()
        info.check(provider)
        hierarchy_deployer.info(provider)
        event_action_deployer.info(provider)
        return {"message": f"System check (all layers) completed for provider '{provider}'. See logs for detailed status."}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Individual layer check endpoints
@app.get("/check_l1", tags=["Status"])
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


@app.get("/check_l2", tags=["Status"])
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


@app.get("/check_l3", tags=["Status"])
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


@app.get("/check_l4", tags=["Status"])
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


@app.get("/check_l5", tags=["Status"])
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


# --------- Info ----------    
@app.get("/info/config", tags=["Info"])
def get_main_config():
    """
    Retrieve the main configuration of the digital twin environment.

    Contains:
    - `digital_twin_name`: Name of the digital twin instance.
    - `layer_3_hot_to_cold_interval_days`: Number of days after which hot data is moved to cold storage.
    - `layer_3_cold_to_archive_interval_days`: Number of days after which cold data is moved to archive storage.

    Example response:
    ```json
    {
      "digital_twin_name": "digital-twin",
      "layer_3_hot_to_cold_interval_days": 30,
      "layer_3_cold_to_archive_interval_days": 90
    }
    ```

    Returns:
        JSON object containing the main configuration parameters of the digital twin.
    """
    try:
        return pretty_json(globals.config)
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/info/config_iot_devices", tags=["Info"])
def get_iot_config():
    """
    Retrieve the configuration for all IoT devices.

    Each IoT device includes:
    - `name`: Unique name of the device.
    - `properties`: List of sensor properties with names and data types.
    - `constProperties` (optional): List of constant properties with names, data types, and fixed values.

    Example response:
    ```json
    [
      {
        "name": "temperature-sensor-1",
        "properties": [{"name": "temperature", "dataType": "DOUBLE"}],
        "constProperties": [{"name": "serial-number", "dataType": "STRING", "value": "1232323"}]
      },
      {
        "name": "pressure-sensor-1",
        "properties": [
          {"name": "pressure", "dataType": "DOUBLE"},
          {"name": "density", "dataType": "DOUBLE"},
          {"name": "hardness", "dataType": "DOUBLE"}
        ]
      }
    ]
    ```

    Returns:
        JSON array of IoT device configurations.
    """
    try:
        return pretty_json(globals.config_iot_devices)
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/info/config_providers", tags=["Info"])
def get_providers_config():
    """
    Retrieve the cloud provider configuration for each deployment layer.

    Example response:
    ```json
    {
      "layer_1_provider": "aws",
      "layer_2_provider": "aws",
      "layer_3_hot_provider": "aws",
      "layer_3_cold_provider": "aws",
      "layer_3_archive_provider": "aws",
      "layer_4_provider": "aws",
      "layer_5_provider": "aws"
    }
    ```

    Returns:
        JSON object where each key represents a layer in the digital twin architecture and the value specifies the cloud provider used for that layer.
    """
    try:
        return pretty_json(globals.config_providers)
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

# @app.get("/info/config_credentials", tags=["Info"])
# def get_credentials_config():
#     """
#     Retrieve the cloud credentials configuration.

#     Contains:
#     - `aws`: AWS credentials with fields:
#         - `aws_access_key_id`: AWS access key ID.
#         - `aws_secret_access_key`: AWS secret access key.
#         - `aws_region`: Default AWS region.
#     - `azure`: Azure credentials with fields:
#         - `azure_subscription_id`: Azure subscription ID.
#         - `azure_client_id`: Azure client ID.
#         - `azure_client_secret`: Azure client secret.
#         - `azure_tenant_id`: Azure tenant ID.
#         - `azure_region`: Default Azure region.
#     - `google`: Google Cloud credentials with fields:
#         - `gcp_project_id`: Google Cloud project ID.
#         - `gcp_credentials_file`: Path to the Google Cloud credentials JSON file.
#         - `gcp_region`: Default Google Cloud region.

#     Returns:
#         JSON object containing cloud credentials used for API calls.
#     """
#     try:
#         return pretty_json(globals.config_credentials)
#     except Exception as e:
#         print_stack_trace()
#         logger.error(str(e))
#         raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/info/config_hierarchy", tags=["Info"])
def get_config_hierarchy():
    """
    Retrieve the hierarchical entity configuration of the digital twin environment.

    This configuration defines how entities, machines, and IoT components are organized within the digital twin.

    Example structure:
    ```json
    [
      {
        "type": "entity",
        "id": "room-1",
        "children": [
          {
            "type": "entity",
            "id": "machine-1",
            "children": [
              {
                "type": "component",
                "name": "temperature-sensor-1",
                "componentTypeId": "digital-twin-temperature-sensor-1"
              }
            ]
          },
          {
            "type": "component",
            "name": "temperature-sensor-2",
            "iotDeviceId": "temperature-sensor-2"
          }
        ]
      }
    ]
    ```

    Returns:
        JSON array defining the full entity and component hierarchy of the digital twin.
    """
    try:
        with open("config_hierarchy.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return pretty_json(data)
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/info/config_events", tags=["Info"])
def get_config_events():
    """
    Retrieve the event-driven automation configuration of the digital twin environment.

    Each event defines a condition to monitor (e.g., sensor value thresholds) and an action to execute when the condition is met.

    Example structure:
    ```json
    [
      {
        "condition": "testEntityId.temperature-sensor-1.temperature == DOUBLE(30)",
        "action": {
          "type": "lambda",
          "functionName": "high-temperature-callback",
          "autoDeploy": true
        }
      }
    ]
    ```

    Returns:
        JSON array defining event conditions and corresponding automated actions.
    """
    try:
        with open("config_events.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return pretty_json(data)
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

# --------- Lambda Management ----------
@app.post("/lambda_update", tags=["AWS"])
def lambda_update(req: LambdaUpdateRequest):
    """
    Update an AWS Lambda function with the latest local code.

    Behavior:
    - If `local_function_name` is "default-processor", updates all processor Lambdas for each IoT device.
    - Otherwise, updates a single Lambda function by name.
    - Optionally updates the Lambda environment variables if `environment` is provided.

    Parameters:
    - local_function_name: Name of the local Lambda function to update.
    - environment: JSON string defining environment variables to set (optional).

    Returns:
        JSON message confirming the update.
    """
    try:
        if req.environment:
            lambda_manager.update_function(req.local_function_name, req.environment)
        else:
            lambda_manager.update_function(req.local_function_name)
        return {"message": f"Lambda {req.local_function_name} updated successfully"}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/lambda_logs", tags=["AWS"])
def get_lambda_logs(req: LambdaLogsRequest = Depends()) -> List[str]:
    """
    Fetch the most recent log messages from a specified Lambda function.

    Parameters:
    - local_function_name: Name of the local Lambda function to fetch logs from.
    - n: Number of log lines to return (default 10).
    - filter_system_logs: Whether to exclude AWS system log messages (default True).

    Returns:
        List of log messages as strings.
    """
    try:
        logs = lambda_manager.fetch_logs(req.local_function_name, n=req.n, filter_system_logs=req.filter_system_logs)
        return logs
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/lambda_invoke", tags=["AWS"])
def lambda_invoke(req: LambdaInvokeRequest):
    """
    Invokes a lambda function.
    """
    try:
        lambda_manager.invoke_function(req.local_function_name, req.payload, req.sync)
        return {"message": f"Lambda {req.local_function_name} invoked successfully"}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
