from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Request
from pydantic import BaseModel
import file_manager
import src.validator as validator
from api.dependencies import ConfigType, ProviderEnum
from logger import logger
from api.utils import extract_file_content

router = APIRouter()

class FunctionValidationRequest(BaseModel):
    project_name: str
    function_name: str
    filename: str
    code: str

class FunctionCodeValidationRequest(BaseModel):
    provider: ProviderEnum
    code: str

# ==========================================
# 1. Zip Validation
# ==========================================
@router.post("/validate/zip", tags=["Validation"])
async def validate_zip(request: Request):
    """
    Validates a project zip file without extracting it.
    Supports Multipart (binary) or JSON (Base64).
    
    Checks performed:
    - Zip integrity.
    - Presence of all required configuration files.
    - Path traversal safety (Zip Slip).
    - Content schema validation for all config files.
    
    Returns:
        JSON message indicating validity.
    """
    try:
        content = await extract_file_content(request)
        validator.validate_project_zip(content)
        return {"message": "Project zip is valid and secure."}
    except ValueError as e:
        # Return 400 for validation errors (client side error)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. Config Validation
# ==========================================
@router.post("/validate/config/{config_type}", tags=["Validation"])
async def validate_config(config_type: ConfigType, request: Request):
    """
    Validates a specific configuration file against its schema.
    Supports Multipart (binary) or JSON (Base64).
    
    Args:
        config_type: Select from the dropdown.
        
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
        content = await extract_file_content(request)
        content_str = content.decode('utf-8')
        validator.validate_config_content(filename, content_str)
        return {"message": f"Configuration '{filename}' is valid."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 3. State Machine Validation
# ==========================================
@router.post("/validate/state-machine", tags=["Validation"])
async def validate_state_machine(
    request: Request,
    provider: ProviderEnum = Query(..., description="Target cloud provider")
):
    """
    Validates a state machine definition file against the provider's schema.
    Supports Multipart (binary) or JSON (Base64).
    
    Args:
        provider (ProviderEnum): aws, azure, or google.
    """
    filename_map = {
        "aws": "aws_step_function.json",
        "azure": "azure_logic_app.json",
        "google": "google_cloud_workflow.json"
    }
    
    target_filename = filename_map[provider]
    
    try:
        content = await extract_file_content(request)
        content_str = content.decode('utf-8')
        validator.validate_state_machine_content(target_filename, content_str)
        return {"message": f"State machine definition is valid for {provider}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 4. Function Code Validation
# ==========================================
@router.post("/validate/function", tags=["Validation"])
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
        provider = validator.get_provider_for_function(req.project_name, req.function_name)
        
        # Select appropriate validator
        if provider == "aws":
            validator.validate_python_code_aws(req.code)
        elif provider == "azure":
            validator.validate_python_code_azure(req.code)
        elif provider == "google":
            validator.validate_python_code_google(req.code)
            
        return {"message": f"Function code is valid for provider '{provider}'."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate/function-code", tags=["Validation"])
def validate_function_code(req: FunctionCodeValidationRequest):
    """
    Validates Python code for a specific provider independently of any project.
    
    Args:
        req (FunctionCodeValidationRequest): JSON body with provider and code.
    """
    try:
        if req.provider == ProviderEnum.aws:
            validator.validate_python_code_aws(req.code)
        elif req.provider == ProviderEnum.azure:
            validator.validate_python_code_azure(req.code)
        elif req.provider == ProviderEnum.google:
            validator.validate_python_code_google(req.code)
            
        return {"message": f"Code is valid for {req.provider}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
