"""Configuration, workflow, and serverless-code validation endpoints."""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

import src.validator as validator
from src.api.dependencies import ConfigType, ProviderEnum
from src.api.error_models import ERROR_RESPONSES
from logger import logger

router = APIRouter()

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


