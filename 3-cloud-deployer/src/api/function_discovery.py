"""Discovery and bounded in-memory caching for user functions."""

import os
from threading import RLock
import time
from typing import Any, Dict, Optional

import constants as CONSTANTS
from logger import logger
from src.core.config_loader import ProjectConfigLoader, load_optimization_flags
from src.core.paths import resolve_project_context_path

def _get_upload_dir(project_name: str) -> str:
    """Get the upload directory path for a project."""
    return str(resolve_project_context_path(project_name))

# ==========================================
# Caching for Updatable Functions List
# ==========================================

_function_cache: Dict[str, Any] = {}
_cache_timestamps: Dict[str, float] = {}
_cache_lock = RLock()
CACHE_TTL_SECONDS = 60  # Cache expires after 60 seconds


def _invalidate_cache(project_name: str) -> None:
    """
    Invalidate the function cache for a project.
    
    Called when config files or function code changes.
    
    Args:
        project_name: Name of the project to invalidate cache for
    """
    with _cache_lock:
        _function_cache.pop(project_name, None)
        _cache_timestamps.pop(project_name, None)
    logger.info(f"Cache invalidated for project: {project_name}")


def _get_cached_functions(project_name: str) -> Optional[Dict[str, Any]]:
    """
    Get cached function list if available and not expired.
    
    Args:
        project_name: Name of the project
        
    Returns:
        Cached function data or None if cache miss/expired
    """
    with _cache_lock:
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
    with _cache_lock:
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
    bundle = ProjectConfigLoader().load_bundle(project_name)
    upload_dir = os.fspath(bundle.project_path)
    
    if not os.path.exists(upload_dir):
        raise ValueError(f"Project directory not found: {project_name}")
    events_config = bundle.config.events
    devices_config = bundle.config.iot_devices
    providers_config = bundle.config.providers
    optimization_flags = load_optimization_flags(bundle.project_path)
    
    # Validate providers_config structure
    if "layer_2_provider" not in providers_config:
        raise ValueError("Missing required key in config_providers.json: layer_2_provider")
    
    l2_provider = providers_config["layer_2_provider"]
    
    functions: Dict[str, Any] = {}
    
    # 1. Discover Event Actions from config_events.json
    for event in events_config if optimization_flags["useEventChecking"] else []:
        if "action" not in event:
            raise ValueError("Event config entry missing required 'action' field")
        
        action = event["action"]
        if action.get("type") in {"step_function", "logic_app", "workflow"}:
            continue
        if "functionName" not in action:
            raise ValueError("Event action missing required 'functionName' field")
        
        func_name = action["functionName"]
        
        # Check code existence
        if l2_provider == "aws":
            func_dir = os.path.join(
                upload_dir,
                CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME,
                CONSTANTS.EVENT_ACTIONS_DIR_NAME,
                func_name,
            )
        elif l2_provider == "azure":
            func_dir = os.path.join(upload_dir, "azure_functions", "event_actions", func_name)
        elif l2_provider in {"gcp", "google"}:
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
        
        processor_name = device["id"]
        
        if processor_name in processors_seen:
            continue
        processors_seen.add(processor_name)
        
        # Check code existence
        if l2_provider == "aws":
            proc_dir = os.path.join(upload_dir, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "processors", processor_name)
        elif l2_provider == "azure":
            proc_dir = os.path.join(upload_dir, "azure_functions", "processors", processor_name)
        elif l2_provider in {"gcp", "google"}:
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
    
    # 3. Check event-feedback only when feedback is enabled.
    if not optimization_flags["returnFeedbackToDevice"]:
        return functions

    if l2_provider == "aws":
        feedback_dir = os.path.join(upload_dir, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "event-feedback")
    elif l2_provider == "azure":
        feedback_dir = os.path.join(upload_dir, "azure_functions", "event-feedback")
    elif l2_provider in {"gcp", "google"}:
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
