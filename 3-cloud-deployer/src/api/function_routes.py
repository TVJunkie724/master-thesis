"""Function discovery and post-deployment update API routes."""

import json
from pathlib import Path
import tempfile

from fastapi import APIRouter, HTTPException, Query

import constants as CONSTANTS
from src.api.dependencies import check_template_protection
from src.api.error_models import ERROR_RESPONSES
from src.api.function_artifacts import (
    _compute_source_hash,
    get_artifact_metadata,
)
from src.api.function_errors import FunctionProviderError
from src.api.function_discovery import (
    _get_cached_functions,
    _get_updatable_functions,
    _get_upload_dir,
    _invalidate_cache,
    _set_cache,
)
from src.api.function_upload import _upload_aws_lambda, _upload_azure_function
from src.api.function_upload import _upload_gcp_function
from logger import logger
from src.core.config_loader import ProjectConfigLoader
from src.core.observability import redact_sensitive
from src.function_metadata import (
    hash_bytes,
    mark_function_deployed,
    mark_provider_artifact_deployed,
    record_function_build,
)
from src.providers.terraform.package_builder import build_azure_user_bundle
from src.providers.terraform.package_builders.aws import _create_lambda_zip
from src.providers.terraform.package_builders.gcp import _create_gcp_function_zip
from src.terraform_runner import TerraformRunner

router = APIRouter()
PROVIDERS_ROOT = Path(__file__).resolve().parents[1] / "providers"


def _public_function_inventory(functions: dict) -> dict:
    """Remove host filesystem details from the public discovery contract."""
    return {
        name: {key: value for key, value in descriptor.items() if key != "path"}
        for name, descriptor in functions.items()
    }


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


def _metadata_function_name(function_type: str, name: str) -> str:
    if function_type == "processor":
        return f"processor-{name}"
    if function_type == "feedback":
        return "event-feedback"
    return name


def _build_provider_update_artifact(
    provider: str,
    function_dir: str,
    *,
    twin_name: str,
    function_type: str,
    function_name: str,
) -> bytes:
    """Build the same provider artifact shape used by Terraform deployments."""
    source = Path(function_dir)
    with tempfile.TemporaryDirectory(prefix="function-update-") as temporary_dir:
        target = Path(temporary_dir) / "function.zip"
        if provider == "aws":
            _create_lambda_zip(
                source,
                PROVIDERS_ROOT / "aws" / "lambda_functions" / "_shared",
                target,
                digital_twin_name=twin_name,
                device_id=function_name if function_type == "processor" else None,
            )
        elif provider in {"gcp", "google"}:
            _create_gcp_function_zip(
                source,
                PROVIDERS_ROOT / "gcp" / "cloud_functions" / "_shared",
                target,
                digital_twin_name=twin_name,
                device_id=function_name if function_type == "processor" else None,
            )
        else:
            raise ValueError(f"Unsupported individual function provider: {provider}")
        return target.read_bytes()


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
    - `provider`: aws, azure, or gcp
    - `type`: event_action, processor, or feedback
    - `exists`: whether code directory exists
    
    Results are cached for 60 seconds.
    """
    try:
        # Check cache first
        cached = _get_cached_functions(project_name)
        if cached is not None:
            return {
                "project": project_name,
                "cached": True,
                "functions": _public_function_inventory(cached),
            }
        
        # Discover functions
        functions = _get_updatable_functions(project_name)
        
        # Cache result
        _set_cache(project_name, functions)
        
        return {
            "project": project_name,
            "cached": False,
            "functions": _public_function_inventory(functions),
        }
    
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error getting updatable functions: %s", redact_sensitive(exc))
        raise HTTPException(
            status_code=500,
            detail="Function operation failed. Check logs.",
        ) from exc


@router.post(
    "/update_function/{function_name}",
    operation_id="updateFunctionCode",
    tags=["Functions"],
    summary="Update function code via SDK",
    description=(
        "**Purpose:** Deploy updated function code to cloud via SDK (boto3/Kudu/gcloud).\n\n"
        "**When to call:** After modifying function code locally.\n\n"
        "**Process:** Build provider artifact → Compare deployed evidence → Upload if changed "
        "→ Record deployment evidence."
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
    2. Build the canonical provider deployment artifact
    3. Compare it with successful deployment evidence (unless `force=True`)
    4. Upload via SDK (boto3 for AWS, Kudu for Azure, Cloud Functions API for GCP)
    5. Record deployment evidence only after provider success
    
    Azure functions share one Function App bundle; updating one target can therefore
    update all functions represented by that bundle.

    **Returns:** Update result with status, provider details, artifact hash, source
    hash, and all affected functions.
    """
    # Protect template project from modifications
    check_template_protection(project_name, "update function in")
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
        
        provider = "gcp" if func_info["provider"] == "google" else func_info["provider"]
        func_dir = func_info["path"]
        twin_name = _load_twin_name(project_name)
        function_type = func_info["type"]
        metadata_name = _metadata_function_name(function_type, function_name)
        source_hash = _compute_source_hash(func_dir)

        if provider == "azure":
            zip_content, app_name = _build_azure_bundle_and_resolve_app(project_name)
            artifact_hash = hash_bytes(zip_content)
            existing_metadata = get_artifact_metadata(
                project_name,
                metadata_name,
                provider,
            )
        else:
            zip_content = _build_provider_update_artifact(
                provider,
                func_dir,
                twin_name=twin_name,
                function_type=function_type,
                function_name=function_name,
            )
            artifact_hash = hash_bytes(zip_content)
            target = record_function_build(
                Path(_get_upload_dir(project_name)),
                metadata_name,
                provider,
                source_hash,
                artifact_hash,
            )
            existing_metadata = get_artifact_metadata(
                project_name,
                metadata_name,
                provider,
            )

        if (
            not force
            and existing_metadata
            and existing_metadata.get("deployed_artifact_hash") == artifact_hash
        ):
            return {
                "function": function_name,
                "status": "unchanged",
                "message": "Deployment artifact unchanged; provider update skipped.",
                "hash": artifact_hash,
                "source_hash": source_hash,
            }

        if provider == "aws":
            lambda_name = _provider_function_name(provider, function_type, twin_name, function_name)
            result = _upload_aws_lambda(lambda_name, zip_content, project_name)
        elif provider == "azure":
            result = _upload_azure_function(app_name, zip_content, project_name)
        elif provider == "gcp":
            gcp_name = _provider_function_name(provider, function_type, twin_name, function_name)
            result = _upload_gcp_function(gcp_name, zip_content, project_name)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        if provider == "azure":
            affected_functions = mark_provider_artifact_deployed(
                Path(_get_upload_dir(project_name)),
                provider,
                artifact_hash,
            )
        else:
            evidence_recorded = mark_function_deployed(
                target,
                expected_artifact_hash=artifact_hash,
            )
            affected_functions = [metadata_name] if evidence_recorded else []
            if not evidence_recorded:
                logger.warning(
                    "Function %s was updated, but newer build evidence superseded artifact %s",
                    metadata_name,
                    artifact_hash,
                )
        
        # Invalidate cache since we made changes
        _invalidate_cache(project_name)
        
        return {
            "function": function_name,
            "status": "updated",
            "provider": provider,
            "hash": artifact_hash,
            "source_hash": source_hash,
            "affected_functions": affected_functions,
            **result
        }
    
    except FunctionProviderError as e:
        logger.warning("Function provider update failed for %s: %s", function_name, e)
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Error updating function %s: %s",
            function_name,
            redact_sensitive(e),
        )
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
