"""Discovery and bounded in-memory caching for user functions."""

from copy import deepcopy
from pathlib import Path
from threading import RLock
import time
from typing import Any, Dict, Optional

import constants as CONSTANTS
from logger import logger
from src.core.config_loader import (
    ProjectConfigLoader,
    load_optimization_flags,
    normalize_provider_name,
)
from src.core.paths import resolve_project_context_path, validate_path_component

SUPPORTED_FUNCTION_PROVIDERS = frozenset({"aws", "azure", "gcp"})
FUNCTION_SOURCE_ROOTS = {
    "aws": "lambda_functions",
    "azure": "azure_functions",
    "gcp": "cloud_functions",
}

def _get_upload_dir(project_name: str) -> str:
    """Get the upload directory path for a project."""
    return str(resolve_project_context_path(project_name))


def _source_directory(
    project_path: Path,
    provider: str,
    category: str,
    function_name: str | None = None,
) -> Path:
    """Resolve a validated source directory below the provider-owned root."""
    if provider not in SUPPORTED_FUNCTION_PROVIDERS:
        raise ValueError(f"Unsupported layer_2_provider: {provider}")
    validate_path_component(category, "function category")
    parts = [FUNCTION_SOURCE_ROOTS[provider], category]
    if function_name is not None:
        parts.append(validate_path_component(function_name, "function name"))
    candidate = project_path.joinpath(*parts)
    current = project_path
    for part in parts:
        current /= part
        if current.is_symlink():
            raise ValueError("Function source path cannot contain symbolic links")
    try:
        candidate.resolve().relative_to(project_path.resolve())
    except (OSError, ValueError) as exc:
        raise ValueError("Function source path escaped the project boundary") from exc
    return candidate


def _register_function(
    functions: Dict[str, Any],
    function_name: str,
    descriptor: Dict[str, Any],
) -> None:
    if function_name in functions:
        raise ValueError(f"Duplicate function name across configuration: {function_name}")
    functions[function_name] = descriptor

# ==========================================
# Caching for Updatable Functions List
# ==========================================

_function_cache: Dict[str, Any] = {}
_cache_timestamps: Dict[str, float] = {}
_cache_lock = RLock()
CACHE_TTL_SECONDS = 60  # Cache expires after 60 seconds
MAX_CACHE_ENTRIES = 128


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
        if time.monotonic() - cache_time > CACHE_TTL_SECONDS:
            _function_cache.pop(project_name, None)
            _cache_timestamps.pop(project_name, None)
            return None

        return deepcopy(_function_cache[project_name])


def _set_cache(project_name: str, data: Dict[str, Any]) -> None:
    """
    Store function list in cache.
    
    Args:
        project_name: Name of the project
        data: Function data to cache
    """
    with _cache_lock:
        if project_name not in _function_cache and len(_function_cache) >= MAX_CACHE_ENTRIES:
            oldest = min(_cache_timestamps, key=_cache_timestamps.get)
            _function_cache.pop(oldest, None)
            _cache_timestamps.pop(oldest, None)
        _function_cache[project_name] = deepcopy(data)
        _cache_timestamps[project_name] = time.monotonic()


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
    project_path = bundle.project_path

    if project_path.is_symlink() or not project_path.is_dir():
        raise ValueError(f"Project directory not found: {project_name}")
    events_config = bundle.config.events
    devices_config = bundle.config.iot_devices
    providers_config = bundle.config.providers
    optimization_flags = load_optimization_flags(bundle.project_path)
    
    # Validate providers_config structure
    if "layer_2_provider" not in providers_config:
        raise ValueError("Missing required key in config_providers.json: layer_2_provider")
    
    configured_provider = providers_config["layer_2_provider"]
    if not isinstance(configured_provider, str):
        raise ValueError("layer_2_provider must be a string")
    l2_provider = normalize_provider_name(configured_provider)
    if l2_provider not in SUPPORTED_FUNCTION_PROVIDERS:
        raise ValueError(f"Unsupported layer_2_provider: {l2_provider}")
    
    functions: Dict[str, Any] = {}
    
    # 1. Discover Event Actions from config_events.json
    for event in events_config if optimization_flags["useEventChecking"] else []:
        if not isinstance(event, dict) or not isinstance(event.get("action"), dict):
            raise ValueError("Event config entry requires an action object")

        action = event["action"]
        if action.get("type") in {"step_function", "logic_app", "workflow"}:
            continue
        func_name = action.get("functionName")
        if not isinstance(func_name, str) or not func_name:
            raise ValueError("Event action requires a non-empty functionName")
        func_dir = _source_directory(
            project_path,
            l2_provider,
            CONSTANTS.EVENT_ACTIONS_DIR_NAME,
            func_name,
        )
        code_exists = func_dir.is_dir() and not func_dir.is_symlink()

        descriptor = {
            "provider": l2_provider,
            "type": "event_action",
            "exists": code_exists,
            "path": str(func_dir),
            "auto_deploy": (
                action.get("autoDeploy")
                if isinstance(action.get("autoDeploy"), bool)
                else False
            ),
        }
        if not code_exists:
            descriptor["error"] = "Function source directory is missing"
        _register_function(functions, func_name, descriptor)
    
    # 2. Discover Processors from config_iot_devices.json
    processors_seen = set()
    for device in devices_config:
        processor_name = device.get("id") if isinstance(device, dict) else None
        if not isinstance(processor_name, str) or not processor_name:
            raise ValueError("Device config entry requires a non-empty id")
        validate_path_component(processor_name, "device id")
        
        if processor_name in processors_seen:
            continue
        processors_seen.add(processor_name)
        
        proc_dir = _source_directory(
            project_path,
            l2_provider,
            "processors",
            processor_name,
        )
        code_exists = proc_dir.is_dir() and not proc_dir.is_symlink()

        descriptor = {
            "provider": l2_provider,
            "type": "processor",
            "exists": code_exists,
            "path": str(proc_dir)
        }
        if not code_exists:
            descriptor["error"] = "Function source directory is missing"
        _register_function(functions, processor_name, descriptor)
    
    # 3. Check event-feedback only when feedback is enabled.
    if not optimization_flags["returnFeedbackToDevice"]:
        return functions

    feedback_dir = _source_directory(project_path, l2_provider, "event-feedback")
    feedback_exists = feedback_dir.is_dir() and not feedback_dir.is_symlink()
    descriptor = {
        "provider": l2_provider,
        "type": "feedback",
        "exists": feedback_exists,
        "path": str(feedback_dir)
    }
    if not feedback_exists:
        descriptor["error"] = "Function source directory is missing"
    _register_function(functions, "event-feedback", descriptor)
    
    return functions
