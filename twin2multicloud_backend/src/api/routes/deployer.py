"""Deployer Configuration API endpoints.

Manages deployer config for digital twins, including config validation,
GLB file uploads, and project.zip extraction for wizard auto-population.

**Key endpoints:**
- GET/PUT /config: Deployer configuration CRUD
- POST /validate/{type}: Validate config via Deployer API
- POST /upload-glb: Upload 3D scene file
- POST /upload-zip: Extract project.zip for wizard
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import httpx
import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

from src.models.database import get_db
from src.models.deployer_config import DeployerConfiguration
from src.models.twin import DigitalTwin
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.deployer_config import (
    DeployerConfigUpdate,
    DeployerConfigResponse,
    ConfigValidationRequest,
    ConfigValidationResponse,
)
from src.config import settings
from src.repositories.twin_repository import TwinRepository
from src.services.deployer_configuration_service import DeployerConfigurationService
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.services.twin_helpers import get_user_twin
from src.api.routes.error_models import ERROR_RESPONSES

router = APIRouter(prefix="/twins/{twin_id}/deployer", tags=["deployer"])


def _deployer_configuration_service(db: Session) -> DeployerConfigurationService:
    """Build the deployer configuration service for this request."""
    return DeployerConfigurationService(db=db, twin_repository=TwinRepository(db))


def _raise_service_http_error(exc: Exception) -> None:
    """Map typed service errors to the existing deployer HTTP contract."""
    if isinstance(exc, EntityNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc



@router.get(
    "/config", 
    response_model=DeployerConfigResponse,
    operation_id="getDeployerConfig",
    summary="Get deployer configuration for a twin",
    description=(
        "**Purpose:** Retrieve Step 3 (Deployer) configuration for a Digital Twin.\n\n"
        "**When to call:** Loading Step 3 wizard to restore saved config fields.\n\n"
        "**Response fields:**\n"
        "- `layer_*_provider`: Selected provider per layer (aws, azure, gcp)\n"
        "- `*_config`/`*_code`/`*_state_machine`: Config content per provider\n"
        "- `*_validated`: Boolean validation flags per section\n"
        "- `scene_glb_uploaded`: Whether 3D model file exists\n\n"
        "**Note:** Creates empty config if none exists."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def get_deployer_config(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get deployer configuration for a twin. Creates default if none exists."""
    try:
        return _deployer_configuration_service(db).get_config(twin_id=twin_id, user_id=current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


@router.put(
    "/config", 
    response_model=DeployerConfigResponse,
    operation_id="updateDeployerConfig",
    summary="Update deployer configuration",
    description=(
        "**Purpose:** Save Step 3 configuration fields (function code, state machines, configs).\n\n"
        "**When to call:** Auto-save on field blur, or explicit 'Save' button.\n\n"
        "**Request body:** Partial update - only provided fields are modified.\n\n"
        "**Key fields:**\n"
        "- `layer_*_provider`: aws, azure, or gcp\n"
        "- `*_function_code`, `*_state_machine`: Code and workflow definitions\n"
        "- `*_config`: Provider-specific configuration\n\n"
        "**Blocked states:** Returns 400 for DEPLOYED, DEPLOYING, DESTROYING twins.\n\n"
        "**Side effect:** Regresses CONFIGURED/ERROR/DESTROYED twins to DRAFT."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def update_deployer_config(
    twin_id: str,
    update: DeployerConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update deployer configuration for a twin.
    Validation state is persisted to gate save operations.
    """
    try:
        return _deployer_configuration_service(db).update_config(
            twin_id=twin_id,
            user_id=current_user.id,
            update=update,
        )
    except (EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


@router.post(
    "/validate/{config_type}", 
    response_model=ConfigValidationResponse,
    operation_id="validateDeployerConfigSection",
    summary="Validate a deployer config section via Deployer API",
    description=(
        "**Purpose:** Validate individual config sections before saving/deployment.\n\n"
        "**When to call:** User clicks 'Validate' button for a specific section.\n\n"
        "**Path param config_type:**\n"
        "- Section 2: 'events', 'iot', 'config', 'hierarchy'\n"
        "- Section 3 L1: 'payloads'\n"
        "- Section 3 L2: 'function-code', 'state-machine'\n"
        "- Section 3 L4: 'scene-config', 'user-config'\n\n"
        "**Response fields:**\n"
        "- `valid`: Boolean\n"
        "- `errors`: Array of {field, message, line (optional)}\n\n"
        "**Note:** Proxies to Deployer API's /validate/* endpoints."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def validate_config(
    twin_id: str,
    config_type: str,
    request: ConfigValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate config content via Deployer API.
    
    Section 2 types: 'events', 'iot', 'config' (persisted to DB)
    Section 3 L1: 'payloads' (persisted to DB)
    Section 3 L2: 'function-code', 'state-machine' (NOT persisted - BLoC handles)
    
    Proxies to Deployer API: POST /validate/{endpoint}
    """
    # Map Flutter config types to Deployer endpoint paths
    config_type_map = {
        # Section 2
        "events": "config/events",
        "iot": "config/iot",
        "config": "config/config",
        # Section 2: L4 Hierarchy
        "hierarchy": "hierarchy",
        # Section 3 L1
        "payloads": "simulator/payloads",
        # Section 3 L2
        "function-code": "function-code",
        "state-machine": "state-machine",
        # Section 3 L4
        "scene-config": "scene-config",
        "user-config": "user-config",
    }
    
    l2_types = {"function-code", "state-machine"}
    # L4 types require provider parameter
    l4_types = {"hierarchy", "scene-config", "user-config"}
    
    if config_type not in config_type_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config_type. Use: {list(config_type_map.keys())}"
        )
    
    # L2 types require provider parameter
    if config_type in l2_types and not request.provider:
        raise HTTPException(
            status_code=400,
            detail=f"provider is required for {config_type} validation (aws, azure, google)"
        )
    
    # L4 types require provider parameter
    if config_type in l4_types and not request.provider:
        raise HTTPException(
            status_code=400,
            detail=f"provider is required for {config_type} validation (aws or azure)"
        )
    
    twin = await get_user_twin(twin_id, current_user, db)
    deployer_endpoint = config_type_map[config_type]
    
    try:
        async with httpx.AsyncClient() as client:
            if config_type in l2_types:
                # L2: File upload with provider query param
                if config_type == "function-code":
                    ext = ".py"
                else:
                    # State machine: detect JSON vs YAML
                    ext = ".json" if request.content.strip().startswith(("{", "[")) else ".yaml"
                
                files = {"file": (f"code{ext}", request.content.encode(), "text/plain")}
                response = await client.post(
                    f"{settings.DEPLOYER_URL}/validate/{deployer_endpoint}?provider={request.provider}",
                    files=files,
                    timeout=30.0
                )
            elif config_type in l4_types:
                # L4: File upload with provider query param
                if config_type == "scene-config":
                    # Scene config needs hierarchy for cross-reference
                    config = twin.deployer_config
                    hierarchy_content = config.hierarchy_content if config else ""
                    files = {
                        "scene_file": ("scene.json", request.content.encode(), "application/json"),
                        "hierarchy_file": ("hierarchy.json", (hierarchy_content or "").encode(), "application/json"),
                    }
                else:
                    # hierarchy or user-config: simple file upload
                    files = {"file": (f"{config_type}.json", request.content.encode(), "application/json")}
                
                response = await client.post(
                    f"{settings.DEPLOYER_URL}/validate/{deployer_endpoint}?provider={request.provider}",
                    files=files,
                    timeout=30.0
                )
            else:
                # Section 2 / L1: JSON file upload
                files = {
                    "file": (f"config_{config_type}.json", request.content.encode(), "application/json")
                }
                response = await client.post(
                    f"{settings.DEPLOYER_URL}/validate/{deployer_endpoint}",
                    files=files,
                    timeout=30.0
                )
            
            if response.status_code == 200:
                result = response.json()
                valid = True
                message = result.get("message", "Valid")
                
                # Only persist validation for Section 2/L1/L4 types, NOT L2
                # L2 per-entity validation is handled by Flutter BLoC
                if config_type not in l2_types:
                    config = twin.deployer_config
                    if not config:
                        config = DeployerConfiguration(twin_id=twin_id)
                        db.add(config)
                    
                    if config_type == "config":
                        config.config_json_validated = True
                    elif config_type == "events":
                        config.config_events_validated = True
                    elif config_type == "iot":
                        config.config_iot_devices_validated = True
                    elif config_type == "payloads":
                        config.payloads_validated = True
                    # L4 types
                    elif config_type == "hierarchy":
                        config.hierarchy_validated = True
                    elif config_type == "scene-config":
                        config.scene_config_validated = True
                    elif config_type == "user-config":
                        config.user_config_validated = True
                    
                    db.commit()
                
                return ConfigValidationResponse(valid=valid, message=message)
            else:
                # Normalize error: Deployer uses "detail" for errors
                try:
                    error_detail = response.json().get("detail", response.text)
                except Exception:
                    error_detail = response.text
                
                return ConfigValidationResponse(
                    valid=False,
                    message=str(error_detail)
                )
                
    except httpx.ConnectError:
        return ConfigValidationResponse(
            valid=False,
            message="Cannot connect to Deployer API. Is it running on port 5004?"
        )
    except httpx.RequestError as e:
        return ConfigValidationResponse(
            valid=False,
            message=f"Request error: {str(e)}"
        )


# ==========================================
# GLB File Upload/Delete for L4 Scene
# ==========================================
@router.post(
    "/upload-glb",
    operation_id="uploadSceneGlb",
    summary="Upload 3D scene GLB file",
    description=(
        "**Purpose:** Upload the scene.glb file for L4 3D visualization.\n\n"
        "**When to call:** User selects GLB file in Step 3 L4 config.\n\n"
        "**Constraints:**\n"
        "- Max file size: 100MB\n"
        "- Must be `.glb` format\n\n"
        "**Response:** `{message, size_mb}` on success.\n\n"
        "**Storage:** Saved to `UPLOAD_DIR/{twin_id}/scene.glb`."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        500: ERROR_RESPONSES[500],
    }
)
async def upload_scene_glb(
    twin_id: str,
    file: UploadFile = File(..., description="Scene GLB file (max 100MB)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload scene.glb file for 3D visualization.
    
    Saves to: UPLOAD_DIR/<twin_id>/scene.glb
    File size limit: MAX_GLB_SIZE_MB (default 100MB)
    """
    twin = await get_user_twin(twin_id, current_user, db)
    
    # Check file size
    max_size = settings.MAX_GLB_SIZE_MB * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {settings.MAX_GLB_SIZE_MB}MB limit"
        )
    
    # Save to disk
    upload_path = Path(settings.UPLOAD_DIR) / twin_id
    glb_path = upload_path / "scene.glb"
    
    try:
        upload_path.mkdir(parents=True, exist_ok=True)
        with open(glb_path, "wb") as f:
            f.write(contents)
        
        # Update DB flag
        config = twin.deployer_config
        if not config:
            config = DeployerConfiguration(twin_id=twin_id)
            db.add(config)
        config.scene_glb_uploaded = True
        db.commit()
        
        return {"message": "GLB file uploaded successfully", "size_mb": round(len(contents) / 1024 / 1024, 2)}
    except Exception as e:
        # Cleanup on failure
        glb_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save GLB file: {str(e)}")


@router.delete(
    "/upload-glb",
    operation_id="deleteSceneGlb",
    summary="Delete 3D scene GLB file",
    description=(
        "**Purpose:** Remove the uploaded scene.glb file.\n\n"
        "**When to call:**\n"
        "- User unchecks 'Include 3D Model' toggle\n"
        "- L4 provider changes (invalidates previous GLB)\n"
        "- Twin is deleted\n\n"
        "**Side effects:** Updates `scene_glb_uploaded` flag to false."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def delete_scene_glb(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete scene.glb file for a twin.
    
    Called when:
    - needs3DModel is toggled off
    - L4 provider changes (invalidation)
    - Twin is deleted
    """
    twin = await get_user_twin(twin_id, current_user, db)
    
    # Delete from disk
    glb_path = Path(settings.UPLOAD_DIR) / twin_id / "scene.glb"
    glb_path.unlink(missing_ok=True)
    
    # Try to remove empty directory
    try:
        (Path(settings.UPLOAD_DIR) / twin_id).rmdir()
    except OSError:
        pass  # Directory not empty or doesn't exist
    
    # Update DB flag
    config = twin.deployer_config
    if config:
        config.scene_glb_uploaded = False
        db.commit()
    
    return {"message": "GLB file deleted"}


# ==========================================
# Zip Upload and Extraction for Wizard
# ==========================================
@router.post(
    "/upload-zip",
    operation_id="uploadProjectZip",
    summary="Upload project.zip for wizard auto-population",
    description=(
        "**Purpose:** Upload and extract project.zip to auto-populate Step 3 fields.\n\n"
        "**When to call:** User clicks 'Upload Project Zip' button in Step 3.\n\n"
        "**Flow:**\n"
        "1. Validates zip structure against optimizer's cheapest_path\n"
        "2. Extracts code files, configs, and optional scene.glb\n"
        "3. Returns content for UI fields (NOT persisted - BLoC handles save)\n\n"
        "**Response fields per provider:**\n"
        "- `functionCode`, `stateMachine`, `config`: Content strings\n"
        "- `valid`: Boolean validation status\n"
        "- `errors`: Validation errors if any\n\n"
        "**Max size:** 100MB"
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        413: {"description": "File too large (max 100MB)"},
    }
)
async def upload_project_zip(
    twin_id: str,
    file: UploadFile = File(..., description="Project zip file to extract"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload and extract project.zip for Step 3 wizard auto-population.
    
    1. Builds ValidationContext from twin's saved optimizer config
    2. Proxies to Deployer /validate/zip/extract
    3. If GLB exists in response, saves via existing upload logic
    4. Returns extracted content for Flutter to populate fields
    """
    import base64
    
    twin = await get_user_twin(twin_id, current_user, db)
    
    # Build validation context from twin's optimizer config
    validation_context = {
        "skip_credentials": True,  # Mode A: never return credentials
        "skip_config_files": [],   # Validate all files
    }
    
    # Get provider info from optimizer config if available.
    # Prefer the cheapest_l* columns; fall back to parsing result_json.calculationResult
    # when the columns weren't populated (data inconsistency from save endpoint).
    if twin.optimizer_config:
        opt_config = twin.optimizer_config

        # Parse calculationResult from result_json as fallback source
        calc_result = {}
        if opt_config.result_json:
            try:
                calc_result = (json.loads(opt_config.result_json) or {}).get("calculationResult", {}) or {}
            except (ValueError, TypeError):
                calc_result = {}

        def _resolve_layer(column_value: str | None, calc_key: str) -> str | None:
            if column_value:
                return column_value.lower()
            raw = calc_result.get(calc_key)
            return raw.lower() if isinstance(raw, str) and raw else None

        l2 = _resolve_layer(opt_config.cheapest_l2, "L2")
        l4 = _resolve_layer(opt_config.cheapest_l4, "L4")
        if l2:
            validation_context["l2_provider"] = l2
        if l4:
            validation_context["l4_provider"] = l4
        logger.info(
            "upload-zip: resolved providers for twin %s — l2=%s, l4=%s (columns: l2=%s l4=%s)",
            twin_id, l2, l4, opt_config.cheapest_l2, opt_config.cheapest_l4,
        )
    
    # Read zip file content
    zip_content = await file.read()
    
    # File size limit: 100MB
    MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100 MB
    if len(zip_content) > MAX_ZIP_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is 100MB, got {len(zip_content) / (1024*1024):.1f}MB"
        )
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Proxy to Deployer
            response = await client.post(
                f"{settings.DEPLOYER_URL}/validate/zip/extract",
                files={"file": ("project.zip", zip_content, "application/zip")},
                params={
                    "validation_context": json.dumps(validation_context),
                    "include_credentials": False
                }
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "validation_errors": [f"Deployer error: {response.text}"],
                    "files": {},
                    "functions": {"processors": {}, "event_actions": {}, "event_feedback": None},
                    "assets": {"scene_glb": None},
                    "warnings": []
                }
            
            result = response.json()
            
            # If GLB exists in result, save it locally
            assets = result.get("assets") or {}
            scene_glb = assets.get("scene_glb") or {}
            if scene_glb.get("exists"):
                glb_data = scene_glb
                if glb_data.get("content") and glb_data.get("is_binary"):
                    try:
                        glb_bytes = base64.b64decode(glb_data["content"])
                        
                        # Save to disk (reuse existing logic)
                        upload_path = Path(settings.UPLOAD_DIR) / twin_id
                        glb_path = upload_path / "scene.glb"
                        upload_path.mkdir(parents=True, exist_ok=True)
                        
                        with open(glb_path, "wb") as f:
                            f.write(glb_bytes)
                        
                        # Update DB flag
                        config = twin.deployer_config
                        if not config:
                            config = DeployerConfiguration(twin_id=twin_id)
                            db.add(config)
                        config.scene_glb_uploaded = True
                        db.commit()
                        
                        # Mark as saved (don't return base64 content to Flutter)
                        result["assets"]["scene_glb"] = {
                            "exists": True,
                            "saved": True,
                            "is_binary": True,
                            "content": None  # Don't send base64 back to Flutter
                        }
                    except Exception as e:
                        result["warnings"] = result.get("warnings", []) + [f"Failed to save GLB: {str(e)}"]
            
            return result
            
    except httpx.ConnectError:
        return {
            "success": False,
            "validation_errors": ["Cannot connect to Deployer API. Is it running?"],
            "files": {},
            "functions": {"processors": {}, "event_actions": {}, "event_feedback": None},
            "assets": {"scene_glb": None},
            "warnings": []
        }
    except httpx.RequestError as e:
        return {
            "success": False,
            "validation_errors": [f"Request error: {str(e)}"],
            "files": {},
            "functions": {"processors": {}, "event_actions": {}, "event_feedback": None},
            "assets": {"scene_glb": None},
            "warnings": []
        }
