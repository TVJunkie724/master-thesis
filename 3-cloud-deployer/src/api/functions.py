"""
Functions API - User Function Management Endpoints.

This module provides endpoints for querying and updating user-modifiable functions
(event actions, processors, feedback functions) across AWS and Azure deployments.

Endpoints:
- GET /updatable_functions: List all user-modifiable functions with status
- POST /update_function/{function_name}: Update a single function's code via SDK

Architecture:
    User Code (upload/<project>/) → Build ZIP → Upload via SDK (boto3/Kudu)
    
Function Types:
- Event Actions: Lambda/Azure functions triggered by events (config_events.json)
- Processors: Device data processors (from config_iot_devices.json)
- Event Feedback: Feedback function for sending responses back to devices
"""

import hashlib
import json
import os
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse

import constants as CONSTANTS
import src.core.state as state
from api.dependencies import validate_project_context, check_template_protection
from logger import logger

# Optional SDK imports - fail at runtime if SDK not available for that provider
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def _get_upload_dir(project_name: str) -> str:
    """Get the upload directory path for a project."""
    return os.path.join(state.get_project_base_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name)

router = APIRouter(prefix="/functions", tags=["Functions"])


# ==========================================
# Caching for Updatable Functions List
# ==========================================

_function_cache: Dict[str, Any] = {}
_cache_timestamps: Dict[str, float] = {}
CACHE_TTL_SECONDS = 60  # Cache expires after 60 seconds


def _invalidate_cache(project_name: str) -> None:
    """
    Invalidate the function cache for a project.
    
    Called when config files or function code changes.
    
    Args:
        project_name: Name of the project to invalidate cache for
    """
    if project_name in _function_cache:
        del _function_cache[project_name]
    if project_name in _cache_timestamps:
        del _cache_timestamps[project_name]
    logger.info(f"Cache invalidated for project: {project_name}")


def _get_cached_functions(project_name: str) -> Optional[Dict[str, Any]]:
    """
    Get cached function list if available and not expired.
    
    Args:
        project_name: Name of the project
        
    Returns:
        Cached function data or None if cache miss/expired
    """
    if project_name not in _function_cache:
        return None
    
    cache_time = _cache_timestamps.get(project_name, 0)
    if time.time() - cache_time > CACHE_TTL_SECONDS:
        _invalidate_cache(project_name)
        return None
    
    return _function_cache[project_name]


def _set_cache(project_name: str, data: Dict[str, Any]) -> None:
    """
    Store function list in cache.
    
    Args:
        project_name: Name of the project
        data: Function data to cache
    """
    _function_cache[project_name] = data
    _cache_timestamps[project_name] = time.time()


# ==========================================
# Core Function Discovery
# ==========================================

def _get_updatable_functions(project_name: str) -> Dict[str, Any]:
    """
    Discover all user-modifiable functions for a project.
    
    Cross-checks config files with actual code presence.
    
    Args:
        project_name: Name of the project
        
    Returns:
        Dict mapping function names to their metadata
        
    Raises:
        ValueError: If required configs are missing
    """
    upload_dir = _get_upload_dir(project_name)
    
    if not os.path.exists(upload_dir):
        raise ValueError(f"Project directory not found: {project_name}")
    
    # Load required config files - fail-fast if missing
    events_path = os.path.join(upload_dir, CONSTANTS.CONFIG_EVENTS_FILE)
    devices_path = os.path.join(upload_dir, CONSTANTS.CONFIG_IOT_DEVICES_FILE)
    providers_path = os.path.join(upload_dir, CONSTANTS.CONFIG_PROVIDERS_FILE)
    
    if not os.path.exists(events_path):
        raise ValueError(f"Missing required config: {CONSTANTS.CONFIG_EVENTS_FILE}")
    if not os.path.exists(devices_path):
        raise ValueError(f"Missing required config: {CONSTANTS.CONFIG_IOT_DEVICES_FILE}")
    if not os.path.exists(providers_path):
        raise ValueError(f"Missing required config: {CONSTANTS.CONFIG_PROVIDERS_FILE}")
    
    with open(events_path, 'r') as f:
        events_config = json.load(f)
    with open(devices_path, 'r') as f:
        devices_config = json.load(f)
    with open(providers_path, 'r') as f:
        providers_config = json.load(f)
    
    # Validate providers_config structure
    if "layer_2_provider" not in providers_config:
        raise ValueError("Missing required key in config_providers.json: layer_2_provider")
    
    l2_provider = providers_config["layer_2_provider"]
    
    functions: Dict[str, Any] = {}
    
    # 1. Discover Event Actions from config_events.json
    for event in events_config:
        if "action" not in event:
            raise ValueError("Event config entry missing required 'action' field")
        
        action = event["action"]
        if "functionName" not in action:
            raise ValueError("Event action missing required 'functionName' field")
        
        func_name = action["functionName"]
        
        # Check code existence
        if l2_provider == "aws":
            func_dir = os.path.join(upload_dir, CONSTANTS.EVENT_ACTIONS_DIR_NAME, func_name)
        elif l2_provider == "azure":
            func_dir = os.path.join(upload_dir, "azure_functions", "event_actions", func_name)
        elif l2_provider == "google":
            func_dir = os.path.join(upload_dir, "cloud_functions", "event_actions", func_name)
        else:
            raise ValueError(f"Unsupported layer_2_provider: {l2_provider}")
        
        code_exists = os.path.exists(func_dir)
        
        functions[func_name] = {
            "provider": l2_provider,
            "type": "event_action",
            "exists": code_exists,
            "path": func_dir,
            "auto_deploy": action.get("autoDeploy", False)
        }
        
        if not code_exists:
            functions[func_name]["error"] = f"Missing code directory: {func_dir}"
    
    # 2. Discover Processors from config_iot_devices.json
    processors_seen = set()
    for device in devices_config:
        if "id" not in device:
            raise ValueError("Device config entry missing required 'id' field")
        
        # Processor can be explicit or default
        processor_name = device.get("processor", "default_processor")
        
        if processor_name in processors_seen:
            continue
        processors_seen.add(processor_name)
        
        # Check code existence
        if l2_provider == "aws":
            proc_dir = os.path.join(upload_dir, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "processors", processor_name)
        elif l2_provider == "azure":
            proc_dir = os.path.join(upload_dir, "azure_functions", "processors", processor_name)
        elif l2_provider == "google":
            proc_dir = os.path.join(upload_dir, "cloud_functions", "processors", processor_name)
        else:
            raise ValueError(f"Unsupported layer_2_provider: {l2_provider}")
        
        code_exists = os.path.exists(proc_dir)
        
        functions[processor_name] = {
            "provider": l2_provider,
            "type": "processor",
            "exists": code_exists,
            "path": proc_dir
        }
        
        if not code_exists:
            functions[processor_name]["error"] = f"Missing code directory: {proc_dir}"
    
    # 3. Check event-feedback function (always required for L2)
    if l2_provider == "aws":
        feedback_dir = os.path.join(upload_dir, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "event-feedback")
    elif l2_provider == "azure":
        feedback_dir = os.path.join(upload_dir, "azure_functions", "event-feedback")
    elif l2_provider == "google":
        feedback_dir = os.path.join(upload_dir, "cloud_functions", "event-feedback")
    else:
        raise ValueError(f"Unsupported layer_2_provider: {l2_provider}")
    
    feedback_exists = os.path.exists(feedback_dir)
    functions["event-feedback"] = {
        "provider": l2_provider,
        "type": "feedback",
        "exists": feedback_exists,
        "path": feedback_dir
    }
    if not feedback_exists:
        functions["event-feedback"]["error"] = f"Missing code directory: {feedback_dir}"
    
    return functions


# ==========================================
# ZIP Building and Hash Computation
# ==========================================

def _compute_directory_hash(dir_path: str) -> str:
    """
    Compute SHA256 hash of all files in a directory.
    
    Args:
        dir_path: Path to directory to hash
        
    Returns:
        SHA256 hash string prefixed with 'sha256:'
        
    Raises:
        ValueError: If directory doesn't exist
    """
    if not os.path.exists(dir_path):
        raise ValueError(f"Directory not found: {dir_path}")
    
    hasher = hashlib.sha256()
    
    for root, dirs, files in sorted(os.walk(dir_path)):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        
        for filename in sorted(files):
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, dir_path)
            
            # Hash the relative path
            hasher.update(rel_path.encode('utf-8'))
            
            # Hash the file content
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
    
    return f"sha256:{hasher.hexdigest()}"


def _build_function_zip(func_dir: str, shared_dir: Optional[str] = None) -> bytes:
    """
    Build a deployment ZIP for a function.
    
    Args:
        func_dir: Path to function code directory
        shared_dir: Optional path to shared modules to include
        
    Returns:
        ZIP file content as bytes
        
    Raises:
        ValueError: If function directory doesn't exist
    """
    if not os.path.exists(func_dir):
        raise ValueError(f"Function directory not found: {func_dir}")
    
    buffer = BytesIO()
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add function files
        for root, dirs, files in os.walk(func_dir):
            # Skip __pycache__
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            
            for filename in files:
                if filename.endswith('.pyc'):
                    continue
                
                filepath = os.path.join(root, filename)
                arcname = os.path.relpath(filepath, func_dir)
                zf.write(filepath, arcname)
        
        # Add shared modules if provided
        if shared_dir and os.path.exists(shared_dir):
            for root, dirs, files in os.walk(shared_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                
                for filename in files:
                    if filename.endswith('.pyc'):
                        continue
                    
                    filepath = os.path.join(root, filename)
                    arcname = os.path.relpath(filepath, shared_dir)
                    zf.write(filepath, arcname)
    
    return buffer.getvalue()


# ==========================================
# SDK Upload Functions
# ==========================================

def _upload_aws_lambda(function_name: str, zip_content: bytes, project_name: str) -> Dict[str, Any]:
    """
    Upload function code to AWS Lambda via boto3.
    
    Args:
        function_name: Name of the Lambda function
        zip_content: ZIP file content
        project_name: Name of the project (for getting credentials)
        
    Returns:
        Dict with upload result
        
    Raises:
        ValueError: If boto3 not available or credentials missing
    """
    if not HAS_BOTO3:
        raise ValueError("boto3 not installed - cannot upload to AWS Lambda")
    
    upload_dir = _get_upload_dir(project_name)
    creds_path = os.path.join(upload_dir, CONSTANTS.CONFIG_CREDENTIALS_FILE)
    
    if not os.path.exists(creds_path):
        raise ValueError(f"Missing credentials file: {CONSTANTS.CONFIG_CREDENTIALS_FILE}")
    
    with open(creds_path, 'r') as f:
        creds = json.load(f)
    
    # Validate required AWS credentials
    required = ["aws_access_key_id", "aws_secret_access_key", "aws_region"]
    for key in required:
        if key not in creds:
            raise ValueError(f"Missing required AWS credential: {key}")
    
    lambda_client = boto3.client(
        'lambda',
        aws_access_key_id=creds["aws_access_key_id"],
        aws_secret_access_key=creds["aws_secret_access_key"],
        region_name=creds["aws_region"]
    )
    
    try:
        response = lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_content,
            Publish=True
        )
        logger.info(f"✓ AWS Lambda code updated: {function_name}")
        return {
            "success": True,
            "function_arn": response.get("FunctionArn"),
            "version": response.get("Version")
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        if error_code == "ResourceNotFoundException":
            raise ValueError(f"Lambda function not found: {function_name}. Deploy infrastructure first.")
        else:
            raise ValueError(f"AWS Lambda update failed: {error_code} - {error_msg}")


def _upload_azure_function(function_app_name: str, zip_content: bytes, project_name: str) -> Dict[str, Any]:
    """
    Upload function code to Azure Function App via Kudu zipdeploy.
    
    Args:
        function_app_name: Name of the Azure Function App
        zip_content: ZIP file content
        project_name: Name of the project (for getting credentials)
        
    Returns:
        Dict with upload result
        
    Raises:
        ValueError: If requests not available or credentials missing
    """
    if not HAS_REQUESTS:
        raise ValueError("requests library not installed - cannot upload to Azure")
    
    upload_dir = _get_upload_dir(project_name)
    creds_path = os.path.join(upload_dir, CONSTANTS.CONFIG_CREDENTIALS_FILE)
    
    if not os.path.exists(creds_path):
        raise ValueError(f"Missing credentials file: {CONSTANTS.CONFIG_CREDENTIALS_FILE}")
    
    with open(creds_path, 'r') as f:
        creds = json.load(f)
    
    # Validate required Azure credentials
    required = ["azure_subscription_id", "azure_tenant_id", "azure_client_id", "azure_client_secret"]
    for key in required:
        if key not in creds:
            raise ValueError(f"Missing required Azure credential: {key}")
    
    # Get Azure publish credentials via Management API
    # First, get access token
    token_url = f"https://login.microsoftonline.com/{creds['azure_tenant_id']}/oauth2/v2.0/token"
    token_data = {
        "client_id": creds["azure_client_id"],
        "client_secret": creds["azure_client_secret"],
        "scope": "https://management.azure.com/.default",
        "grant_type": "client_credentials"
    }
    
    token_response = requests.post(token_url, data=token_data, timeout=30)
    if token_response.status_code != 200:
        raise ValueError(f"Failed to get Azure access token: {token_response.text}")
    
    access_token = token_response.json()["access_token"]
    
    # Get publish credentials for the Function App
    # We need to find the resource group - check inter_cloud config or use naming convention
    inter_cloud_path = os.path.join(upload_dir, CONSTANTS.CONFIG_INTER_CLOUD_FILE)
    resource_group = None
    
    if os.path.exists(inter_cloud_path):
        with open(inter_cloud_path, 'r') as f:
            inter_cloud = json.load(f)
            resource_group = inter_cloud.get("azure_resource_group")
    
    if not resource_group:
        # Try to derive from config.json
        config_path = os.path.join(upload_dir, CONSTANTS.CONFIG_FILE)
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                if "digital_twin_name" not in config:
                    raise ValueError(f"Missing digital_twin_name in {CONSTANTS.CONFIG_FILE}")
                resource_group = f"{config['digital_twin_name']}-rg"
        else:
            raise ValueError("Cannot determine Azure resource group - missing config.json")
    
    # Get publish credentials
    creds_url = (
        f"https://management.azure.com/subscriptions/{creds['azure_subscription_id']}"
        f"/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{function_app_name}"
        f"/config/publishingcredentials/list?api-version=2022-03-01"
    )
    
    creds_response = requests.post(
        creds_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30
    )
    
    if creds_response.status_code != 200:
        raise ValueError(f"Failed to get Azure publish credentials: {creds_response.text}")
    
    pub_creds = creds_response.json()
    pub_user = pub_creds["properties"]["publishingUserName"]
    pub_pass = pub_creds["properties"]["publishingPassword"]
    
    # Deploy via Kudu zipdeploy
    kudu_url = f"https://{function_app_name}.scm.azurewebsites.net/api/zipdeploy"
    
    deploy_response = requests.post(
        kudu_url,
        data=zip_content,
        auth=(pub_user, pub_pass),
        headers={"Content-Type": "application/zip"},
        timeout=300
    )
    
    if deploy_response.status_code not in (200, 202):
        raise ValueError(f"Kudu zipdeploy failed: {deploy_response.status_code} - {deploy_response.text}")
    
    logger.info(f"✓ Azure Function code updated: {function_app_name}")
    return {
        "success": True,
        "function_app": function_app_name
    }


# ==========================================
# Hash Metadata Storage
# ==========================================

def _get_metadata_path(project_name: str, function_name: str, provider: str) -> str:
    """
    Get path to hash metadata file for a function.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        provider: Provider name (aws/azure)
        
    Returns:
        Path to metadata JSON file
    """
    upload_dir = _get_upload_dir(project_name)
    metadata_dir = os.path.join(upload_dir, ".build", "metadata")
    return os.path.join(metadata_dir, f"{function_name}.{provider}.json")


def _save_hash_metadata(
    project_name: str, 
    function_name: str, 
    provider: str, 
    code_hash: str
) -> None:
    """
    Save hash metadata for a deployed function.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        provider: Provider name
        code_hash: SHA256 hash of the function code
    """
    import datetime
    
    metadata_path = _get_metadata_path(project_name, function_name, provider)
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    
    metadata = {
        "function": function_name,
        "provider": provider,
        "zip_hash": code_hash,
        "last_deployed": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Saved hash metadata: {metadata_path}")


def _get_hash_metadata(project_name: str, function_name: str, provider: str) -> Optional[Dict[str, Any]]:
    """
    Load hash metadata for a function if it exists.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        provider: Provider name
        
    Returns:
        Metadata dict or None if not found
    """
    metadata_path = _get_metadata_path(project_name, function_name, provider)
    
    if not os.path.exists(metadata_path):
        return None
    
    with open(metadata_path, 'r') as f:
        return json.load(f)


def _delete_hash_metadata(project_name: str, function_name: str, provider: str) -> None:
    """
    Delete hash metadata for a function.
    
    Args:
        project_name: Name of the project
        function_name: Name of the function
        provider: Provider name
    """
    metadata_path = _get_metadata_path(project_name, function_name, provider)
    
    if os.path.exists(metadata_path):
        os.remove(metadata_path)
        logger.info(f"Deleted hash metadata: {metadata_path}")


def clear_all_hash_metadata(project_name: str) -> None:
    """
    Clear all hash metadata for a project.
    
    Called when project ZIP is fully replaced.
    
    Args:
        project_name: Name of the project
    """
    upload_dir = _get_upload_dir(project_name)
    metadata_dir = os.path.join(upload_dir, ".build", "metadata")
    
    if os.path.exists(metadata_dir):
        import shutil
        shutil.rmtree(metadata_dir)
        logger.info(f"Cleared all hash metadata for project: {project_name}")
    
    # Also invalidate cache
    _invalidate_cache(project_name)


# ==========================================
# API Endpoints
# ==========================================

@router.get(
    "/updatable_functions",
    tags=["Functions"],
    summary="List user-modifiable functions",
    responses={
        200: {"description": "Function list retrieved successfully"},
        400: {"description": "Invalid project or missing config"}
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
    validate_project_context(project_name)
    
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
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/update_function/{function_name}",
    tags=["Functions"],
    summary="Update function code via SDK",
    responses={
        200: {"description": "Function updated successfully"},
        400: {"description": "Invalid function or missing code"},
        500: {"description": "SDK upload failed"}
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
    # Protect template project from modifications
    check_template_protection(project_name, "update function in")
    
    validate_project_context(project_name)
    
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
        
        # Step 4: Build ZIP
        shared_dir = None
        if provider == "aws":
            # Include shared modules for AWS Lambda
            shared_dir = str(Path(__file__).parent.parent / "providers" / "aws" / "lambda_functions" / "_shared")
        
        zip_content = _build_function_zip(func_dir, shared_dir)
        
        # Step 5: Upload via SDK
        if provider == "aws":
            # For AWS, we need to construct the full Lambda name
            # This depends on the digital_twin_name from config
            upload_dir = _get_upload_dir(project_name)
            config_path = os.path.join(upload_dir, CONSTANTS.CONFIG_FILE)
            
            if not os.path.exists(config_path):
                raise ValueError(f"Missing config file: {CONSTANTS.CONFIG_FILE}")
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            if "digital_twin_name" not in config:
                raise ValueError(f"Missing digital_twin_name in {CONSTANTS.CONFIG_FILE}")
            
            twin_name = config["digital_twin_name"]
            
            # Construct Lambda function name based on type
            if func_info["type"] == "event_action":
                lambda_name = f"{twin_name}-l2-{function_name}"
            elif func_info["type"] == "processor":
                lambda_name = f"{twin_name}-l2-processor-{function_name}"
            elif func_info["type"] == "feedback":
                lambda_name = f"{twin_name}-l2-event-feedback"
            else:
                raise ValueError(f"Unknown function type: {func_info['type']}")
            
            result = _upload_aws_lambda(lambda_name, zip_content, project_name)
            
        elif provider == "azure":
            # For Azure, construct Function App name
            upload_dir = _get_upload_dir(project_name)
            config_path = os.path.join(upload_dir, CONSTANTS.CONFIG_FILE)
            
            if not os.path.exists(config_path):
                raise ValueError(f"Missing config file: {CONSTANTS.CONFIG_FILE}")
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            if "digital_twin_name" not in config:
                raise ValueError(f"Missing digital_twin_name in {CONSTANTS.CONFIG_FILE}")
            
            twin_name = config["digital_twin_name"]
            
            # Azure Function Apps group functions by layer
            if func_info["type"] == "event_action":
                app_name = f"{twin_name}-l2-event-actions"
            elif func_info["type"] == "processor":
                app_name = f"{twin_name}-l2-processors"
            elif func_info["type"] == "feedback":
                app_name = f"{twin_name}-l2-feedback"
            else:
                raise ValueError(f"Unknown function type: {func_info['type']}")
            
            result = _upload_azure_function(app_name, zip_content, project_name)
            
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
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating function {function_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# ==========================================
# Build Function ZIP Endpoint
# ==========================================

import ast


def _validate_python_syntax(content: bytes, filename: str) -> None:
    """
    Validate Python syntax using AST parsing.
    
    Args:
        content: Python file content as bytes
        filename: Name of the file (for error messages)
        
    Raises:
        ValueError: If syntax is invalid
    """
    try:
        ast.parse(content.decode('utf-8'))
    except SyntaxError as e:
        raise ValueError(f"Python syntax error in {filename}: {e.msg} (line {e.lineno})")
    except UnicodeDecodeError as e:
        raise ValueError(f"Invalid encoding in {filename}: {e}")


def _validate_entry_point(content: bytes, provider: str) -> None:
    """
    Validate that the function has a valid entry point.
    
    Args:
        content: Python file content as bytes
        provider: Cloud provider (aws, azure, google)
        
    Raises:
        ValueError: If entry point is missing
    """
    source = content.decode('utf-8')
    tree = ast.parse(source)
    
    # Extract function names
    function_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    
    # Check for expected entry points by provider
    if provider == "aws":
        valid_entries = ["handler", "lambda_handler"]
        if not any(name in function_names for name in valid_entries):
            raise ValueError(
                f"AWS Lambda requires 'handler(event, context)' or 'lambda_handler(event, context)'. "
                f"Found functions: {function_names}"
            )
    elif provider == "azure":
        # Azure Functions use decorators, check for any function
        if not function_names:
            raise ValueError("No functions found in the file. Azure Functions require at least one function.")
    elif provider == "google":
        # GCP Cloud Functions use a specific entry point
        valid_entries = ["main", "handler", "hello_http"]
        if not any(name in function_names for name in valid_entries):
            raise ValueError(
                f"GCP Cloud Functions require 'main(request)' or 'handler(request)'. "
                f"Found functions: {function_names}"
            )


def _build_aws_zip(function_content: bytes, requirements_content: bytes = None) -> bytes:
    """Build AWS Lambda deployment ZIP."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", function_content)
        if requirements_content:
            zf.writestr("requirements.txt", requirements_content)
    buffer.seek(0)
    return buffer.getvalue()


def _build_azure_zip(function_content: bytes, requirements_content: bytes = None) -> bytes:
    """Build Azure Function deployment ZIP."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add function code
        zf.writestr("function_app.py", function_content)
        
        # Add host.json
        host_json = {
            "version": "2.0",
            "extensionBundle": {
                "id": "Microsoft.Azure.Functions.ExtensionBundle",
                "version": "[4.*, 5.0.0)"
            }
        }
        zf.writestr("host.json", json.dumps(host_json, indent=2))
        
        # Add requirements.txt
        if requirements_content:
            zf.writestr("requirements.txt", requirements_content)
        else:
            zf.writestr("requirements.txt", "azure-functions\n")
    
    buffer.seek(0)
    return buffer.getvalue()


def _build_gcp_zip(function_content: bytes, requirements_content: bytes = None) -> bytes:
    """Build GCP Cloud Function deployment ZIP."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add function code
        zf.writestr("main.py", function_content)
        
        # Add requirements.txt
        if requirements_content:
            zf.writestr("requirements.txt", requirements_content)
        else:
            zf.writestr("requirements.txt", "functions-framework\n")
    
    buffer.seek(0)
    return buffer.getvalue()


@router.post(
    "/build",
    tags=["Functions"],
    summary="Build function deployment ZIP",
    responses={
        200: {"description": "ZIP file download", "content": {"application/zip": {}}},
        400: {"description": "Validation failed - syntax error or missing entry point"},
        422: {"description": "Invalid file upload"}
    }
)
async def build_function_zip(
    provider: str = Query(..., description="Cloud provider: aws, azure, or google"),
    function_file: UploadFile = File(..., description="Python function file (.py)"),
    requirements_file: UploadFile = File(None, description="Optional requirements.txt")
):
    """
    Build a cloud-ready deployment ZIP from a Python function file.
    
    **Validation performed:**
    - Python syntax check (AST parsing)
    - Entry point validation by provider:
      - AWS: `handler(event, context)` or `lambda_handler(event, context)`
      - Azure: Any function (uses decorators)
      - Google: `main(request)` or `handler(request)`
    
    **ZIP contents by provider:**
    - **AWS**: `lambda_function.py` + optional `requirements.txt`
    - **Azure**: `function_app.py` + `host.json` + `requirements.txt`
    - **Google**: `main.py` + `requirements.txt`
    
    **Returns:** ZIP file download ready for cloud deployment.
    """
    # Validate provider
    provider = provider.lower()
    if provider not in ("aws", "azure", "google"):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid provider: {provider}. Must be aws, azure, or google."
        )
    
    # Validate file extension
    if not function_file.filename.endswith('.py'):
        raise HTTPException(
            status_code=400,
            detail=f"Function file must be a Python file (.py). Got: {function_file.filename}"
        )
    
    try:
        # Read function file
        function_content = await function_file.read()
        
        if not function_content:
            raise HTTPException(status_code=400, detail="Function file is empty")
        
        # Validate Python syntax
        _validate_python_syntax(function_content, function_file.filename)
        
        # Validate entry point
        _validate_entry_point(function_content, provider)
        
        # Read optional requirements file
        requirements_content = None
        if requirements_file:
            requirements_content = await requirements_file.read()
        
        # Build ZIP based on provider
        if provider == "aws":
            zip_content = _build_aws_zip(function_content, requirements_content)
            filename = "lambda_function.zip"
        elif provider == "azure":
            zip_content = _build_azure_zip(function_content, requirements_content)
            filename = "azure_function.zip"
        else:  # google
            zip_content = _build_gcp_zip(function_content, requirements_content)
            filename = "cloud_function.zip"
        
        # Return as downloadable ZIP
        return StreamingResponse(
            BytesIO(zip_content),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error building function ZIP: {e}")
        raise HTTPException(status_code=500, detail=str(e))
