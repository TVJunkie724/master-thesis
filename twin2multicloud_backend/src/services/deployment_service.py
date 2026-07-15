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
from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

from src.clients.deployer_client import DeployerClient
from src.config import settings
from src.repositories.deployment_repository import DeploymentRepository
from src.services.credential_resolution_service import (
    CredentialResolutionService,
    DeploymentCredentials,
)
from src.services.errors import (
    DeploymentPackageBuildFailed,
    ExternalServiceError,
    ExternalServiceUnavailable,
)
from src.services.provider_contract import provider_id_for_deployer_project
from src.services.service_errors import DownstreamServiceError
from src.services.twin_lifecycle_service import TwinLifecycleService

if TYPE_CHECKING:
    from src.models.deployer_config import DeployerConfiguration
    from src.models.optimizer_config import OptimizerConfiguration

logger = logging.getLogger(__name__)

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
WORKSPACE_PATH_PATTERN = re.compile(
    r"(/[^\s:]+/twin2multicloud-deployer-workspaces/[^\s:]+)"
)


@dataclass(frozen=True)
class DeployerStreamResult:
    """Terminal result parsed from the Deployer SSE contract."""

    success: bool
    operation_id: str | None = None
    error_code: str | None = None
    message: str | None = None
    outputs: dict[str, Any] | None = None


@dataclass(frozen=True)
class DeploymentPackageFile:
    """Text/JSON file materialized from canonical backend state."""

    path: str
    content: str
    contains_secret_payloads: bool = False


@dataclass(frozen=True)
class DeploymentPackageBinaryFile:
    """Binary file that is copied into the package from managed storage."""

    source_path: Path
    archive_path: str


@dataclass(frozen=True)
class DeploymentPackage:
    """Deployer package materialization independent from HTTP request shape."""

    files: tuple[DeploymentPackageFile, ...]
    binary_files: tuple[DeploymentPackageBinaryFile, ...]
    manifest: dict[str, Any]


@dataclass(frozen=True)
class PreparedDeploymentProject:
    """Opaque Deployer context prepared for one operation."""

    resource_name: str
    operation_token: str


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
        config["resource_name"] = (
            dc.deployer_digital_twin_name or config["resource_name"]
        )

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
                error_code=None
                if event_type == "complete"
                else "DEPLOYER_STREAM_ERROR",
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
                if success
                else f"{operation_type.capitalize()} failed"
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
    provider: str,
    operation_token: str,
    deployer_client: DeployerClient | None = None,
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
    from src.services.deployment_stream_service import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin

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
        client = deployer_client or DeployerClient()
        async for line in client.deploy_stream(
            provider, resource_name, operation_token
        ):
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
                    logger.info(
                        "Deployment stream: %s",
                        log_message,
                        extra={"session_id": session_id, "twin_id": twin_id},
                    )
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
                    TwinLifecycleService.complete_deploy(
                        twin, deployed_at=datetime.utcnow()
                    )
                else:
                    TwinLifecycleService.fail_deploy(twin, error_message)

            if deployment:
                if deploy_success:
                    repository.mark_success(
                        deployment,
                        terraform_outputs=terraform_outputs,
                        operation_id=terminal_result.operation_id
                        if terminal_result
                        else None,
                    )
                else:
                    repository.mark_failed(
                        deployment,
                        error_message=error_message,
                        terraform_outputs=terraform_outputs,
                        operation_id=terminal_result.operation_id
                        if terminal_result
                        else None,
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
            error_code=None
            if deploy_success
            else (
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
                TwinLifecycleService.fail_deploy(twin, safe_error)
            elif twin and deploy_success:
                TwinLifecycleService.complete_deploy(
                    twin, deployed_at=datetime.utcnow()
                )

            repository = DeploymentRepository(db)
            deployment = repository.get_by_session_id(session_id)
            if deployment:
                if deploy_success:
                    repository.mark_success(
                        deployment,
                        terraform_outputs=terraform_outputs,
                        operation_id=terminal_result.operation_id
                        if terminal_result
                        else None,
                    )
                else:
                    repository.mark_failed(
                        deployment,
                        error_message=safe_error,
                        terraform_outputs=terraform_outputs,
                        operation_id=terminal_result.operation_id
                        if terminal_result
                        else None,
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
            error_code=None
            if deploy_success
            else (
                terminal_result.error_code
                if terminal_result and terminal_result.error_code
                else "BACKEND_STREAM_ERROR"
            ),
        )


async def run_real_destroy_stream(
    session_id: str,
    twin_id: str,
    resource_name: str,
    provider: str,
    operation_token: str,
    deployer_client: DeployerClient | None = None,
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
    from src.services.deployment_stream_service import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin

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
        client = deployer_client or DeployerClient()
        async for line in client.destroy_stream(
            provider, resource_name, operation_token
        ):
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
                    logger.info(
                        "Destroy stream: %s",
                        log_message,
                        extra={"session_id": session_id, "twin_id": twin_id},
                    )
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
                    TwinLifecycleService.complete_destroy(
                        twin, destroyed_at=datetime.utcnow()
                    )
                else:
                    TwinLifecycleService.fail_destroy(twin, error_message)

            if deployment:
                if destroy_success:
                    repository.mark_success(
                        deployment,
                        operation_id=terminal_result.operation_id
                        if terminal_result
                        else None,
                    )
                else:
                    repository.mark_failed(
                        deployment,
                        error_message=error_message,
                        operation_id=terminal_result.operation_id
                        if terminal_result
                        else None,
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
            error_code=None
            if destroy_success
            else (
                terminal_result.error_code
                if terminal_result and terminal_result.error_code
                else "DEPLOYER_STREAM_ERROR"
            ),
        )

    except Exception as e:
        destroy_success = bool(terminal_result and terminal_result.success)
        safe_error = _redact_deployment_message(e)
        logger.error(
            "Destroy stream error (success=%s): %s", destroy_success, safe_error
        )
        db = SessionLocal()
        try:
            twin = db.get(DigitalTwin, twin_id)
            if twin and not destroy_success:
                TwinLifecycleService.fail_destroy(twin, safe_error)
            elif twin and destroy_success:
                TwinLifecycleService.complete_destroy(
                    twin, destroyed_at=datetime.utcnow()
                )

            repository = DeploymentRepository(db)
            deployment = repository.get_by_session_id(session_id)
            if deployment:
                if destroy_success:
                    repository.mark_success(
                        deployment,
                        operation_id=terminal_result.operation_id
                        if terminal_result
                        else None,
                    )
                else:
                    repository.mark_failed(
                        deployment,
                        error_message=safe_error,
                        operation_id=terminal_result.operation_id
                        if terminal_result
                        else None,
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
            error_code=None
            if destroy_success
            else (
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
    package = build_deployment_package(twin, user_id)
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in package.files:
            zf.writestr(file.path, file.content)
        for binary_file in package.binary_files:
            zf.write(str(binary_file.source_path), binary_file.archive_path)

    zip_buffer.seek(0)
    return zip_buffer


# ============================================================================
# HELPER FUNCTIONS - Separation of Concerns
# ============================================================================


def build_deployment_package(twin, user_id: str) -> DeploymentPackage:
    """Materialize the Deployer package from persisted backend state."""
    providers = _build_providers_config(twin)
    deployment_credentials = _build_deployment_credentials(twin, user_id)
    files = _materialize_deployment_files(twin, providers, deployment_credentials)
    binary_files = _materialize_binary_files(twin, providers)
    file_names = sorted(
        [file.path for file in files]
        + [binary_file.archive_path for binary_file in binary_files]
    )
    secret_bearing_files = sorted(
        file.path for file in files if file.contains_secret_payloads
    )
    manifest = _build_deployment_manifest(
        twin,
        providers,
        deployment_credentials,
        file_names,
        secret_bearing_files,
    )
    files = files + (
        DeploymentPackageFile(
            DEPLOYMENT_MANIFEST_FILE,
            json.dumps(manifest, indent=2, sort_keys=True),
        ),
    )
    return DeploymentPackage(files=files, binary_files=binary_files, manifest=manifest)


def _materialize_deployment_files(
    twin,
    providers: dict,
    deployment_credentials: DeploymentCredentials,
) -> tuple[DeploymentPackageFile, ...]:
    """Return the text/JSON files required by the Deployer package contract."""
    dc = twin.deployer_config
    oc = twin.optimizer_config
    files: list[DeploymentPackageFile] = [
        DeploymentPackageFile(
            "config.json", json.dumps(_build_main_config(twin), indent=2)
        ),
        DeploymentPackageFile("config_providers.json", json.dumps(providers, indent=2)),
    ]

    credentials, gcp_creds = (
        deployment_credentials.config_credentials,
        deployment_credentials.gcp_credentials_json,
    )
    files.append(
        DeploymentPackageFile(
            "config_credentials.json",
            json.dumps(credentials, indent=2),
            contains_secret_payloads=True,
        )
    )
    if gcp_creds:
        files.append(
            DeploymentPackageFile(
                "gcp_credentials.json",
                json.dumps(gcp_creds, indent=2),
                contains_secret_payloads=True,
            )
        )

    files.append(
        DeploymentPackageFile(
            "config_iot_devices.json",
            _json_content_or_default(
                dc.config_iot_devices_json if dc else None,
                [],
                "deployer_config.config_iot_devices_json",
            ),
        )
    )
    files.append(
        DeploymentPackageFile(
            "config_events.json",
            _json_content_or_default(
                dc.config_events_json if dc else None,
                [],
                "deployer_config.config_events_json",
            ),
        )
    )

    if oc:
        files.append(
            DeploymentPackageFile(
                "config_optimization.json",
                json.dumps(_build_optimization_config(oc), indent=2),
            )
        )
    if dc:
        files.extend(_materialize_deployer_artifacts(dc, oc, providers))
        if dc.payloads_json:
            files.append(
                DeploymentPackageFile(
                    "iot_device_simulator/payloads.json",
                    _json_content_or_default(
                        dc.payloads_json,
                        {},
                        "deployer_config.payloads_json",
                    ),
                )
            )
    return tuple(files)


def _materialize_deployer_artifacts(
    dc: "DeployerConfiguration",
    oc: Optional["OptimizerConfiguration"],
    providers: dict,
) -> tuple[DeploymentPackageFile, ...]:
    files: list[DeploymentPackageFile] = []
    if dc.user_config_content:
        _load_json_document(
            dc.user_config_content, "deployer_config.user_config_content"
        )
        files.append(DeploymentPackageFile("config_user.json", dc.user_config_content))

    if dc.hierarchy_content:
        _load_json_document(dc.hierarchy_content, "deployer_config.hierarchy_content")
        files.append(
            DeploymentPackageFile(
                "twin_hierarchy/aws_hierarchy.json", dc.hierarchy_content
            )
        )
        files.append(
            DeploymentPackageFile(
                "twin_hierarchy/azure_hierarchy.json", dc.hierarchy_content
            )
        )

    if dc.state_machine_content and oc and oc.cheapest_l2:
        l2 = provider_id_for_deployer_project(oc.cheapest_l2)
        filenames = {
            "aws": "state_machines/aws_step_function.json",
            "azure": "state_machines/azure_logic_app.json",
            "google": "state_machines/google_cloud_workflow.yaml",
        }
        if l2 in filenames:
            files.append(DeploymentPackageFile(filenames[l2], dc.state_machine_content))

    files.extend(_materialize_user_functions(dc, providers))
    files.extend(_materialize_scene_config(dc, providers))
    return tuple(files)


def _materialize_user_functions(
    dc: "DeployerConfiguration",
    providers: dict,
) -> tuple[DeploymentPackageFile, ...]:
    l2 = providers.get("layer_2_provider", "aws")
    func_base = _get_function_base_folder(l2)
    func_file = _get_function_filename(l2)
    files: list[DeploymentPackageFile] = []
    files.extend(
        _materialize_function_set(
            func_base,
            "processors",
            func_file,
            dc.processor_contents,
            dc.processor_requirements,
            "deployer_config.processor_contents",
            "deployer_config.processor_requirements",
        )
    )
    files.extend(
        _materialize_function_set(
            func_base,
            "event_actions",
            func_file,
            dc.event_action_contents,
            dc.event_action_requirements,
            "deployer_config.event_action_contents",
            "deployer_config.event_action_requirements",
        )
    )

    if dc.event_feedback_content:
        files.append(
            DeploymentPackageFile(
                f"{func_base}/event-feedback/{func_file}", dc.event_feedback_content
            )
        )
        if dc.event_feedback_requirements:
            files.append(
                DeploymentPackageFile(
                    f"{func_base}/event-feedback/requirements.txt",
                    dc.event_feedback_requirements,
                )
            )
    return tuple(files)


def _materialize_function_set(
    base_folder: str,
    subfolder: str,
    filename: str,
    contents_json: Optional[str],
    requirements_json: Optional[str],
    contents_field: str,
    requirements_field: str,
) -> tuple[DeploymentPackageFile, ...]:
    if not contents_json:
        return ()

    contents = _json_object_from_content(contents_json, contents_field)
    requirements = (
        _json_object_from_content(requirements_json, requirements_field)
        if requirements_json
        else {}
    )
    files: list[DeploymentPackageFile] = []
    for name, code in contents.items():
        if not isinstance(code, str):
            _raise_package_error(
                contents_field,
                "INVALID_FUNCTION_CONTENT",
                "Function content values must be strings",
            )
        files.append(
            DeploymentPackageFile(f"{base_folder}/{subfolder}/{name}/{filename}", code)
        )
        requirement_content = requirements.get(name)
        if requirement_content is not None:
            if not isinstance(requirement_content, str):
                _raise_package_error(
                    requirements_field,
                    "INVALID_REQUIREMENTS_CONTENT",
                    "Requirements values must be strings",
                )
            files.append(
                DeploymentPackageFile(
                    f"{base_folder}/{subfolder}/{name}/requirements.txt",
                    requirement_content,
                )
            )
    return tuple(files)


def _materialize_scene_config(
    dc: "DeployerConfiguration",
    providers: dict,
) -> tuple[DeploymentPackageFile, ...]:
    if not dc.scene_config_content:
        return ()

    _load_json_document(dc.scene_config_content, "deployer_config.scene_config_content")
    l4 = providers.get("layer_4_provider")
    scene_filenames = {
        "azure": "scene_assets/azure/3DScenesConfiguration.json",
        "aws": "scene_assets/aws/scene.json",
    }
    if l4 not in scene_filenames:
        return ()
    return (DeploymentPackageFile(scene_filenames[l4], dc.scene_config_content),)


def _materialize_binary_files(
    twin, providers: dict
) -> tuple[DeploymentPackageBinaryFile, ...]:
    dc = twin.deployer_config
    l4 = providers.get("layer_4_provider")
    if not (dc and dc.scene_glb_uploaded and l4 in ("aws", "azure")):
        return ()

    glb_path = Path(settings.UPLOAD_DIR) / twin.id / "scene.glb"
    if not glb_path.exists():
        _raise_package_error(
            "deployer_config.scene_glb_uploaded",
            "MISSING_BINARY_ARTIFACT",
            "Scene GLB is marked as uploaded but the managed file is missing",
        )
    return (DeploymentPackageBinaryFile(glb_path, f"scene_assets/{l4}/scene.glb"),)


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


def _json_content_or_default(
    content: Optional[str], default_value: Any, field: str
) -> str:
    """Return stored JSON content or a stable JSON default for required files."""
    if content:
        _load_json_document(content, field)
        return content
    return json.dumps(default_value, indent=2)


def _json_object_from_content(content: str, field: str) -> dict[str, Any]:
    value = _load_json_document(content, field)
    if not isinstance(value, dict):
        _raise_package_error(
            field,
            "INVALID_JSON_OBJECT",
            "Deployment artifact must be a JSON object",
        )
    return value


def _load_json_document(content: str, field: str) -> Any:
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        _raise_package_error(
            field,
            "INVALID_JSON",
            "Deployment artifact contains invalid JSON",
        )


def _raise_package_error(field: str, code: str, message: str) -> None:
    raise DeploymentPackageBuildFailed(
        "Cannot build deployment package",
        [
            {
                "code": code,
                "field": field,
                "message": message,
            }
        ],
    )


def _months_to_days(value: Any, default_months: int) -> int:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return int(value * 30)
    return default_months * 30


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
        params = _json_object_from_content(
            twin.optimizer_config.params,
            "optimizer_config.params",
        )
        hot_days = _months_to_days(params.get("hotStorageDurationInMonths"), 1)
        cold_days = _months_to_days(params.get("coolStorageDurationInMonths"), 3)

    # Mode from Step 1 debug toggle
    mode = (
        "debug"
        if (twin.configuration and twin.configuration.debug_mode)
        else "production"
    )

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

    return {
        "layer_1_provider": provider_id_for_deployer_project(oc.cheapest_l1),
        "layer_2_provider": provider_id_for_deployer_project(oc.cheapest_l2),
        "layer_3_hot_provider": provider_id_for_deployer_project(oc.cheapest_l3_hot),
        "layer_3_cold_provider": provider_id_for_deployer_project(
            oc.cheapest_l3_cool
        ),  # Model: cheapest_l3_cool → Output: layer_3_cold_provider
        "layer_3_archive_provider": provider_id_for_deployer_project(
            oc.cheapest_l3_archive
        ),
        "layer_4_provider": provider_id_for_deployer_project(oc.cheapest_l4),
        "layer_5_provider": provider_id_for_deployer_project(oc.cheapest_l5),
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
    secret_bearing_files: list[str] | None = None,
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
            "secret_bearing_files": secret_bearing_files or [],
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
        key: value for key, value in values.items() if value is not None and value != ""
    }


def _build_optimization_config(oc) -> dict:
    """
    Build config_optimization.json with the deployer-expected format.

    The deployer reads: result.inputParamsUsed.{flag} via config_loader.load_optimization_flags()
    These flags control which Terraform resources are conditionally created.
    """
    input_params = {}
    if oc.params:
        params = _json_object_from_content(oc.params, "optimizer_config.params")
        input_params = {
            "useEventChecking": params.get("useEventChecking") is True,
            "triggerNotificationWorkflow": params.get("triggerNotificationWorkflow")
            is True,
            "returnFeedbackToDevice": params.get("returnFeedbackToDevice") is True,
            "integrateErrorHandling": params.get("integrateErrorHandling") is True,
            "needs3DModel": params.get("needs3DModel") is True,
        }
    return {"result": {"inputParamsUsed": input_params}}


async def upload_project_to_deployer(
    project_name: str,
    zip_data: io.BytesIO,
    deployer_client: DeployerClient | None = None,
) -> dict:
    """
    Upload project ZIP to the Deployer API.

    Args:
        project_name: Name of the project in the Deployer
        zip_data: BytesIO containing the project ZIP
    Returns:
        Response from Deployer API

    Raises:
        DownstreamServiceError when the Deployer cannot stage the package
    """
    client = deployer_client or DeployerClient()
    try:
        zip_data.seek(0)
        content = zip_data.read()
        return await client.stage_operation_package(project_name, content)
    except ExternalServiceUnavailable as exc:
        raise DownstreamServiceError(
            status_code=503,
            public_detail="Deployer API unavailable during project setup",
        ) from exc
    except ExternalServiceError as exc:
        upstream_status = exc.upstream_status_code
        status_code = (
            upstream_status
            if upstream_status in {400, 409, 413, 422}
            else 502
        )
        raise DownstreamServiceError(
            status_code=status_code,
            public_detail=(
                "Deployer project setup failed: "
                f"{_redact_deployment_message(exc.public_detail)}"
            ),
        ) from exc


async def prepare_project_for_deployment(
    twin, user_id: str
) -> PreparedDeploymentProject:
    """
    Main entry point: Prepare and upload project to Deployer.

    Args:
        twin: DigitalTwin with all related configurations loaded
        user_id: Current user ID for credential decryption

    Returns:
        Opaque operation-scoped Deployer project context
    """
    resource_name = get_resource_name(twin)  # DRY: reuse helper

    # Build ZIP
    zip_data = build_project_zip(twin, user_id)

    # Upload to Deployer
    result = await upload_project_to_deployer(resource_name, zip_data)
    operation_token = result.get("operation_token")
    if not isinstance(operation_token, str) or not operation_token:
        raise DeploymentPackageBuildFailed(
            "Deployer did not return an operation package token"
        )

    return PreparedDeploymentProject(
        resource_name=resource_name,
        operation_token=operation_token,
    )
