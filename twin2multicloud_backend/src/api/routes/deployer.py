from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import httpx
import json
import shutil
from pathlib import Path

from src.models.database import get_db
from src.models.twin import DigitalTwin, TwinState
from src.models.deployer_config import DeployerConfiguration
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.deployer_config import (
    DeployerConfigUpdate,
    DeployerConfigResponse,
    ConfigValidationRequest,
    ConfigValidationResponse,
)
from src.config import settings

router = APIRouter(prefix="/twins/{twin_id}/deployer", tags=["deployer"])


async def get_user_twin(twin_id: str, user: User, db: Session) -> DigitalTwin:
    """Helper to verify twin ownership."""
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin


@router.get("/config", response_model=DeployerConfigResponse)
async def get_deployer_config(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get deployer configuration for a twin. Creates default if none exists."""
    twin = await get_user_twin(twin_id, current_user, db)
    
    if not twin.deployer_config:
        config = DeployerConfiguration(twin_id=twin_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    else:
        config = twin.deployer_config
    
    return DeployerConfigResponse.from_db(config)


@router.put("/config", response_model=DeployerConfigResponse)
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
    twin = await get_user_twin(twin_id, current_user, db)
    
    # Block modifications for deployed/deploying/destroying twins
    BLOCKED_STATES = {TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING}
    if twin.state in BLOCKED_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot modify twin in '{twin.state.value}' state"
        )
    
    # Track if we need to regress state
    REGRESS_STATES = {TwinState.CONFIGURED, TwinState.ERROR, TwinState.DESTROYED}
    should_regress = twin.state in REGRESS_STATES
    
    if not twin.deployer_config:
        config = DeployerConfiguration(twin_id=twin_id)
        db.add(config)
    else:
        config = twin.deployer_config
    
    # Update fields
    if update.deployer_digital_twin_name is not None:
        config.deployer_digital_twin_name = update.deployer_digital_twin_name
    if update.config_events_json is not None:
        config.config_events_json = update.config_events_json
    if update.config_iot_devices_json is not None:
        config.config_iot_devices_json = update.config_iot_devices_json
    if update.config_json_validated is not None:
        config.config_json_validated = update.config_json_validated
    if update.config_events_validated is not None:
        config.config_events_validated = update.config_events_validated
    if update.config_iot_devices_validated is not None:
        config.config_iot_devices_validated = update.config_iot_devices_validated
    # Section 3: L1 Payloads
    if update.payloads_json is not None:
        config.payloads_json = update.payloads_json
    if update.payloads_validated is not None:
        config.payloads_validated = update.payloads_validated
    # Section 3: L2 User Functions
    if update.processor_contents is not None:
        config.processor_contents = json.dumps(update.processor_contents)
    if update.processor_validated is not None:
        config.processor_validated = json.dumps(update.processor_validated)
    if update.processor_requirements is not None:
        config.processor_requirements = json.dumps(update.processor_requirements)
    if update.event_feedback_content is not None:
        config.event_feedback_content = update.event_feedback_content
    if update.event_feedback_validated is not None:
        config.event_feedback_validated = update.event_feedback_validated
    if update.event_feedback_requirements is not None:
        config.event_feedback_requirements = update.event_feedback_requirements
    if update.event_action_contents is not None:
        config.event_action_contents = json.dumps(update.event_action_contents)
    if update.event_action_validated is not None:
        config.event_action_validated = json.dumps(update.event_action_validated)
    if update.event_action_requirements is not None:
        config.event_action_requirements = json.dumps(update.event_action_requirements)
    if update.state_machine_content is not None:
        config.state_machine_content = update.state_machine_content
    if update.state_machine_validated is not None:
        config.state_machine_validated = update.state_machine_validated
    # Section 2: L4 Hierarchy
    if update.hierarchy_content is not None:
        config.hierarchy_content = update.hierarchy_content
    if update.hierarchy_validated is not None:
        config.hierarchy_validated = update.hierarchy_validated
    # Section 3: L4 Scene
    if update.scene_glb_uploaded is not None:
        config.scene_glb_uploaded = update.scene_glb_uploaded
    if update.scene_config_content is not None:
        config.scene_config_content = update.scene_config_content
    if update.scene_config_validated is not None:
        config.scene_config_validated = update.scene_config_validated
    # Section 3: L4/L5 User Config
    if update.user_config_content is not None:
        config.user_config_content = update.user_config_content
    if update.user_config_validated is not None:
        config.user_config_validated = update.user_config_validated
    
    # Regress to draft if editing configured/error/destroyed twin
    if should_regress:
        twin.state = TwinState.DRAFT
    
    db.commit()
    db.refresh(config)
    db.refresh(twin)
    
    # Include twin_state in response for frontend sync
    response = DeployerConfigResponse.from_db(config)
    return {**response.dict(), "twin_state": twin.state.value}


@router.post("/validate/{config_type}", response_model=ConfigValidationResponse)
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
@router.post("/upload-glb")
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


@router.delete("/upload-glb")
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
@router.post("/upload-zip")
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
    
    # Get provider info from optimizer config if available
    if twin.optimizer_config:
        opt_config = twin.optimizer_config
        # Map providers from cheapest path columns
        if opt_config.cheapest_l2:
            validation_context["l2_provider"] = opt_config.cheapest_l2.lower()
        if opt_config.cheapest_l4:
            validation_context["l4_provider"] = opt_config.cheapest_l4.lower()
    
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

