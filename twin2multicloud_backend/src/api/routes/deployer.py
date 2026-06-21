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

from src.models.database import get_db
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.deployer_config import (
    DeployerConfigUpdate,
    DeployerConfigResponse,
    ConfigValidationRequest,
    ConfigValidationResponse,
)
from src.repositories.twin_repository import TwinRepository
from src.services.deployer_config_validation_service import DeployerConfigValidationService
from src.services.deployer_configuration_service import DeployerConfigurationService
from src.services.project_zip_extraction_service import ProjectZipExtractionService
from src.services.scene_glb_service import SceneGlbService
from src.services.service_errors import EntityNotFoundError, StorageError, ValidationError
from src.api.routes.error_models import ERROR_RESPONSES

router = APIRouter(prefix="/twins/{twin_id}/deployer", tags=["deployer"])


def _deployer_configuration_service(db: Session) -> DeployerConfigurationService:
    """Build the deployer configuration service for this request."""
    return DeployerConfigurationService(db=db, twin_repository=TwinRepository(db))


def _deployer_config_validation_service(db: Session) -> DeployerConfigValidationService:
    """Build the deployer config validation service for this request."""
    return DeployerConfigValidationService(db=db, twin_repository=TwinRepository(db))


def _scene_glb_service(db: Session) -> SceneGlbService:
    """Build the scene GLB storage service for this request."""
    return SceneGlbService(db=db, twin_repository=TwinRepository(db))


def _project_zip_extraction_service(db: Session) -> ProjectZipExtractionService:
    """Build the project ZIP extraction service for this request."""
    twin_repository = TwinRepository(db)
    return ProjectZipExtractionService(
        db=db,
        twin_repository=twin_repository,
        scene_glb_service=SceneGlbService(db=db, twin_repository=twin_repository),
    )


def _raise_service_http_error(exc: Exception) -> None:
    """Map typed service errors to the existing deployer HTTP contract."""
    if isinstance(exc, EntityNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, StorageError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
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
    try:
        return await _deployer_config_validation_service(db).validate_config(
            twin_id=twin_id,
            user_id=current_user.id,
            config_type=config_type,
            request=request,
        )
    except (EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


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
    contents = await file.read()
    try:
        return _scene_glb_service(db).upload_scene_glb(
            twin_id=twin_id,
            user_id=current_user.id,
            content=contents,
        )
    except (EntityNotFoundError, ValidationError, StorageError) as exc:
        _raise_service_http_error(exc)


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
    try:
        return _scene_glb_service(db).delete_scene_glb(twin_id=twin_id, user_id=current_user.id)
    except (EntityNotFoundError, StorageError) as exc:
        _raise_service_http_error(exc)


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
    zip_content = await file.read()
    try:
        return await _project_zip_extraction_service(db).upload_project_zip(
            twin_id=twin_id,
            user_id=current_user.id,
            zip_content=zip_content,
        )
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)
    except ValidationError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
