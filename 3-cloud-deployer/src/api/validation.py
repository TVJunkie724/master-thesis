# TODO(refactoring): This file is 1377 lines - candidate for refactoring.
# Consider splitting into domain-specific validation modules:
# - zip_validation.py - Zip validation endpoints
# - config_validation.py - Config file validation
# - function_validation.py - Function code validation
# - hierarchy_validation.py - L4 hierarchy validation
# See: monolith_reduction_patterns KI for patterns.

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
import src.validator as validator
from api.dependencies import ConfigType, ProviderEnum
from api.error_models import ERROR_RESPONSES
from logger import logger
import json

router = APIRouter()

class FunctionCodeValidationRequest(BaseModel):
    provider: ProviderEnum
    code: str

# ==========================================
# 1. Zip Validation
# ==========================================
@router.post(
    "/validate/zip",
    operation_id="validateProjectZip",
    tags=["Validation"],
    summary="Validate project zip file",
    description=(
        "**Purpose:** Validates a project zip file without extracting, checking structure and security.\\n\\n"
        "**When to call:** Before uploading a project to verify it meets all requirements.\\n\\n"
        "**Checks performed:** Zip integrity, Zip Slip path traversal, required files, schema validation."
    ),
    responses={
        200: {"description": "Project zip is valid"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_zip(file: UploadFile = File(..., description="Project zip file to validate")):
    """
    Validates a project zip file without extracting it.
    
    **Minimal valid project structure:**
    ```
    project.zip
    ├── config.json                    (required)
    ├── config_iot_devices.json        (required)
    ├── config_events.json             (required)
    ├── config_providers.json          (required)
    ├── config_optimization.json       (required)
    ├── config_credentials.json        (required)
    │
    ├── twin_hierarchy/                (required)
    │   ├── aws_hierarchy.json         (required if layer_4_provider=aws)
    │   └── azure_hierarchy.json       (required if layer_4_provider=azure)
    │
    ├── state_machines/                (optional - required if triggerNotificationWorkflow=true)
    │   ├── aws_step_function.json     (if layer_2_provider=aws)
    │   ├── azure_logic_app.json       (if layer_2_provider=azure)
    │   └── google_cloud_workflow.yaml (if layer_2_provider=google)
    │
    ├── lambda_functions/              (if layer_2_provider=aws)
    │   ├── processors/
    │   │   └── default_processor/
    │   │       └── process.py
    │   ├── event_actions/             (optional - required if useEventChecking=true)
    │   │   └── <action_name>/
    │   │       └── lambda_function.py
    │   └── event-feedback/            (optional - required if returnFeedbackToDevice=true)
    │       └── lambda_function.py
    │
    ├── azure_functions/               (if layer_2_provider=azure)
    │   ├── processors/
    │   │   └── default_processor/
    │   │       └── function_app.py
    │   └── event_actions/             (optional - required if useEventChecking=true)
    │       └── <action_name>/
    │           └── function_app.py
    │
    ├── cloud_functions/               (if layer_2_provider=google)
    │   ├── processors/
    │   │   └── default_processor/
    │   │       └── main.py
    │   └── event_actions/             (optional - required if useEventChecking=true)
    │       └── <action_name>/
    │           └── main.py
    │
    └── iot_device_simulator/          (optional - for testing IoT data flow)
        └── payloads.json
    ```
    
    **Dependency triggers (in config_optimization.json):**
    - `useEventChecking=true` → requires event_actions/ folder
    - `returnFeedbackToDevice=true` → requires event-feedback/ folder (AWS only)
    - `triggerNotificationWorkflow=true` → requires state_machines/ folder
    
    **Checks performed:**
    - Zip integrity and path traversal safety (Zip Slip)
    - Presence of all required configuration files
    - Content schema validation for all config files
    - Dependency checks based on optimization flags
    """
    try:
        content = await file.read()
        validator.validate_project_zip(content)
        return {"message": "Project zip is valid and secure."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")

# ==========================================
# 2. Config Validation
# ==========================================
@router.post(
    "/validate/config/{config_type}",
    operation_id="validateConfigFile",
    tags=["Validation"],
    summary="Validate configuration file",
    description=(
        "**Purpose:** Validates a specific configuration file against its JSON schema.\n\n"
        "**When to call:** To validate individual config files (config.json, config_iot_devices.json, etc).\n\n"
        "**Path param:** config_type = config|iot|events|providers|optimization|credentials|aws_hierarchy|azure_hierarchy"
    ),
    responses={
        200: {"description": "Configuration is valid"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_config(
    config_type: ConfigType,
    file: UploadFile = File(..., description="Configuration file to validate")
):
    """
    Validates a specific configuration file against its schema.
    
    **Minimal examples per config_type:**
    
    `config`:
    ```json
    {"digital_twin_name": "my-twin", "hot_storage_size_in_days": 7, "cold_storage_size_in_days": 30, "mode": "production"}
    ```
    
    `iot`:
    ```json
    [{"id": "device-1", "properties": ["temperature", "humidity"]}]
    ```
    
    `events`:
    ```json
    [{"condition": "temperature > 30", "action": {"type": "lambda", "functionName": "alert-handler"}}]
    ```
    
    `providers`:
    ```json
    {"layer_1_provider": "aws", "layer_2_provider": "aws", "layer_3_hot_provider": "aws", "layer_4_provider": "aws"}
    ```
    
    `optimization`:
    ```json
    {"result": {"inputParamsUsed": {"useEventChecking": false, "returnFeedbackToDevice": false, "triggerNotificationWorkflow": false}}}
    ```
    
    `credentials` (include sections for each provider you use):
    ```json
    {
      "aws": {"aws_access_key_id": "...", "aws_secret_access_key": "...", "aws_region": "eu-central-1"},
      "azure": {"azure_subscription_id": "...", "azure_tenant_id": "...", "azure_client_id": "...", "azure_client_secret": "...", "azure_region": "italynorth", "azure_region_iothub": "westeurope", "azure_region_digital_twin": "westeurope"},
      "gcp": {"gcp_project_id": "...", "gcp_credentials_file": "google_credentials.json", "gcp_region": "europe-west1"}
    }
    ```
    
    `aws_hierarchy` (for layer_4_provider=aws):
    ```json
    [{"type": "entity", "id": "root", "children": [{"type": "component", "name": "sensor", "iotDeviceId": "device-1"}]}]
    ```
    
    `azure_hierarchy` (for layer_4_provider=azure):
    ```json
    {"header": {"fileVersion": "1.0.0"}, "models": [{"@id": "dtmi:example:Room;1", "@type": "Interface", "@context": "dtmi:dtdl:context;2"}], "twins": [], "relationships": []}
    ```
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
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Use provider-specific hierarchy validators
        if config_type == ConfigType.aws_hierarchy:
            validator.validate_aws_hierarchy_content(content_str)
        elif config_type == ConfigType.azure_hierarchy:
            validator.validate_azure_hierarchy_content(content_str)
        else:
            validator.validate_config_content(filename, content_str)
        
        return {"message": f"Configuration '{filename}' is valid."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Config validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")

# ==========================================
# 3. State Machine Validation
# ==========================================
@router.post(
    "/validate/state-machine",
    operation_id="validateStateMachine",
    tags=["Validation"],
    summary="Validate state machine definition",
    description=(
        "**Purpose:** Validates state machine definitions for workflow orchestration.\n\n"
        "**When to call:** To validate AWS Step Functions, Azure Logic Apps, or GCP Cloud Workflows.\n\n"
        "**Query param:** provider=aws|azure|google determines which schema to validate against."
    ),
    responses={
        200: {"description": "State machine is valid"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_state_machine(
    provider: ProviderEnum = Query(..., description="Target cloud provider"),
    file: UploadFile = File(..., description="State machine definition file (JSON)")
):
    """
    Validates a state machine definition file against the provider's schema.
    
    **File location in project:** `state_machines/<provider_file>.json`
    
    **Minimal examples per provider:**
    
    `aws` → `state_machines/aws_step_function.json`:
    ```json
    {"StartAt": "Init", "States": {"Init": {"Type": "Pass", "End": true}}}
    ```
    
    `azure` → `state_machines/azure_logic_app.json`:
    ```json
    {"definition": {"$schema": "...", "triggers": {}, "actions": {}}}
    ```
    
    `google` → `state_machines/google_cloud_workflow.yaml`:
    ```yaml
    main:
      steps:
        - init:
            assign:
              - result: "ok"
    ```
    """
    filename_map = {
        "aws": "aws_step_function.json",
        "azure": "azure_logic_app.json",
        "google": "google_cloud_workflow.yaml"
    }
    
    target_filename = filename_map[provider]
    
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        validator.validate_state_machine_content(target_filename, content_str)
        return {"message": f"State machine definition is valid for {provider.value}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"State machine validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")

# ==========================================
# 4. Function Code Validation
# ==========================================
@router.post(
    "/validate/function-code",
    operation_id="validateFunctionCode",
    tags=["Validation"],
    summary="Validate function code syntax",
    description=(
        "**Purpose:** Validates Python code syntax and entry point signatures for serverless functions.\n\n"
        "**When to call:** To validate processor or event action code before deployment.\n\n"
        "**Checks:** Python syntax (ast.parse), required function signature per provider."
    ),
    responses={
        200: {"description": "Code is valid"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_function_code(
    provider: ProviderEnum = Query(..., description="Target cloud provider"),
    file: UploadFile = File(..., description="Python file to validate")
):
    """
    Validates Python code for a specific provider.
    
    **Checks performed:**
    1. **Python syntax** - File must be valid, compilable Python (uses `ast.parse`)
    2. **Entry point** - Must have the required function signature for the provider
    
    **File locations per provider:**
    - `aws` → `lambda_functions/processors/<name>/process.py` or `lambda_function.py`
    - `azure` → `azure_functions/processors/<name>/function_app.py`
    - `google` → `cloud_functions/processors/<name>/main.py`
    
    **Minimal examples per provider:**
    
    `aws` (Lambda - requires `lambda_handler(event, context)`):
    ```python
    def lambda_handler(event, context):
        return {"statusCode": 200, "body": "OK"}
    ```
    
    `azure` (Function - requires `main(req)`):
    ```python
    import azure.functions as func
    def main(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse("OK")
    ```
    
    `google` (Cloud Function - any function name):
    ```python
    def hello_world(request):
        return "OK"
    ```
    
    **Note:** For processor files (process.py), use `/validate/processor` instead.
    """
    try:
        content = await file.read()
        code = content.decode('utf-8')
        
        if provider == ProviderEnum.aws:
            validator.validate_python_code_aws(code)
        elif provider == ProviderEnum.azure:
            validator.validate_python_code_azure(code)
        elif provider == ProviderEnum.google:
            validator.validate_python_code_google(code)
            
        return {"message": f"Code is valid for {provider.value}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Code validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")

# ==========================================
# 4b. Processor Code Validation - DEPRECATED
# ==========================================
# This endpoint validated process.py files which are no longer used.
# User functions are now standalone serverless functions validated by /validate/function-code
# 
# @router.post(
#     "/validate/processor",
#     tags=["Validation"],
#     summary="Validate processor code",
#     responses={
#         200: {"description": "Processor code is valid"},
#         400: {"description": "Missing process(event) function"}
#     }
# )
# async def validate_processor_code(
#     provider: ProviderEnum = Query(..., description="Target cloud provider"),
#     file: UploadFile = File(..., description="Processor Python file (process.py) to validate")
# ):
#     """DEPRECATED - process.py pattern no longer used"""
#     pass

# ==========================================
# 5. Simulator Payload Validation
# ==========================================
@router.post(
    "/validate/simulator/payloads",
    operation_id="validateSimulatorPayloads",
    tags=["Validation"],
    summary="Validate simulator payloads",
    description=(
        "**Purpose:** Validates the structure of a payloads.json file for IoT simulation.\n\n"
        "**When to call:** Before running the IoT simulator to verify payload format.\n\n"
        "**Required fields:** Each payload must have an iotDeviceId matching config_iot_devices.json."
    ),
    responses={
        200: {"description": "Payloads structure is valid"},
        500: ERROR_RESPONSES[500],
    }
)
async def validate_simulator_payloads(
    file: UploadFile = File(..., description="payloads.json file to validate")
):
    """
    Validates the structure of a payloads.json file.
    
    **Minimal example:**
    ```json
    [
        {
            "iotDeviceId": "device-1",
            "temperature": 25.5,
            "humidity": 60
        },
        {
            "iotDeviceId": "device-2",
            "pressure": 1013.25
        }
    ]
    ```
    
    **Required fields per payload:**
    - `iotDeviceId`: String identifier matching a device in config_iot_devices.json
    """
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        
        is_valid, errors, warnings = validator.validate_simulator_payloads(content_str)
        
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }
    except Exception as e:
        logger.error(f"Payload validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")

@router.post(
    "/validate/payloads-with-devices",
    operation_id="validatePayloadsWithDevices",
    tags=["Validation"],
    summary="Cross-validate payloads against devices",
    description=(
        "**Purpose:** Validates that all iotDeviceId values in payloads.json exist in config_iot_devices.json.\n\n"
        "**When to call:** To ensure payload device IDs match configured devices before simulation.\n\n"
        "**Response:** Returns valid=true if all device IDs match, or list of mismatches."
    ),
    responses={
        200: {"description": "All payload device IDs exist in devices config"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_payloads_with_devices(
    payloads_file: UploadFile = File(..., description="payloads.json file"),
    devices_file: UploadFile = File(..., description="config_iot_devices.json file")
):
    """
    Validates payloads.json against config_iot_devices.json.
    
    **payloads.json example:**
    ```json
    [{"iotDeviceId": "device-1", "temperature": 25.5}]
    ```
    
    **config_iot_devices.json example:**
    ```json
    [{"id": "device-1", "properties": ["temperature", "humidity"]}]
    ```
    
    **Checks:**
    - All `iotDeviceId` values in payloads exist as `id` in devices config
    - Payload structure is valid
    """
    try:
        payloads_content = await payloads_file.read()
        devices_content = await devices_file.read()
        
        payloads_str = payloads_content.decode('utf-8')
        devices_str = devices_content.decode('utf-8')
        
        # Parse both files
        try:
            payloads = json.loads(payloads_str)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in payloads file: {e}")
        
        try:
            devices = json.loads(devices_str)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in devices file: {e}")
        
        errors = []
        warnings = []
        
        # Get valid device IDs from config
        if not isinstance(devices, list):
            raise HTTPException(status_code=400, detail="config_iot_devices.json must be a JSON array")
        
        valid_device_ids = {d.get("id") for d in devices if isinstance(d, dict) and "id" in d}
        
        if not isinstance(payloads, list):
            raise HTTPException(status_code=400, detail="payloads.json must be a JSON array")
        
        # Check each payload
        for idx, payload in enumerate(payloads):
            if not isinstance(payload, dict):
                errors.append(f"Item at index {idx} is not a JSON object")
                continue
            
            device_id = payload.get("iotDeviceId")
            if not device_id:
                errors.append(f"Item at index {idx} missing required 'iotDeviceId'")
            elif device_id not in valid_device_ids:
                errors.append(f"Item at index {idx}: iotDeviceId '{device_id}' not found in config_iot_devices.json")
        
        if not payloads:
            warnings.append("Payloads list is empty")
        
        is_valid = len(errors) == 0
        
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "devices_found": list(valid_device_ids)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cross-validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")

# ==========================================
# 7. L4 Hierarchy Validation
# ==========================================
@router.post(
    "/validate/hierarchy",
    operation_id="validateHierarchy",
    tags=["Validation"],
    summary="Validate hierarchy JSON for L4 provider",
    description=(
        "**Purpose:** Validates hierarchy JSON for L4 Digital Twins (AWS IoT TwinMaker or Azure ADT).\n\n"
        "**When to call:** To validate aws_hierarchy.json or azure_hierarchy.json before deployment.\n\n"
        "**AWS format:** Array of entity definitions with type, id, and optional children.\n"
        "**Azure format:** Object with header, models, twins, and relationships arrays."
    ),
    responses={
        200: {"description": "Hierarchy is valid"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_hierarchy(
    provider: ProviderEnum = Query(..., description="L4 provider (aws or azure)"),
    file: UploadFile = File(..., description="Hierarchy JSON file")
):
    """
    Validates hierarchy JSON for the specified L4 provider.
    
    **AWS** (`aws_hierarchy.json`):
    ```json
    [{"type": "entity", "id": "root", "children": [...]}]
    ```
    
    **Azure** (`azure_hierarchy.json`):
    ```json
    {"header": {...}, "models": [...], "twins": [...], "relationships": [...]}
    ```
    """
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        
        if provider == ProviderEnum.aws:
            validator.validate_aws_hierarchy_content(content_str)
        elif provider == ProviderEnum.azure:
            validator.validate_azure_hierarchy_content(content_str)
        else:
            raise HTTPException(status_code=400, detail=f"Provider '{provider}' is not valid for L4. Use 'aws' or 'azure'.")
        
        return {"message": f"Hierarchy for {provider} is valid."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hierarchy validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")

# ==========================================
# 8. L4 User Config Validation
# ==========================================
@router.post(
    "/validate/user-config",
    operation_id="validateUserConfig",
    tags=["Validation"],
    summary="Validate config_user.json for platform user",
    description=(
        "**Purpose:** Validates config_user.json for L5 platform user provisioning (Grafana admin).\n\n"
        "**When to call:** To validate platform user configuration before L5 deployment.\n\n"
        "**Azure requirement:** Email must use verified domain (*.onmicrosoft.com)."
    ),
    responses={
        200: {"description": "User config is valid"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_user_config(
    provider: ProviderEnum = Query(..., description="L4 provider (aws or azure)"),
    file: UploadFile = File(..., description="config_user.json file")
):
    """
    Validates config_user.json for platform user provisioning.
    
    **Required format:**
    ```json
    {
        "admin_email": "user@yourtenant.onmicrosoft.com",
        "admin_first_name": "Platform",
        "admin_last_name": "Admin"
    }
    ```
    
    **Validation:**
    - Email format validation
    - Azure: requires verified domain (*.onmicrosoft.com)
    - Empty email allowed (skips user provisioning)
    """
    import re
    
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        
        try:
            user_config = json.loads(content_str)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
        
        if not isinstance(user_config, dict):
            raise HTTPException(status_code=400, detail="config_user.json must be a JSON object")
        
        admin_email = user_config.get("admin_email", "")
        
        # Allow empty email (skips user provisioning)
        if not admin_email:
            return {"message": "User config valid. Empty email - user provisioning will be skipped."}
        
        # Email format validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, admin_email):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid email format: '{admin_email}'. Please provide a valid email address."
            )
        
        # Azure-specific: Require verified domain
        if provider == ProviderEnum.azure:
            email_domain = admin_email.split("@")[1] if "@" in admin_email else ""
            
            if not email_domain.endswith(".onmicrosoft.com"):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Azure platform user email must use your tenant's verified domain.\n"
                        f"  Provided: {admin_email}\n"
                        f"  Domain '{email_domain}' is likely not verified in your Azure tenant.\n\n"
                        f"Options:\n"
                        f"  1. Use your tenant domain: username@YOUR_TENANT.onmicrosoft.com\n"
                        f"  2. Use an empty string to skip user provisioning\n"
                        f"  3. If '{email_domain}' IS verified, proceed with deployment."
                    )
                )
        
        return {"message": f"User configuration is valid. Platform user: {admin_email}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User config validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")

# ==========================================
# 9. L4 Scene Config Validation
# ==========================================
@router.post(
    "/validate/scene-config",
    operation_id="validateSceneConfig",
    tags=["Validation"],
    summary="Validate scene configuration with hierarchy cross-reference",
    description=(
        "**Purpose:** Validates scene configuration for L4 3D visualization.\n\n"
        "**When to call:** To validate scene.json (AWS) or 3DScenesConfiguration.json (Azure).\n\n"
        "**Azure:** Validates JSON schema and cross-references primaryTwinID against hierarchy twins."
    ),
    responses={
        200: {"description": "Scene config is valid"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_scene_config(
    provider: ProviderEnum = Query(..., description="L4 provider (aws or azure)"),
    scene_file: UploadFile = File(..., description="Scene config file (scene.json or 3DScenesConfiguration.json)"),
    hierarchy_file: UploadFile = File(None, description="Hierarchy JSON for cross-reference (optional)")
):
    """
    Validates scene configuration for 3D visualization.
    
    **AWS** (`scene.json`):
    Basic JSON structure validation.
    
    **Azure** (`3DScenesConfiguration.json`):
    - Valid JSON with $schema and configuration
    - Allows {{STORAGE_URL}} placeholders in asset URLs
    - Cross-references primaryTwinID against hierarchy twins
    """
    try:
        scene_content = await scene_file.read()
        scene_str = scene_content.decode('utf-8')
        
        hierarchy_str = None
        if hierarchy_file:
            hierarchy_content = await hierarchy_file.read()
            hierarchy_str = hierarchy_content.decode('utf-8')
        
        # Delegate to validator function
        validator.validate_scene_config_content(provider.value, scene_str, hierarchy_str)
        
        return {"message": f"Scene configuration is valid."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scene config validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")


# ==========================================
# 10. Zip Extraction for Flutter Wizard
# ==========================================
@router.post(
    "/validate/zip/extract",
    operation_id="extractProjectZip",
    tags=["Validation"],
    summary="Extract and validate project zip for wizard auto-population",
    description=(
        "**Purpose:** Extracts and validates project zip for Flutter wizard auto-population.\n\n"
        "**When to call:** From Step 3 wizard to import existing project files.\n\n"
        "**Mode A:** Pass validation_context to skip credentials (wizard step 3).\n"
        "**Mode B:** Full import with include_credentials=true."
    ),
    responses={
        200: {"description": "Extraction successful with file contents"},
        400: ERROR_RESPONSES[400],
        413: {"description": "File too large (max 100MB)"},
        422: ERROR_RESPONSES[422],
        500: ERROR_RESPONSES[500],
    }
)
async def extract_zip(
    file: UploadFile = File(..., description="Project zip file to extract"),
    validation_context: str = Query(None, description="JSON ValidationContext for Mode A"),
    include_credentials: bool = Query(False, description="Include credentials in response (Mode B only)")
):
    """
    Extract project zip contents for Flutter wizard auto-population.
    
    **Mode A (Wizard Step 3)**: Pass validation_context with l2_provider etc.
    Credentials are NOT returned unless include_credentials=true.
    
    **Mode B (Full Import)**: No context, include_credentials=true.
    All files extracted and validated.
    
    **Returns**: JSON with all extracted file contents, including:
    - Config files (events, devices, payloads, etc.)
    - Function code (processors, event actions, feedback)
    - Scene assets (GLB as base64)
    - Validation errors (aggregated)
    """
    import zipfile
    import io
    import base64
    import re
    import os
    from src.validation.core import (
        run_all_checks_aggregated,
        ValidationContext as CoreValidationContext,
        PROVIDER_USER_CODE_FILES,
        PROVIDER_FUNCTION_DIRS,
    )
    from src.validation.accessors import ZipFileAccessor
    from src.api.models.zip_extraction import (
        ZipExtractionResponse,
        FileExtractionResult,
        FunctionExtractionResult,
        AssetExtractionResult,
    )
    
    try:
        content = await file.read()
        
        # File size limit: 100MB
        MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100 MB
        if len(content) > MAX_ZIP_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum allowed size is 100MB, got {len(content) / (1024*1024):.1f}MB"
            )
        
        # Open ZIP file
        try:
            zf = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid or corrupted ZIP file")
        
        # Security: Check for Zip Slip
        for name in zf.namelist():
            if name.startswith('/') or '..' in name:
                raise HTTPException(status_code=400, detail=f"Unsafe path in ZIP: {name}")
        
        accessor = ZipFileAccessor(zf)
        project_root = accessor.get_project_root()
        
        # Parse validation context if provided (Mode A)
        ctx = CoreValidationContext()
        if validation_context:
            try:
                ctx_data = json.loads(validation_context)
                ctx.skip_credentials = ctx_data.get("skip_credentials", True)
                ctx.skip_config_files = ctx_data.get("skip_config_files", [])
                # Store provider info for extraction
                l2_provider = ctx_data.get("l2_provider", "")
                l4_provider = ctx_data.get("l4_provider", "")
            except json.JSONDecodeError:
                raise HTTPException(status_code=422, detail="Invalid JSON in validation_context")
        else:
            l2_provider = ""
            l4_provider = ""
            ctx.skip_credentials = not include_credentials
        
        # Run aggregated validation
        validation_result = run_all_checks_aggregated(accessor, ctx)
        
        # Extract config files
        config_files = {}
        config_file_names = [
            "config.json", "config_events.json", "config_iot_devices.json",
            "config_providers.json", "config_optimization.json", "config_user.json",
            "iot_device_simulator/payloads.json",
        ]
        
        # Add hierarchy files based on L4 provider
        if l4_provider in ["aws", "azure"] or not l4_provider:
            config_file_names.extend([
                "twin_hierarchy/aws_hierarchy.json",
                "twin_hierarchy/azure_hierarchy.json",
            ])
        
        # Add scene config files (provider-specific subdirectories)
        # AWS uses scene_assets/aws/scene.json, Azure uses scene_assets/azure/3DScenesConfiguration.json
        config_file_names.extend([
            "scene_assets/aws/scene.json",
            "scene_assets/azure/3DScenesConfiguration.json",
        ])
        
        # Add state machine files (all provider formats)
        config_file_names.extend([
            "state_machines/aws_step_function.json",
            "state_machines/azure_logic_app.json",
            "state_machines/google_cloud_workflow.yaml",
        ])
        
        for filename in config_file_names:
            path = project_root + filename
            if accessor.file_exists(path):
                try:
                    content_str = accessor.read_text(path)
                    config_files[filename] = FileExtractionResult(
                        exists=True,
                        content=content_str,
                        is_binary=False
                    )
                except Exception as e:
                    config_files[filename] = FileExtractionResult(
                        exists=True,
                        content=None,
                        validation_error=str(e)
                    )
            else:
                config_files[filename] = FileExtractionResult(exists=False)
        
        # Skip credentials unless explicitly requested
        if include_credentials and accessor.file_exists(project_root + "config_credentials.json"):
            try:
                creds = accessor.read_text(project_root + "config_credentials.json")
                config_files["config_credentials.json"] = FileExtractionResult(
                    exists=True,
                    content=creds,
                    is_binary=False
                )
            except Exception as e:
                config_files["config_credentials.json"] = FileExtractionResult(
                    exists=True,
                    validation_error=str(e)
                )
        
        # Extract function code
        functions = FunctionExtractionResult()
        
        # Determine which provider directories to scan
        providers_to_scan = [l2_provider] if l2_provider else ["aws", "azure", "gcp"]
        
        for provider in providers_to_scan:
            func_dir = PROVIDER_FUNCTION_DIRS.get(provider.lower(), "")
            user_file = PROVIDER_USER_CODE_FILES.get(provider.lower(), "main.py")
            if not func_dir:
                continue
            
            # Scan for processors
            processor_prefix = f"{project_root}{func_dir}/processors/"
            for filepath in accessor.list_files():
                if filepath.startswith(processor_prefix) and filepath.endswith(user_file):
                    # Extract device ID from path
                    rel_path = filepath[len(processor_prefix):]
                    parts = rel_path.split('/')
                    if len(parts) >= 2:
                        device_id = parts[0]
                        try:
                            code = accessor.read_text(filepath)
                            functions.processors[device_id] = FileExtractionResult(
                                exists=True,
                                content=code,
                                is_binary=False
                            )
                        except Exception as e:
                            functions.processors[device_id] = FileExtractionResult(
                                exists=True,
                                validation_error=str(e)
                            )
            
            # Scan for event actions
            action_prefix = f"{project_root}{func_dir}/event_actions/"
            for filepath in accessor.list_files():
                if filepath.startswith(action_prefix) and filepath.endswith(user_file):
                    rel_path = filepath[len(action_prefix):]
                    parts = rel_path.split('/')
                    if len(parts) >= 2:
                        action_name = parts[0]
                        try:
                            code = accessor.read_text(filepath)
                            functions.event_actions[action_name] = FileExtractionResult(
                                exists=True,
                                content=code,
                                is_binary=False
                            )
                        except Exception as e:
                            functions.event_actions[action_name] = FileExtractionResult(
                                exists=True,
                                validation_error=str(e)
                            )
            
            # Scan for event feedback (only if not already extracted from preferred provider)
            if functions.event_feedback is None:
                feedback_path = f"{project_root}{func_dir}/event-feedback/{user_file}"
                if accessor.file_exists(feedback_path):
                    try:
                        code = accessor.read_text(feedback_path)
                        functions.event_feedback = FileExtractionResult(
                            exists=True,
                            content=code,
                            is_binary=False
                        )
                    except Exception as e:
                        functions.event_feedback = FileExtractionResult(
                            exists=True,
                            validation_error=str(e)
                        )
        
        # Extract scene GLB (binary, base64 encoded)
        # Check provider-specific paths: scene_assets/aws/scene.glb or scene_assets/azure/scene.glb
        assets = AssetExtractionResult()
        glb_paths = [
            project_root + "scene_assets/aws/scene.glb",
            project_root + "scene_assets/azure/scene.glb",
            project_root + "scene_assets/scene.glb",  # Fallback for flat structure
        ]
        for glb_path in glb_paths:
            if accessor.file_exists(glb_path):
                try:
                    glb_bytes = accessor.read_binary(glb_path)
                    glb_b64 = base64.b64encode(glb_bytes).decode('ascii')
                    assets.scene_glb = FileExtractionResult(
                        exists=True,
                        content=glb_b64,
                        is_binary=True
                    )
                    break  # Found it, stop searching
                except Exception as e:
                    assets.scene_glb = FileExtractionResult(
                        exists=True,
                        validation_error=str(e)
                    )
                    break
        
        return ZipExtractionResponse(
            success=validation_result.is_valid,
            files=config_files,
            functions=functions,
            assets=assets,
            validation_errors=validation_result.errors,
            warnings=validation_result.warnings
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Zip extraction error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal extraction error: {str(e)}")


# ==========================================
# 11. Complete Deployer Config Validation
# ==========================================

class ValidationError(BaseModel):
    """Structured validation error with error code for localization."""
    code: str
    field: str
    message: str


class DeployerCompleteValidation(BaseModel):
    """Input model for complete deployer config validation."""
    # Core configs
    deployer_digital_twin_name: str | None = None
    config_events: str | None = None          # JSON content
    config_iot_devices: str | None = None     # JSON content
    payloads: str | None = None               # JSON content
    
    # Functions
    processors: dict[str, str] | None = None  # {device_id: code}
    event_feedback: str | None = None         # code
    event_actions: dict[str, str] | None = None  # {name: code}
    
    # L4 assets
    hierarchy: str | None = None              # JSON content
    scene_config: str | None = None           # JSON content
    scene_glb_uploaded: bool = False
    
    # L2 state machine
    state_machine: str | None = None          # JSON/YAML content
    
    # L5 user config
    user_config: str | None = None            # JSON content
    
    # Context from optimizer
    optimizer_params: dict | None = None
    cheapest_path: list | dict | None = None  # Either ['L1_GCP', 'L2_AWS', ...] or {L1: "aws", ...}


class DeployerValidationResponse(BaseModel):
    """Validation response with all errors."""
    valid: bool
    errors: list[ValidationError] = []


def _parse_device_ids(config_iot_devices: str | None) -> list[str]:
    """Extract device IDs from config_iot_devices JSON."""
    if not config_iot_devices:
        return []
    try:
        devices = json.loads(config_iot_devices)
        if isinstance(devices, list):
            return [d.get("id") for d in devices if isinstance(d, dict) and d.get("id")]
    except json.JSONDecodeError:
        pass
    return []


def _parse_action_names(config_events: str | None) -> list[str]:
    """Extract action functionNames from config_events JSON.
    
    For workflow actions (step_function, logic_app, workflow), extracts both
    functionName and functionNameB since they represent chained functions.
    """
    if not config_events:
        return []
    try:
        events = json.loads(config_events)
        if isinstance(events, list):
            names = []
            for event in events:
                if isinstance(event, dict):
                    action = event.get("action", {})
                    if isinstance(action, dict):
                        if action.get("functionName"):
                            names.append(action["functionName"])
                        if action.get("functionNameB"):
                            names.append(action["functionNameB"])
            return names
    except json.JSONDecodeError:
        pass
    return []


def _get_state_machine_filename(provider: str) -> str:
    """Get state machine filename for provider."""
    provider = provider.lower()
    if provider == "azure":
        return "azure_logic_app.json"
    elif provider == "gcp" or provider == "google":
        return "google_cloud_workflow.yaml"
    else:  # aws is default
        return "aws_step_function.json"


@router.post(
    "/validate/deployer-complete",
    operation_id="validateDeployerComplete",
    response_model=DeployerValidationResponse,
    tags=["Validation"],
    summary="Validate complete deployer configuration",
    description="""
Validates ALL deployer configuration files and functions for state transition to 'configured'.

**Checks performed (reuses existing validators):**
- `deployer_digital_twin_name`: Non-empty, valid format (alphanumeric, hyphen, underscore, max 15 chars)
- `config_events`, `config_iot_devices`: Required, schema validation
- `payloads`: Required
- `processors`: One per device in config_iot_devices, code validation
- `hierarchy`: Required if L4 = AWS or Azure, schema validation
- `scene_config`, `scene_glb`: Required if needs3DModel = true and L4 = AWS/Azure
- `event_feedback`: Required if returnFeedbackToDevice = true
- `event_actions`: One per action functionName in config_events (if useEventChecking = true)
- `state_machine`: Required if triggerNotificationWorkflow = true
- `user_config`: Required if L5 = AWS or Azure

**Returns all errors, not just the first one.**
"""
)
async def validate_deployer_complete(
    config: DeployerCompleteValidation
) -> DeployerValidationResponse:
    """
    Validates complete deployer configuration for state transition.
    
    Reuses existing validators from validator.py.
    Returns all validation errors aggregated.
    """
    errors: list[ValidationError] = []
    
    # === CORE CONFIGS (always required) ===
    
    # Digital twin name
    name = config.deployer_digital_twin_name or ""
    if not name.strip():
        errors.append(ValidationError(
            code="EMPTY_NAME",
            field="deployer_digital_twin_name",
            message="Digital twin name in config.json is required"
        ))
    else:
        try:
            validator.validate_digital_twin_name(name)
        except ValueError as e:
            errors.append(ValidationError(
                code="INVALID_NAME",
                field="deployer_digital_twin_name",
                message=str(e)
            ))
    
    # Config events
    if not config.config_events:
        errors.append(ValidationError(
            code="MISSING_CONFIG_EVENTS",
            field="config_events",
            message="config_events.json is required"
        ))
    else:
        try:
            validator.validate_config_content("config_events.json", config.config_events)
        except ValueError as e:
            errors.append(ValidationError(
                code="INVALID_CONFIG_EVENTS",
                field="config_events",
                message=str(e)
            ))
    
    # Config IoT devices
    if not config.config_iot_devices:
        errors.append(ValidationError(
            code="MISSING_CONFIG_IOT_DEVICES",
            field="config_iot_devices",
            message="config_iot_devices.json is required"
        ))
    else:
        try:
            validator.validate_config_content("config_iot_devices.json", config.config_iot_devices)
        except ValueError as e:
            errors.append(ValidationError(
                code="INVALID_CONFIG_IOT_DEVICES",
                field="config_iot_devices",
                message=str(e)
            ))
    
    # Payloads
    if not config.payloads:
        errors.append(ValidationError(
            code="MISSING_PAYLOADS",
            field="payloads",
            message="payloads.json is required"
        ))
    
    # === PROCESSORS (per device) ===
    device_ids = _parse_device_ids(config.config_iot_devices)
    processors = config.processors or {}
    l2_provider = (config.cheapest_path or {}).get("L2", "aws").lower()
    
    for device_id in device_ids:
        code = processors.get(device_id)
        if not code:
            errors.append(ValidationError(
                code="MISSING_PROCESSOR",
                field=f"processor:{device_id}",
                message=f"Processor for device '{device_id}' is required"
            ))
        else:
            try:
                if l2_provider == "azure":
                    validator.validate_python_code_azure(code)
                elif l2_provider == "gcp" or l2_provider == "google":
                    validator.validate_python_code_google(code)
                else:  # aws is default
                    validator.validate_python_code_aws(code)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_PROCESSOR",
                    field=f"processor:{device_id}",
                    message=f"Processor for '{device_id}': {str(e)}"
                ))
    
    # === CONDITIONAL VALIDATION ===
    params = config.optimizer_params or {}
    path = config.cheapest_path or {}
    l4 = path.get("L4", "").upper()
    l5 = path.get("L5", "").upper()
    
    # Hierarchy (L4 = AWS/Azure)
    if l4 in ("AWS", "AZURE"):
        if not config.hierarchy:
            errors.append(ValidationError(
                code="MISSING_HIERARCHY",
                field="hierarchy",
                message=f"Hierarchy JSON is required for L4 provider ({l4})"
            ))
        else:
            try:
                if l4 == "AWS":
                    validator.validate_aws_hierarchy_content(config.hierarchy)
                else:
                    validator.validate_azure_hierarchy_content(config.hierarchy)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_HIERARCHY",
                    field="hierarchy",
                    message=str(e)
                ))
    
    # Scene config (L4 = AWS/Azure + needs3DModel)
    if l4 in ("AWS", "AZURE") and params.get("needs3DModel"):
        if not config.scene_config:
            errors.append(ValidationError(
                code="MISSING_SCENE_CONFIG",
                field="scene_config",
                message="Scene config is required for 3D visualization"
            ))
        else:
            try:
                validator.validate_scene_config_content(l4.lower(), config.scene_config, config.hierarchy)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_SCENE_CONFIG",
                    field="scene_config",
                    message=str(e)
                ))
        
        if not config.scene_glb_uploaded:
            errors.append(ValidationError(
                code="MISSING_SCENE_GLB",
                field="scene_glb",
                message="Scene GLB file must be uploaded for 3D visualization"
            ))
    
    # Event feedback (returnFeedbackToDevice = true)
    if params.get("returnFeedbackToDevice"):
        if not config.event_feedback:
            errors.append(ValidationError(
                code="MISSING_EVENT_FEEDBACK",
                field="event_feedback",
                message="Event feedback function is required (returnFeedbackToDevice=true)"
            ))
        else:
            try:
                if l2_provider == "azure":
                    validator.validate_python_code_azure(config.event_feedback)
                elif l2_provider == "gcp" or l2_provider == "google":
                    validator.validate_python_code_google(config.event_feedback)
                else:
                    validator.validate_python_code_aws(config.event_feedback)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_EVENT_FEEDBACK",
                    field="event_feedback",
                    message=f"Event feedback: {str(e)}"
                ))
    
    # Event actions (useEventChecking = true)
    if params.get("useEventChecking"):
        action_names = _parse_action_names(config.config_events)
        actions = config.event_actions or {}
        for action_name in action_names:
            code = actions.get(action_name)
            if not code:
                errors.append(ValidationError(
                    code="MISSING_EVENT_ACTION",
                    field=f"event_action:{action_name}",
                    message=f"Event action function '{action_name}' is required"
                ))
            else:
                try:
                    if l2_provider == "azure":
                        validator.validate_python_code_azure(code)
                    elif l2_provider == "gcp" or l2_provider == "google":
                        validator.validate_python_code_google(code)
                    else:
                        validator.validate_python_code_aws(code)
                except ValueError as e:
                    errors.append(ValidationError(
                        code="INVALID_EVENT_ACTION",
                        field=f"event_action:{action_name}",
                        message=f"Event action '{action_name}': {str(e)}"
                    ))
    
    # State machine (triggerNotificationWorkflow = true)
    if params.get("triggerNotificationWorkflow"):
        if not config.state_machine:
            errors.append(ValidationError(
                code="MISSING_STATE_MACHINE",
                field="state_machine",
                message="State machine is required (triggerNotificationWorkflow=true)"
            ))
        else:
            try:
                filename = _get_state_machine_filename(l2_provider)
                validator.validate_state_machine_content(filename, config.state_machine)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_STATE_MACHINE",
                    field="state_machine",
                    message=str(e)
                ))
    
    # User config (L5 = AWS/Azure)
    if l5 in ("AWS", "AZURE"):
        if not config.user_config:
            errors.append(ValidationError(
                code="MISSING_USER_CONFIG",
                field="user_config",
                message=f"User config is required for L5 provider ({l5})"
            ))
    
    return DeployerValidationResponse(
        valid=len(errors) == 0,
        errors=errors
    )


