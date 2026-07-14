"""Digital-twin hierarchy, user, and scene validation endpoints."""

import json
import re

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

import src.validator as validator
from src.api.dependencies import ProviderEnum
from src.api.error_handling import internal_server_error, safe_error_detail
from src.api.error_models import ERROR_RESPONSES
from src.api.upload_limits import MAX_VALIDATION_UPLOAD_BYTES, read_upload_bounded

router = APIRouter()

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
        413: ERROR_RESPONSES[413],
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
        content = await read_upload_bounded(
            file,
            max_bytes=MAX_VALIDATION_UPLOAD_BYTES,
        )
        content_str = content.decode('utf-8')
        
        if provider == ProviderEnum.aws:
            validator.validate_aws_hierarchy_content(content_str)
        elif provider == ProviderEnum.azure:
            validator.validate_azure_hierarchy_content(content_str)
        else:
            raise HTTPException(status_code=400, detail=f"Provider '{provider}' is not valid for L4. Use 'aws' or 'azure'.")
        
        return {"message": f"Hierarchy for {provider} is valid."}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=safe_error_detail(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_server_error("Validate hierarchy", exc) from exc

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
        413: ERROR_RESPONSES[413],
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
    try:
        content = await read_upload_bounded(
            file,
            max_bytes=MAX_VALIDATION_UPLOAD_BYTES,
        )
        content_str = content.decode('utf-8')
        
        try:
            user_config = json.loads(content_str)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON: {safe_error_detail(exc)}",
            ) from exc
        
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
    except Exception as exc:
        raise internal_server_error("Validate user configuration", exc) from exc

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
        413: ERROR_RESPONSES[413],
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
        scene_content = await read_upload_bounded(
            scene_file,
            max_bytes=MAX_VALIDATION_UPLOAD_BYTES,
        )
        scene_str = scene_content.decode('utf-8')
        
        hierarchy_str = None
        if hierarchy_file:
            hierarchy_content = await read_upload_bounded(
                hierarchy_file,
                max_bytes=MAX_VALIDATION_UPLOAD_BYTES,
            )
            hierarchy_str = hierarchy_content.decode('utf-8')
        
        # Delegate to validator function
        validator.validate_scene_config_content(provider.value, scene_str, hierarchy_str)
        
        return {"message": "Scene configuration is valid."}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=safe_error_detail(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_server_error("Validate scene configuration", exc) from exc
