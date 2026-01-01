from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
import src.validator as validator
from api.dependencies import ConfigType, ProviderEnum
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
    tags=["Validation"],
    summary="Validate project zip file",
    responses={
        200: {"description": "Project zip is valid"},
        400: {"description": "Validation failed with details"}
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
    tags=["Validation"],
    summary="Validate configuration file",
    responses={
        200: {"description": "Configuration is valid"},
        400: {"description": "Schema validation failed"}
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
    tags=["Validation"],
    summary="Validate state machine definition",
    responses={
        200: {"description": "State machine is valid"},
        400: {"description": "Invalid structure or schema"}
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
    tags=["Validation"],
    summary="Validate function code syntax",
    responses={
        200: {"description": "Code is valid"},
        400: {"description": "Syntax or signature error"}
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
    tags=["Validation"],
    summary="Validate simulator payloads",
    responses={
        200: {"description": "Payloads structure is valid"}
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
    tags=["Validation"],
    summary="Cross-validate payloads against devices",
    responses={
        200: {"description": "All payload device IDs exist in devices config"},
        400: {"description": "Device ID mismatch"}
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
