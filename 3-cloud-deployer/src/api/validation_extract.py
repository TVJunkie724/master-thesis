"""Secure project ZIP extraction for wizard imports."""

import json

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from api.error_models import ERROR_RESPONSES
from logger import logger

router = APIRouter()


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

