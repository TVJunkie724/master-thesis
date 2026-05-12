# src/services/deployment_service.py
"""
Deployment services extracted from twins.py route handlers.

This module provides:
- Real deployment streaming functions (subscribe to Deployer SSE)
- Build deployment config helper
- Project ZIP building and upload (production deployment flow)
- Shared constants and error handling

These functions were previously embedded in twins.py but are now
centralized for reusability and maintainability.
"""

import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
import httpx
from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

from src.config import settings
from src.repositories.deployment_repository import DeploymentRepository
from src.services.credential_resolution_service import CredentialResolutionService, DeploymentCredentials

if TYPE_CHECKING:
    from src.models.deployer_config import DeployerConfiguration
    from src.models.optimizer_config import OptimizerConfiguration

logger = logging.getLogger(__name__)

# Deployer API URL from settings
DEPLOYER_API_URL = getattr(settings, 'DEPLOYER_URL', 'http://3cloud-deployer:8000')
DEPLOYMENT_MANIFEST_FILE = "deployment_manifest.json"
DEPLOYMENT_MANIFEST_VERSION = "1.0"
REQUIRED_DEPLOYER_CONFIG_FILES = [
    "config.json",
    "config_iot_devices.json",
    "config_events.json",
    "config_credentials.json",
    "config_providers.json",
]

SECRET_FRAGMENT_PATTERN = re.compile(
    r"(?i)"
    r"(\b(?:aws_access_key_id|aws_secret_access_key|azure_client_secret|"
    r"client_secret|private_key|private_key_id|token|access_token|refresh_token|"
    r"password|secret|api_key|access_key)\b)"
    r"([\"']?\s*[:=]\s*[\"']?)"
    r"([^\"',\s}\]]+)"
)
PROJECT_PATH_PATTERN = re.compile(r"(/[^\s:]+/upload/[^\s:]+)")
WORKSPACE_PATH_PATTERN = re.compile(r"(/[^\s:]+/twin2multicloud-deployer-workspaces/[^\s:]+)")


@dataclass(frozen=True)
class DeployerStreamResult:
    """Terminal result parsed from the Deployer SSE contract."""

    success: bool
    operation_id: str | None = None
    error_code: str | None = None
    message: str | None = None
    outputs: dict[str, Any] | None = None


def build_deploy_config(twin) -> dict:
    """
    Build the config.json payload from saved configurations.
    
    Combines:
    - OptimizerConfiguration (layer providers, parameters)
    - DeployerConfiguration (config files, user functions)
    
    Args:
        twin: DigitalTwin model instance with related configs
        
    Returns:
        dict: Configuration payload ready for Deployer API
    """
    config = {
        "resource_name": twin.name.lower().replace(" ", "-"),
        "twin_id": twin.id,
    }
    
    # Add from deployer config
    if twin.deployer_config:
        dc = twin.deployer_config
        config["resource_name"] = dc.deployer_digital_twin_name or config["resource_name"]
        
        # Parse JSON fields
        if dc.config_events_json:
            config["config_events"] = json.loads(dc.config_events_json)
        if dc.config_iot_devices_json:
            config["config_iot_devices"] = json.loads(dc.config_iot_devices_json)
        if dc.payloads_json:
            config["payloads"] = json.loads(dc.payloads_json)
        if dc.state_machine_content:
            config["state_machine"] = dc.state_machine_content
        if dc.hierarchy_content:
            config["hierarchy"] = dc.hierarchy_content
        if dc.scene_config_content:
            config["scene_config"] = dc.scene_config_content
        if dc.user_config_content:
            config["user_config"] = dc.user_config_content
        
        # User functions
        if dc.processor_contents:
            config["processors"] = json.loads(dc.processor_contents)
        if dc.event_feedback_content:
            config["event_feedback"] = dc.event_feedback_content
        if dc.event_action_contents:
            config["event_actions"] = json.loads(dc.event_action_contents)
    
    # Add from optimizer config
    if twin.optimizer_config:
        oc = twin.optimizer_config
        config["layers"] = {
            "l1": oc.cheapest_l1,
            "l2": oc.cheapest_l2,
            "l3_hot": oc.cheapest_l3_hot,
            "l3_cool": oc.cheapest_l3_cool,
            "l3_archive": oc.cheapest_l3_archive,
            "l4": oc.cheapest_l4,
            "l5": oc.cheapest_l5,
        }
        if oc.result_json:
            config["optimizer_result"] = json.loads(oc.result_json)
    
    return config


def _redact_deployment_message(value: Any) -> str:
    """Return a client-safe deployment message without path or secret leakage."""
    text = str(value)
    text = SECRET_FRAGMENT_PATTERN.sub(r"\1\2[REDACTED]", text)
    text = PROJECT_PATH_PATTERN.sub("<project-path>", text)
    text = WORKSPACE_PATH_PATTERN.sub("<workspace-path>", text)
    return text


def _parse_deployer_sse_data(
    raw_data: str,
    event_type: str | None,
    operation_type: str,
) -> tuple[str | None, DeployerStreamResult | None]:
    """
    Parse one Deployer SSE data line.

    Returns `(log_message, terminal_result)`. Only one side is populated.
    """
    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError:
        if event_type in {"complete", "error"}:
            return None, DeployerStreamResult(
                success=event_type == "complete",
                message=_redact_deployment_message(raw_data),
                error_code=None if event_type == "complete" else "DEPLOYER_STREAM_ERROR",
            )
        return _redact_deployment_message(raw_data), None

    if not isinstance(payload, dict):
        return _redact_deployment_message(raw_data), None

    payload_event = payload.get("event") or event_type
    if payload_event in {"complete", "error"}:
        success = bool(payload.get("success", payload_event == "complete"))
        message = (
            payload.get("message")
            or payload.get("error")
            or (
                f"{operation_type.capitalize()} complete"
                if success else f"{operation_type.capitalize()} failed"
            )
        )
        return None, DeployerStreamResult(
            success=success,
            operation_id=payload.get("operation_id"),
            error_code=payload.get("error_code"),
            message=_redact_deployment_message(message),
            outputs=payload.get("outputs") or {},
        )

    message = payload.get("message") if payload.get("event") == "log" else None
    if message is None:
        message = raw_data
    return _redact_deployment_message(message), None


def _result_message(
    result: DeployerStreamResult | None,
    *,
    success_message: str,
    failure_message: str,
) -> str:
    if result and result.message:
        return result.message
    return success_message if result and result.success else failure_message


async def run_real_deploy_stream(
    session_id: str,
    twin_id: str,
    resource_name: str,
    provider: str
):
    """
    Background task that subscribes to Deployer SSE and forwards logs.
    Updates Deployment record on completion.
    
    Args:
        session_id: SSE session ID for pushing logs to client
        twin_id: ID of the twin being deployed
        resource_name: Deployer project/resource name
        provider: Cloud provider (aws, azure, gcp)
    """
    # Late imports to avoid circular dependencies
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin, TwinState
    
    session = await get_session(session_id)
    if not session:
        return
    
    db = SessionLocal()
    DeploymentRepository(db).create_running(
        twin_id=twin_id,
        session_id=session_id,
        operation_type="deploy",
    )
    db.commit()
    db.close()
    
    terraform_outputs = {}
    terminal_result: DeployerStreamResult | None = None
    current_event_type: str | None = None
    
    try:
        # Subscribe to Deployer SSE with long timeouts
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{DEPLOYER_API_URL}/infrastructure/deploy/stream",
                params={"provider": provider, "project_name": resource_name}
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        current_event_type = line[7:].strip()
                        continue
                    if line.startswith("data: "):
                        log_message, result = _parse_deployer_sse_data(
                            line[6:],
                            current_event_type,
                            "deploy",
                        )
                        current_event_type = None
                        if result:
                            terminal_result = result
                            if result.success and result.outputs:
                                terraform_outputs = result.outputs
                        elif log_message:
                            print(log_message, flush=True)
                            await session.push_log(log_message)
        
        deploy_success = bool(terminal_result and terminal_result.success)
        error_message = _result_message(
            terminal_result,
            success_message="Deployment complete",
            failure_message="Deployment stream ended without terminal result",
        )

        db = SessionLocal()
        try:
            twin = db.get(DigitalTwin, twin_id)
            repository = DeploymentRepository(db)
            deployment = repository.get_by_session_id(session_id)
            if twin:
                if deploy_success:
                    twin.state = TwinState.DEPLOYED
                    twin.deployed_at = datetime.utcnow()
                else:
                    twin.state = TwinState.ERROR
                    twin.last_error = error_message
            
            if deployment:
                if deploy_success:
                    repository.mark_success(
                        deployment,
                        terraform_outputs=terraform_outputs,
                        operation_id=terminal_result.operation_id if terminal_result else None,
                    )
                else:
                    repository.mark_failed(
                        deployment,
                        error_message=error_message,
                        terraform_outputs=terraform_outputs,
                        operation_id=terminal_result.operation_id if terminal_result else None,
                        error_code=(
                            terminal_result.error_code
                            if terminal_result and terminal_result.error_code
                            else "DEPLOYER_STREAM_ERROR"
                        ),
                    )
            db.commit()  # Single atomic commit
        finally:
            db.close()
        
        session.on_complete(
            success=deploy_success,
            message=error_message,
            outputs=terraform_outputs,
            operation_id=terminal_result.operation_id if terminal_result else None,
            error_code=None if deploy_success else (
                terminal_result.error_code
                if terminal_result and terminal_result.error_code
                else "DEPLOYER_STREAM_ERROR"
            ),
        )
        
    except Exception as e:
        deploy_success = bool(terminal_result and terminal_result.success)
        safe_error = _redact_deployment_message(e)
        logger.error("Deploy stream error (success=%s): %s", deploy_success, safe_error)
        db = SessionLocal()
        try:
            twin = db.get(DigitalTwin, twin_id)
            if twin and not deploy_success:
                twin.state = TwinState.ERROR
                twin.last_error = safe_error
            elif twin and deploy_success:
                twin.state = TwinState.DEPLOYED
                twin.deployed_at = datetime.utcnow()
            
            repository = DeploymentRepository(db)
            deployment = repository.get_by_session_id(session_id)
            if deployment:
                if deploy_success:
                    repository.mark_success(
                        deployment,
                        terraform_outputs=terraform_outputs,
                        operation_id=terminal_result.operation_id if terminal_result else None,
                    )
                else:
                    repository.mark_failed(
                        deployment,
                        error_message=safe_error,
                        terraform_outputs=terraform_outputs,
                        operation_id=terminal_result.operation_id if terminal_result else None,
                        error_code=(
                            terminal_result.error_code
                            if terminal_result and terminal_result.error_code
                            else "BACKEND_STREAM_ERROR"
                        ),
                    )
            db.commit()
        finally:
            db.close()
        
        if not deploy_success:
            await session.push_log(f"Deployment error: {safe_error}", level="error")
        session.on_complete(
            success=deploy_success,
            message=safe_error if not deploy_success else "Deployment complete",
            outputs=terraform_outputs if deploy_success else {},
            operation_id=terminal_result.operation_id if terminal_result else None,
            error_code=None if deploy_success else (
                terminal_result.error_code
                if terminal_result and terminal_result.error_code
                else "BACKEND_STREAM_ERROR"
            ),
        )


async def run_real_destroy_stream(
    session_id: str,
    twin_id: str,
    resource_name: str,
    provider: str
):
    """
    Background task that subscribes to Deployer destroy SSE and forwards logs.
    
    Args:
        session_id: SSE session ID for pushing logs to client
        twin_id: ID of the twin being destroyed
        resource_name: Deployer project/resource name
        provider: Cloud provider (aws, azure, gcp)
    """
    # Late imports to avoid circular dependencies
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin, TwinState
    
    session = await get_session(session_id)
    if not session:
        return
    
    db = SessionLocal()
    DeploymentRepository(db).create_running(
        twin_id=twin_id,
        session_id=session_id,
        operation_type="destroy",
    )
    db.commit()
    db.close()
    
    terminal_result: DeployerStreamResult | None = None
    current_event_type: str | None = None
    
    try:
        # Subscribe to Deployer destroy SSE
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{DEPLOYER_API_URL}/infrastructure/destroy/stream",
                params={"provider": provider, "project_name": resource_name}
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        current_event_type = line[7:].strip()
                        continue
                    if line.startswith("data: "):
                        log_message, result = _parse_deployer_sse_data(
                            line[6:],
                            current_event_type,
                            "destroy",
                        )
                        current_event_type = None
                        if result:
                            terminal_result = result
                        elif log_message:
                            print(log_message, flush=True)
                            await session.push_log(log_message)
        
        destroy_success = bool(terminal_result and terminal_result.success)
        error_message = _result_message(
            terminal_result,
            success_message="Destruction complete",
            failure_message="Destroy stream ended without terminal result",
        )

        db = SessionLocal()
        try:
            twin = db.get(DigitalTwin, twin_id)
            repository = DeploymentRepository(db)
            deployment = repository.get_by_session_id(session_id)
            if twin:
                if destroy_success:
                    twin.state = TwinState.DESTROYED
                    twin.destroyed_at = datetime.utcnow()
                else:
                    twin.state = TwinState.ERROR
                    twin.last_error = error_message
            
            if deployment:
                if destroy_success:
                    repository.mark_success(
                        deployment,
                        operation_id=terminal_result.operation_id if terminal_result else None,
                    )
                else:
                    repository.mark_failed(
                        deployment,
                        error_message=error_message,
                        operation_id=terminal_result.operation_id if terminal_result else None,
                        error_code=(
                            terminal_result.error_code
                            if terminal_result and terminal_result.error_code
                            else "DEPLOYER_STREAM_ERROR"
                        ),
                    )
            db.commit()  # Single atomic commit
        finally:
            db.close()
        
        session.on_complete(
            success=destroy_success,
            message=error_message,
            operation_id=terminal_result.operation_id if terminal_result else None,
            error_code=None if destroy_success else (
                terminal_result.error_code
                if terminal_result and terminal_result.error_code
                else "DEPLOYER_STREAM_ERROR"
            ),
        )
        
    except Exception as e:
        destroy_success = bool(terminal_result and terminal_result.success)
        safe_error = _redact_deployment_message(e)
        logger.error("Destroy stream error (success=%s): %s", destroy_success, safe_error)
        db = SessionLocal()
        try:
            twin = db.get(DigitalTwin, twin_id)
            if twin and not destroy_success:
                twin.state = TwinState.ERROR
                twin.last_error = safe_error
            elif twin and destroy_success:
                twin.state = TwinState.DESTROYED
                twin.destroyed_at = datetime.utcnow()
            
            repository = DeploymentRepository(db)
            deployment = repository.get_by_session_id(session_id)
            if deployment:
                if destroy_success:
                    repository.mark_success(
                        deployment,
                        operation_id=terminal_result.operation_id if terminal_result else None,
                    )
                else:
                    repository.mark_failed(
                        deployment,
                        error_message=safe_error,
                        operation_id=terminal_result.operation_id if terminal_result else None,
                        error_code=(
                            terminal_result.error_code
                            if terminal_result and terminal_result.error_code
                            else "BACKEND_STREAM_ERROR"
                        ),
                    )
            db.commit()
        finally:
            db.close()
        
        if not destroy_success:
            await session.push_log(f"Destroy error: {safe_error}", level="error")
        session.on_complete(
            success=destroy_success,
            message=safe_error if not destroy_success else "Destruction complete",
            operation_id=terminal_result.operation_id if terminal_result else None,
            error_code=None if destroy_success else (
                terminal_result.error_code
                if terminal_result and terminal_result.error_code
                else "BACKEND_STREAM_ERROR"
            ),
        )


# ============================================================================
# PRODUCTION DEPLOYMENT - ZIP Building and Upload
# ============================================================================

def build_project_zip(twin, user_id: str) -> io.BytesIO:
    """
    Build a ZIP file containing all configuration files for the Deployer.
    
    Args:
        twin: DigitalTwin model with related configurations loaded
        user_id: Current user ID (for credential decryption)
        
    Returns:
        BytesIO containing the ZIP file
    """
    zip_buffer = io.BytesIO()
    dc = twin.deployer_config  # Shorthand to avoid repetition
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # --- Config Files ---
        providers = _build_providers_config(twin)
        deployment_credentials = _build_deployment_credentials(twin, user_id)
        _add_config_files(zf, twin, providers, deployment_credentials)
        
        # --- Provider-Specific Files ---
        _add_hierarchy_files(zf, dc)
        _add_state_machine_file(zf, dc, twin.optimizer_config)
        _add_user_functions(zf, dc, providers)
        _add_scene_files(zf, dc, providers, twin.id)
        
        # --- Simulator Files ---
        if dc and dc.payloads_json:
            zf.writestr("iot_device_simulator/payloads.json", dc.payloads_json)

        _add_deployment_manifest(zf, twin, providers, deployment_credentials)
    
    zip_buffer.seek(0)
    return zip_buffer


# ============================================================================
# HELPER FUNCTIONS - Separation of Concerns
# ============================================================================

def _add_config_files(
    zf: zipfile.ZipFile,
    twin,
    providers: dict,
    deployment_credentials: DeploymentCredentials,
):
    """Add all config JSON files to the ZIP."""
    dc = twin.deployer_config
    oc = twin.optimizer_config
    
    # Main config and providers
    zf.writestr("config.json", json.dumps(_build_main_config(twin), indent=2))
    zf.writestr("config_providers.json", json.dumps(providers, indent=2))
    
    # Credentials (with separate GCP file)
    credentials, gcp_creds = (
        deployment_credentials.config_credentials,
        deployment_credentials.gcp_credentials_json,
    )
    zf.writestr("config_credentials.json", json.dumps(credentials, indent=2))
    if gcp_creds:
        zf.writestr("gcp_credentials.json", json.dumps(gcp_creds, indent=2))
    
    zf.writestr(
        "config_iot_devices.json",
        _json_content_or_default(dc.config_iot_devices_json if dc else None, []),
    )
    zf.writestr(
        "config_events.json",
        _json_content_or_default(dc.config_events_json if dc else None, []),
    )

    # Optional config files from deployer_config
    if dc:
        _write_if_present(zf, "config_user.json", dc.user_config_content)
    
    # Optimizer result (deployer expects {"result": {"inputParamsUsed": {...}}})
    if oc:
        zf.writestr("config_optimization.json", json.dumps(
            _build_optimization_config(oc), indent=2
        ))


def _add_deployment_manifest(
    zf: zipfile.ZipFile,
    twin,
    providers: dict,
    deployment_credentials: DeploymentCredentials,
) -> None:
    """Add a secrets-free deployment package manifest."""
    file_names = sorted(
        name for name in zf.namelist()
        if name != DEPLOYMENT_MANIFEST_FILE
    )
    zf.writestr(
        DEPLOYMENT_MANIFEST_FILE,
        json.dumps(
            _build_deployment_manifest(twin, providers, deployment_credentials, file_names),
            indent=2,
            sort_keys=True,
        ),
    )


def _add_hierarchy_files(zf: zipfile.ZipFile, dc: Optional["DeployerConfiguration"]) -> None:
    """Add twin hierarchy files (written to both provider locations)."""
    if dc and dc.hierarchy_content:
        zf.writestr("twin_hierarchy/aws_hierarchy.json", dc.hierarchy_content)
        zf.writestr("twin_hierarchy/azure_hierarchy.json", dc.hierarchy_content)


def _add_state_machine_file(zf: zipfile.ZipFile, dc: Optional["DeployerConfiguration"], oc: Optional["OptimizerConfiguration"]) -> None:
    """Add state machine file to provider-specific location."""
    if not (dc and dc.state_machine_content and oc and oc.cheapest_l2):
        return
    
    l2 = oc.cheapest_l2.lower()
    filenames = {
        "aws": "state_machines/aws_step_function.json",
        "azure": "state_machines/azure_logic_app.json",
        "google": "state_machines/google_cloud_workflow.yaml",
        "gcp": "state_machines/google_cloud_workflow.yaml",
    }
    if l2 in filenames:
        zf.writestr(filenames[l2], dc.state_machine_content)


def _add_user_functions(zf: zipfile.ZipFile, dc: Optional["DeployerConfiguration"], providers: dict) -> None:
    """Add all user functions (processors, event_actions, event_feedback)."""
    if not dc:
        return
    
    # L2 is the compute layer (where functions run)
    l2 = providers.get("layer_2_provider", "aws")
    func_base = _get_function_base_folder(l2)
    func_file = _get_function_filename(l2)
    
    # Processors
    _add_function_set(
        zf, func_base, "processors", func_file,
        dc.processor_contents, dc.processor_requirements
    )
    
    # Event actions
    _add_function_set(
        zf, func_base, "event_actions", func_file,
        dc.event_action_contents, dc.event_action_requirements
    )
    
    # Event feedback (single function, not dict)
    if dc.event_feedback_content:
        zf.writestr(f"{func_base}/event-feedback/{func_file}", dc.event_feedback_content)
        _write_if_present(zf, f"{func_base}/event-feedback/requirements.txt", dc.event_feedback_requirements)


def _add_scene_files(zf: zipfile.ZipFile, dc: Optional["DeployerConfiguration"], providers: dict, twin_id: str) -> None:
    """Add scene files to provider-specific location."""
    if not dc or not dc.scene_config_content:
        return
    
    l4 = providers.get("layer_4_provider")
    scene_filenames = {
        "azure": "scene_assets/azure/3DScenesConfiguration.json",
        "aws": "scene_assets/aws/scene.json",
    }
    if l4 in scene_filenames:
        zf.writestr(scene_filenames[l4], dc.scene_config_content)
    
    # Add GLB binary if uploaded (stored on backend disk, not in DB)
    if dc.scene_glb_uploaded and l4 in ("aws", "azure"):
        glb_path = Path(settings.UPLOAD_DIR) / twin_id / "scene.glb"
        if glb_path.exists():
            zf.write(str(glb_path), f"scene_assets/{l4}/scene.glb")


# ============================================================================
# UTILITY FUNCTIONS - DRY Helpers
# ============================================================================

def _get_function_base_folder(provider: str) -> str:
    """Map provider to function folder name."""
    return {
        "azure": "azure_functions",
        "google": "cloud_functions",
        "gcp": "cloud_functions",
    }.get(provider, "lambda_functions")


def _get_function_filename(provider: str) -> str:
    """Map provider to the expected user-code filename."""
    return {
        "azure": "function_app.py",
        "google": "main.py",
        "gcp": "main.py",
    }.get(provider, "lambda_function.py")


def _add_function_set(
    zf: zipfile.ZipFile,
    base_folder: str,
    subfolder: str,
    filename: str,
    contents_json: Optional[str],
    requirements_json: Optional[str]
):
    """Add a set of functions with optional requirements.txt files (DRY pattern)."""
    if not contents_json:
        return
    
    try:
        contents = json.loads(contents_json)
        for name, code in contents.items():
            zf.writestr(f"{base_folder}/{subfolder}/{name}/{filename}", code)
        
        # Add requirements if available
        if requirements_json:
            try:
                reqs = json.loads(requirements_json)
                for name, req_content in reqs.items():
                    zf.writestr(f"{base_folder}/{subfolder}/{name}/requirements.txt", req_content)
            except json.JSONDecodeError:
                pass
    except json.JSONDecodeError:
        pass


def _write_if_present(zf: zipfile.ZipFile, path: str, content: Optional[str]):
    """Write content to ZIP only if not None (DRY helper)."""
    if content:
        zf.writestr(path, content)


def _json_content_or_default(content: Optional[str], default_value: Any) -> str:
    """Return stored JSON content or a stable JSON default for required files."""
    if content:
        return content
    return json.dumps(default_value, indent=2)


def get_resource_name(twin) -> str:
    """
    Extract the Deployer resource name from a twin (DRY helper).
    Used by: build_project_zip, prepare_project_for_deployment, deploy, destroy.
    """
    if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
        return twin.deployer_config.deployer_digital_twin_name
    return twin.name.lower().replace(" ", "-")


def _build_main_config(twin) -> dict:
    """Build the main config.json content."""
    # Storage durations from optimizer params (months → days)
    hot_days = 30  # default: 1 month
    cold_days = 90  # default: 3 months
    if twin.optimizer_config and twin.optimizer_config.params:
        try:
            params = json.loads(twin.optimizer_config.params)
            hot_days = params.get("hotStorageDurationInMonths", 1) * 30
            cold_days = params.get("coolStorageDurationInMonths", 3) * 30
        except (json.JSONDecodeError, TypeError):
            pass  # Use defaults

    # Mode from Step 1 debug toggle
    mode = "debug" if (twin.configuration and twin.configuration.debug_mode) else "production"

    return {
        "digital_twin_name": get_resource_name(twin),
        "hot_storage_size_in_days": hot_days,
        "cold_storage_size_in_days": cold_days,
        "mode": mode,
    }


def _build_providers_config(twin) -> dict:
    """
    Build config_providers.json from OptimizerConfiguration.
    
    NOTE: Provider values are stored as uppercase ("AWS", "AZURE", "GCP")
    but the Deployer expects lowercase. We convert here.
    """
    if not twin.optimizer_config:
        return {}
    
    oc = twin.optimizer_config
    
    def normalize(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        v = value.lower()
        # Optimizer stores "GCP" but Terraform/Deployer expect "google"
        return "google" if v == "gcp" else v
    
    return {
        "layer_1_provider": normalize(oc.cheapest_l1),
        "layer_2_provider": normalize(oc.cheapest_l2),
        "layer_3_hot_provider": normalize(oc.cheapest_l3_hot),
        "layer_3_cold_provider": normalize(oc.cheapest_l3_cool),  # Model: cheapest_l3_cool → Output: layer_3_cold_provider
        "layer_3_archive_provider": normalize(oc.cheapest_l3_archive),
        "layer_4_provider": normalize(oc.cheapest_l4),
        "layer_5_provider": normalize(oc.cheapest_l5),
    }


def _build_credentials_config(twin, user_id: str) -> tuple[dict, Optional[dict]]:
    """
    Build config_credentials.json from the credential SSOT resolver.

    The returned values are secret-bearing and must only be written into the
    ephemeral project ZIP uploaded to the Deployer.
    """
    resolved = _build_deployment_credentials(twin, user_id)
    return resolved.config_credentials, resolved.gcp_credentials_json


def _build_deployment_credentials(twin, user_id: str) -> DeploymentCredentials:
    """Resolve deployment credentials once for config files and manifest metadata."""
    return CredentialResolutionService().resolve_deployment_credentials(twin, user_id)


def _build_deployment_manifest(
    twin,
    providers: dict,
    deployment_credentials: DeploymentCredentials,
    file_names: list[str],
) -> dict[str, Any]:
    """
    Build the secrets-free package manifest.

    The manifest describes package provenance and credential sources only. It
    must never contain credential payloads or decrypted secret values.
    """
    return {
        "manifest_version": DEPLOYMENT_MANIFEST_VERSION,
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "producer": "twin2multicloud_backend",
        "package": {
            "format": "deployer-project-zip",
            "files": file_names,
            "required_files": REQUIRED_DEPLOYER_CONFIG_FILES,
        },
        "twin": {
            "id": _manifest_scalar(getattr(twin, "id", None)),
            "name": _manifest_scalar(getattr(twin, "name", None)),
            "resource_name": get_resource_name(twin),
        },
        "providers": _remove_empty_values(providers),
        "credentials": {
            "providers": list(deployment_credentials.providers),
            "sources": dict(deployment_credentials.sources),
            "contains_secret_payloads": _manifest_contains_secret_payloads(),
        },
    }


def _manifest_scalar(value: Any) -> Optional[str]:
    """Return stable scalar strings without serializing mocks or ORM internals."""
    if value is None:
        return None
    raw_value = getattr(value, "value", None)
    if isinstance(raw_value, (str, int, float, bool)):
        return str(raw_value)
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return None


def _manifest_contains_secret_payloads() -> bool:
    """Return the manifest's explicit secret-payload safety flag."""
    return False


def _remove_empty_values(values: dict[str, Any]) -> dict[str, Any]:
    """Keep manifest JSON compact while preserving explicit false values."""
    return {
        key: value
        for key, value in values.items()
        if value is not None and value != ""
    }


def _build_optimization_config(oc) -> dict:
    """
    Build config_optimization.json with the deployer-expected format.
    
    The deployer reads: result.inputParamsUsed.{flag} via config_loader.load_optimization_flags()
    These flags control which Terraform resources are conditionally created.
    """
    input_params = {}
    if oc.params:
        try:
            params = json.loads(oc.params)
            input_params = {
                "useEventChecking": params.get("useEventChecking", False),
                "triggerNotificationWorkflow": params.get("triggerNotificationWorkflow", False),
                "returnFeedbackToDevice": params.get("returnFeedbackToDevice", False),
                "integrateErrorHandling": params.get("integrateErrorHandling", False),
                "needs3DModel": params.get("needs3DModel", False),
            }
        except (json.JSONDecodeError, TypeError):
            pass
    return {"result": {"inputParamsUsed": input_params}}


async def upload_project_to_deployer(
    project_name: str,
    zip_data: io.BytesIO,
    update_existing: bool = True
) -> dict:
    """
    Upload project ZIP to the Deployer API.
    
    Args:
        project_name: Name of the project in the Deployer
        zip_data: BytesIO containing the project ZIP
        update_existing: If True, use import endpoint for existing projects
        
    Returns:
        Response from Deployer API
        
    Raises:
        HTTPException on failure
    """
    from fastapi import HTTPException
    
    # Use detailed timeouts like existing code (see run_real_deploy_stream)
    timeout = httpx.Timeout(connect=30.0, read=60.0, write=60.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Check if project already exists
        check_resp = await client.get(f"{DEPLOYER_API_URL}/projects/{project_name}/validate")
        project_exists = check_resp.status_code == 200
        
        zip_data.seek(0)
        content = zip_data.read()
        
        if project_exists and update_existing:
            # Use import endpoint to UPDATE existing project
            # Import endpoint uses UploadFile (multipart form data)
            resp = await client.post(
                f"{DEPLOYER_API_URL}/projects/{project_name}/import",
                files={"file": (f"{project_name}.zip", content, "application/zip")}
            )
        else:
            # Create NEW project
            # IMPORTANT: create_project uses extract_file_content() which ONLY accepts:
            # - multipart/form-data
            # - application/json (with base64)
            # It does NOT accept application/octet-stream (returns 415)!
            resp = await client.post(
                f"{DEPLOYER_API_URL}/projects",
                params={"project_name": project_name},
                files={"file": (f"{project_name}.zip", content, "application/zip")}
            )
        
        if resp.status_code not in (200, 201):
            raise HTTPException(
                status_code=502,
                detail=f"Deployer project setup failed: {resp.text}"
            )
        
        return resp.json()


async def prepare_project_for_deployment(twin, user_id: str) -> str:
    """
    Main entry point: Prepare and upload project to Deployer.
    
    Args:
        twin: DigitalTwin with all related configurations loaded
        user_id: Current user ID for credential decryption
        
    Returns:
        resource_name: The project name used in the Deployer
    """
    resource_name = get_resource_name(twin)  # DRY: reuse helper
    
    # Build ZIP
    zip_data = build_project_zip(twin, user_id)
    
    # Upload to Deployer
    await upload_project_to_deployer(resource_name, zip_data)
    
    return resource_name
