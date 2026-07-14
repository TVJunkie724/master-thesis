"""Function discovery and post-deployment update API routes."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

import constants as CONSTANTS
from api.dependencies import check_template_protection
from api.error_models import ERROR_RESPONSES
from api.function_artifacts import (
    _build_function_zip,
    _compute_directory_hash,
    _get_hash_metadata,
    _save_hash_metadata,
)
from api.function_errors import FunctionProviderError
from api.function_discovery import (
    _get_cached_functions,
    _get_updatable_functions,
    _get_upload_dir,
    _invalidate_cache,
    _set_cache,
)
from api.function_upload import _upload_aws_lambda, _upload_azure_function
from api.function_upload import _upload_gcp_function
from logger import logger
from src.core.config_loader import ProjectConfigLoader
from src.providers.terraform.package_builder import build_azure_user_bundle
from src.terraform_runner import TerraformRunner

router = APIRouter()


def _load_twin_name(project_name: str) -> str:
    config_path = Path(_get_upload_dir(project_name)) / CONSTANTS.CONFIG_FILE
    if not config_path.is_file():
        raise ValueError(f"Missing config file: {CONSTANTS.CONFIG_FILE}")
    config = json.loads(config_path.read_text())
    twin_name = config.get("digital_twin_name")
    if not twin_name:
        raise ValueError(f"Missing digital_twin_name in {CONSTANTS.CONFIG_FILE}")
    return twin_name


def _provider_function_name(provider: str, function_type: str, twin_name: str, name: str) -> str:
    if function_type == "event_action":
        return f"{twin_name}-event-action-{name}" if provider in {"gcp", "google"} else f"{twin_name}-{name}"
    if function_type == "processor":
        return f"{twin_name}-{name}-processor"
    if function_type == "feedback":
        return f"{twin_name}-event-feedback"
    raise ValueError(f"Unknown function type: {function_type}")


def _build_azure_bundle_and_resolve_app(project_name: str) -> tuple[bytes, str]:
    bundle = ProjectConfigLoader().load_bundle(project_name)
    zip_path = build_azure_user_bundle(bundle.project_path, bundle.config.providers)
    if zip_path is None:
        raise ValueError("No Azure user functions are configured")

    state_path = bundle.project_path / "terraform" / "terraform.tfstate"
    if not state_path.is_file():
        raise ValueError("Terraform state is required to resolve the Azure Function App")
    terraform_dir = Path(__file__).resolve().parents[1] / "terraform"
    outputs = TerraformRunner(str(terraform_dir), str(state_path)).output()
    app_name = outputs.get("azure_user_functions_app_name")
    if not app_name:
        raise ValueError("Azure user Function App is missing from Terraform outputs")
    return zip_path.read_bytes(), app_name

@router.get(
    "/updatable_functions",
    operation_id="listUpdatableFunctions",
    tags=["Functions"],
    summary="List user-modifiable functions",
    description=(
        "**Purpose:** Discover all functions that can be updated via SDK.\n\n"
        "**When to call:** Before updating functions to get available targets.\n\n"
        "**Returns:** Function names, types (event_action/processor/feedback), and deployment status."
    ),
    responses={
        200: {"description": "Function list retrieved"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
def get_updatable_functions(
    project_name: str = Query("template", description="Name of the project")
):
    """
    List all user-modifiable functions for a project.
    
    **Provider auto-discovery:** The provider (AWS/Azure/Google) is determined automatically 
    from the project's `config_providers.json` (`layer_2_provider` field).
    
    **Function types discovered:**
    - Event actions from `config_events.json`
    - Processors from `config_iot_devices.json`
    - Event-feedback function (if configured)
    
    **Returns:** Dict mapping function names to metadata including:
    - `provider`: aws, azure, or google (from config)
    - `type`: event_action, processor, or feedback
    - `exists`: whether code directory exists
    - `path`: absolute path to function code
    
    Results are cached for 60 seconds.
    """
    # NOTE: validate_project_context removed - blocking production use
    
    try:
        # Check cache first
        cached = _get_cached_functions(project_name)
        if cached is not None:
            return {
                "project": project_name,
                "cached": True,
                "functions": cached
            }
        
        # Discover functions
        functions = _get_updatable_functions(project_name)
        
        # Cache result
        _set_cache(project_name, functions)
        
        return {
            "project": project_name,
            "cached": False,
            "functions": functions
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting updatable functions: {e}")
        raise HTTPException(status_code=500, detail="Function operation failed. Check logs.")


@router.post(
    "/update_function/{function_name}",
    operation_id="updateFunctionCode",
    tags=["Functions"],
    summary="Update function code via SDK",
    description=(
        "**Purpose:** Deploy updated function code to cloud via SDK (boto3/Kudu/gcloud).\n\n"
        "**When to call:** After modifying function code locally.\n\n"
        "**Process:** Build ZIP → Compare hash → Upload if changed → Save metadata."
    ),
    responses={
        200: {"description": "Function updated"},
        400: ERROR_RESPONSES[400],
        502: ERROR_RESPONSES[502],
        500: ERROR_RESPONSES[500],
    }
)
def update_function(
    function_name: str,
    project_name: str = Query("template", description="Name of the project"),
    force: bool = Query(False, description="Force update even if hash unchanged")
):
    """
    Update a single function's code via SDK.
    
    **Prerequisites:** Function must be listed in `GET /functions/updatable_functions`.
    The provider (AWS/Azure/Google) is determined from the project's `config_providers.json`.
    
    **Process:**
    1. Verify `function_name` exists in the updatable functions list
    2. Build deployment ZIP (with shared modules for AWS Lambda)
    3. Compare hash - skip if unchanged (unless `force=True`)
    4. Upload via SDK (boto3 for AWS, Kudu for Azure, gcloud for GCP)
    5. Save hash metadata for future comparisons
    
    **Returns:** Update result with status, version info, and hash.
    """
    # Protect template project from modifications
    check_template_protection(project_name, "update function in")
    # NOTE: validate_project_context removed - blocking production use
    
    try:
        # Step 1: Get updatable functions list
        functions = _get_updatable_functions(project_name)
        
        if function_name not in functions:
            raise ValueError(
                f"Function '{function_name}' is not in the updatable functions list. "
                f"Available functions: {list(functions.keys())}"
            )
        
        func_info = functions[function_name]
        
        # Step 2: Verify code exists
        if not func_info["exists"]:
            raise ValueError(
                f"Function code not found: {func_info.get('error', 'Missing code directory')}"
            )
        
        provider = func_info["provider"]
        func_dir = func_info["path"]
        
        # Step 3: Compute hash and check for changes
        current_hash = _compute_directory_hash(func_dir)
        
        existing_metadata = _get_hash_metadata(project_name, function_name, provider)
        
        if not force and existing_metadata:
            if existing_metadata.get("zip_hash") == current_hash:
                return {
                    "function": function_name,
                    "status": "unchanged",
                    "message": "Code hash unchanged, skipping update. Use force=True to override.",
                    "hash": current_hash
                }
        
        # Step 4: Build the provider-specific deployment archive.
        shared_dir = None
        if provider == "aws":
            shared_dir = str(Path(__file__).parent.parent / "providers" / "aws" / "lambda_functions" / "_shared")
        zip_content = _build_function_zip(func_dir, shared_dir)

        twin_name = _load_twin_name(project_name)
        function_type = func_info["type"]

        # Step 5: Upload via the provider adapter.
        if provider == "aws":
            lambda_name = _provider_function_name(provider, function_type, twin_name, function_name)
            result = _upload_aws_lambda(lambda_name, zip_content, project_name)
        elif provider == "azure":
            zip_content, app_name = _build_azure_bundle_and_resolve_app(project_name)
            result = _upload_azure_function(app_name, zip_content, project_name)
        elif provider in {"gcp", "google"}:
            gcp_name = _provider_function_name(provider, function_type, twin_name, function_name)
            result = _upload_gcp_function(gcp_name, zip_content, project_name)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        # Step 6: Save hash metadata
        _save_hash_metadata(project_name, function_name, provider, current_hash)
        
        # Invalidate cache since we made changes
        _invalidate_cache(project_name)
        
        return {
            "function": function_name,
            "status": "updated",
            "provider": provider,
            "hash": current_hash,
            **result
        }
    
    except FunctionProviderError as e:
        logger.warning("Function provider update failed for %s: %s", function_name, e)
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating function {function_name}: {e}")
        raise HTTPException(status_code=500, detail="Function operation failed. Check logs.")


# ==========================================
# Cache Invalidation Hook (for external use)
# ==========================================

def invalidate_function_cache(project_name: str) -> None:
    """
    Public function to invalidate function cache.
    
    Should be called when:
    - config_events.json changes
    - config_iot_devices.json changes
    - Function code is updated via update_function_file endpoint
    
    Args:
        project_name: Name of the project
    """
    _invalidate_cache(project_name)
