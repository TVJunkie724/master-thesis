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
from typing import Any, Mapping, Optional, Sequence, TYPE_CHECKING

from src.clients.deployer_client import DeployerClient
from src.config import settings
from src.contracts.executable_topology import (
    ERROR_HANDLING_FIELD,
    UNSUPPORTED_ERROR_HANDLING_MESSAGE,
    UNSUPPORTED_ERROR_HANDLING_TOPOLOGY,
    ensure_executable_error_handling_topology,
)
from src.repositories.deployment_repository import DeploymentRepository
from src.services.credential_resolution_service import (
    CredentialResolutionService,
    DeploymentCredentials,
)
from src.services.errors import (
    CostCalculationRunSelectionError,
    DeploymentPackageBuildFailed,
    ExternalServiceError,
    ExternalServiceUnavailable,
)
from src.services.cost_calculation_run_service import (
    validate_persisted_run_deployment_specification,
)
from src.services.architecture_contract_service import (
    calculate_digest as calculate_architecture_digest,
)
from src.services.provider_contract import (
    normalize_provider_id,
    provider_id_for_deployer_api,
    provider_id_for_deployer_project,
)
from src.services.service_errors import DownstreamServiceError
from src.services.twin_lifecycle_service import TwinLifecycleService

if TYPE_CHECKING:
    from src.models.deployer_config import DeployerConfiguration
    from src.models.optimizer_config import OptimizerConfiguration

logger = logging.getLogger(__name__)

DEPLOYMENT_MANIFEST_FILE = "deployment_manifest.json"
DEPLOYMENT_MANIFEST_VERSION = "3.0"
DEPLOYMENT_MANIFEST_V4_VERSION = "4.0"
RESOLVED_GRAPH_VERSION = "resolved-deployment-graph.v1"
PACKAGE_BUILDER_VERSION = "graph-package-builder.v1"
TERRAFORM_INPUT_CONTRACT_VERSION = "graph-terraform-inputs.v1"
ARCHITECTURE_CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
    / "definitions"
)
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
STAGE_COMPLETED_MARKER = "T2MC_STAGE_COMPLETED:"
PHASE_8_COMPARISON_PROFILES = {
    ("five-layer-baseline", "2"),
    ("six-layer-eventing", "1"),
}
PHASE_8_FIXED_REGIONS = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}
PHASE_8_FORBIDDEN_OPTIMIZER_FIELDS = {
    "allowGcpSelfHostedL4",
    "allowGcpSelfHostedL5",
    "amountOfActiveEditors",
    "amountOfActiveViewers",
    "apiCallsPerDashboardRefresh",
    "average3DModelSizeInMB",
    "dashboardRefreshesPerHour",
    "entityCount",
    "eventTriggerRate",
    "eventsPerMessage",
    "integrateErrorHandling",
    "needs3DModel",
    "numberOfEventActions",
    "orchestrationActionsPerMessage",
    "returnFeedbackToDevice",
    "triggerNotificationWorkflow",
    "useEventChecking",
}
PHASE_8_FORBIDDEN_DEPLOYER_FIELDS = (
    "event_action_contents",
    "event_action_requirements",
    "event_feedback_content",
    "event_feedback_requirements",
    "hierarchy_content",
    "processor_contents",
    "processor_requirements",
    "scene_config_content",
    "scene_glb_uploaded",
    "state_machine_content",
)


@dataclass(frozen=True)
class DeployerStreamResult:
    """Terminal result parsed from the Deployer SSE contract."""

    success: bool
    operation_id: str | None = None
    error_code: str | None = None
    message: str | None = None
    outputs: dict[str, Any] | None = None
    deployment_access_evidence: dict[str, Any] | None = None


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
class SelectedDeploymentContracts:
    """Immutable selected contracts that own one executable package."""

    run: Any
    architecture: dict[str, Any]
    specification: dict[str, Any]


@dataclass(frozen=True)
class PreparedDeploymentProject:
    """Opaque Deployer context prepared for one operation."""

    resource_name: str
    operation_token: str
    provider: str = "aws"
    graph_evidence: dict[str, Any] | None = None


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

    # Add the architecture-derived compatibility path. Historical fixed
    # columns are never executable inputs.
    if twin.optimizer_config:
        oc = twin.optimizer_config
        contracts = _selected_deployment_contracts(twin)
        provider_config = _build_providers_config(contracts.architecture)
        config["layers"] = {
            "l1": provider_config["layer_1_provider"],
            "l2": provider_config["layer_2_provider"],
            "l3_hot": provider_config["layer_3_hot_provider"],
            "l3_cool": provider_config["layer_3_cold_provider"],
            "l3_archive": provider_config["layer_3_archive_provider"],
            "l4": provider_config["layer_4_provider"],
            "l5": provider_config["layer_5_provider"],
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
            deployment_access_evidence=payload.get("deployment_access_evidence"),
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


def _completed_stage_from_log(message: str | None) -> str | None:
    """Extract one bounded Deployer lifecycle stage marker."""

    if not isinstance(message, str) or not message.startswith(STAGE_COMPLETED_MARKER):
        return None
    stage = message.removeprefix(STAGE_COMPLETED_MARKER)
    return stage if stage in {"package", "preplan", "terraform", "postapply"} else None


def _persist_completed_stage(session_factory, session_id: str, stage: str) -> None:
    """Atomically advance persisted deployment progress for retry diagnostics."""

    db = session_factory()
    try:
        repository = DeploymentRepository(db)
        deployment = repository.get_by_session_id(session_id)
        if deployment is not None:
            repository.mark_completed_stage(deployment, stage)
            db.commit()
    finally:
        db.close()


async def run_real_deploy_stream(
    session_id: str,
    twin_id: str,
    resource_name: str,
    provider: str,
    operation_token: str,
    deployer_client: DeployerClient | None = None,
    graph_evidence: dict[str, Any] | None = None,
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
        graph_evidence=graph_evidence,
    )
    db.commit()
    db.close()

    terraform_outputs = {}
    deployment_access_evidence = None
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
                    if result.success and result.deployment_access_evidence:
                        deployment_access_evidence = result.deployment_access_evidence
                elif log_message:
                    completed_stage = _completed_stage_from_log(log_message)
                    if completed_stage is not None:
                        _persist_completed_stage(
                            SessionLocal,
                            session_id,
                            completed_stage,
                        )
                        continue
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
                        deployment_access_evidence=deployment_access_evidence,
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
                        deployment_access_evidence=deployment_access_evidence,
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
    graph_evidence: dict[str, Any] | None = None,
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
        graph_evidence=graph_evidence,
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
                    completed_stage = _completed_stage_from_log(log_message)
                    if completed_stage is not None:
                        _persist_completed_stage(
                            SessionLocal,
                            session_id,
                            completed_stage,
                        )
                        continue
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


def build_project_zip(
    twin,
    user_id: str,
    *,
    calculation_run_id: str | None = None,
) -> io.BytesIO:
    """
    Build a ZIP file containing all configuration files for the Deployer.

    Args:
        twin: DigitalTwin model with related configurations loaded
        user_id: Current user ID (for credential decryption)

    Returns:
        BytesIO containing the ZIP file
    """
    package = build_deployment_package(
        twin,
        user_id,
        calculation_run_id=calculation_run_id,
    )
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


def build_deployment_package(
    twin,
    user_id: str,
    *,
    calculation_run_id: str | None = None,
) -> DeploymentPackage:
    """Materialize the Deployer package from persisted backend state."""
    contracts = _selected_deployment_contracts(
        twin,
        calculation_run_id=calculation_run_id,
    )
    optimizer_params = _validated_run_params(contracts.run)
    _ensure_optimizer_params_are_executable(optimizer_params)
    providers = _build_providers_config(contracts.architecture)
    _validate_architecture_specification_path(
        providers,
        contracts.architecture,
        contracts.specification,
    )
    required_providers = {
        normalize_provider_id(provider)
        for key, provider in providers.items()
        if key.endswith("_provider") and provider
    }
    deployment_credentials = _build_deployment_credentials(
        twin,
        user_id,
        required_providers=required_providers,
    )
    _validate_phase8_deployment_regions(
        contracts.architecture,
        providers,
        deployment_credentials.config_credentials,
    )
    files = _materialize_deployment_files(
        twin,
        providers,
        deployment_credentials,
        optimizer_params=optimizer_params,
        architecture_profile_ref=contracts.architecture.get("architecture_profile_ref"),
    )
    binary_files = _materialize_binary_files(twin, providers)
    file_names = sorted(
        [file.path for file in files]
        + [binary_file.archive_path for binary_file in binary_files]
    )
    secret_bearing_files = sorted(
        file.path for file in files if file.contains_secret_payloads
    )
    extension_references = _extension_manifest_references(files)
    manifest = _build_deployment_manifest(
        twin,
        providers,
        deployment_credentials,
        file_names,
        secret_bearing_files,
        extension_references=extension_references,
        resolved_architecture=contracts.architecture,
        deployment_specification=contracts.specification,
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
    *,
    optimizer_params: dict[str, Any],
    architecture_profile_ref: Mapping[str, Any] | None = None,
) -> tuple[DeploymentPackageFile, ...]:
    """Return the text/JSON files required by the Deployer package contract."""
    dc = twin.deployer_config
    oc = twin.optimizer_config
    _validate_phase8_deployer_artifacts(dc, architecture_profile_ref)
    files: list[DeploymentPackageFile] = [
        DeploymentPackageFile(
            "config.json",
            json.dumps(
                _build_main_config(twin, optimizer_params=optimizer_params),
                indent=2,
            ),
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

    files.append(
        DeploymentPackageFile(
            "config_optimization.json",
            json.dumps(
                _build_optimization_config_from_params(
                    optimizer_params,
                    architecture_profile_ref=architecture_profile_ref,
                ),
                indent=2,
            ),
        )
    )
    if dc:
        extension_files = _materialize_extension_bindings(twin)
        has_validated_extensions = bool(extension_files)
        if _has_legacy_user_functions(dc) and not has_validated_extensions:
            _raise_package_error(
                "extension_bindings",
                "EXTENSION_BINDING_UNRESOLVED",
                (
                    "Legacy unvalidated user logic cannot be selected for a "
                    "new deployment."
                ),
            )
        files.extend(
            _materialize_deployer_artifacts(
                dc,
                oc,
                providers,
                include_user_functions=not has_validated_extensions,
            )
        )
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
        files.extend(extension_files)
    else:
        files.extend(_materialize_extension_bindings(twin))
    return tuple(files)


def _materialize_extension_bindings(twin) -> tuple[DeploymentPackageFile, ...]:
    """Materialize active validated extension bindings without source rewrites."""
    from src.services.user_function_extension_service import (  # noqa: PLC0415
        ExtensionContractError,
        runtime,
    )

    bindings = sorted(
        (
            binding
            for binding in (getattr(twin, "extension_bindings", None) or ())
            if bool(getattr(binding, "active", False))
        ),
        key=lambda binding: (binding.slot_id, binding.slot_version),
    )
    if not bindings:
        return ()

    files: list[DeploymentPackageFile] = []
    index_bindings: list[dict[str, str]] = []
    identities: set[tuple[str, str]] = set()
    for binding in bindings:
        identity = (binding.slot_id, binding.slot_version)
        if identity in identities:
            _raise_package_error(
                "extension_bindings",
                "EXTENSION_BINDING_UNRESOLVED",
                "The Twin contains duplicate active extension bindings.",
            )
        identities.add(identity)
        artifact = binding.artifact
        if (
            artifact is None
            or artifact.user_id != getattr(twin, "user_id", None)
            or binding.user_id != getattr(twin, "user_id", None)
            or binding.twin_id != getattr(twin, "id", None)
            or artifact.artifact_state != "valid"
            or not artifact.manifest_json
        ):
            _raise_package_error(
                "extension_bindings",
                "EXTENSION_BINDING_UNRESOLVED",
                "An active extension binding is unauthorized or unresolved.",
            )
        try:
            manifest = runtime.load_json_bytes(
                artifact.manifest_json.encode("utf-8"),
                field="extension manifest",
            )
            source_files = {
                item.relative_path: item.content_text for item in artifact.files
            }
            runtime.validate_artifact_manifest(manifest, files=source_files)
            expected_binding_digest = runtime.binding_digest(
                twin_id=binding.twin_id,
                slot_id=binding.slot_id,
                slot_version=binding.slot_version,
                artifact_id=artifact.id,
                artifact_digest=artifact.artifact_digest,
            )
        except ExtensionContractError as exc:
            _raise_package_error(
                "extension_bindings",
                exc.code,
                "An active extension artifact failed contract validation.",
            )
        if (
            manifest["artifact_id"] != artifact.id
            or manifest["artifact_digest"] != artifact.artifact_digest
            or manifest["slot_id"] != binding.slot_id
            or manifest["slot_version"] != binding.slot_version
            or binding.binding_digest != expected_binding_digest
        ):
            _raise_package_error(
                "extension_bindings",
                "EXTENSION_BINDING_UNRESOLVED",
                "An active extension binding does not match its immutable artifact.",
            )

        artifact_root = f".twin2multicloud/extensions/artifacts/{artifact.id}"
        manifest_path = f"{artifact_root}/manifest.json"
        source_root = f"{artifact_root}/source"
        files.append(
            DeploymentPackageFile(
                manifest_path,
                runtime.canonical_json(manifest),
            )
        )
        files.extend(
            DeploymentPackageFile(
                f"{source_root}/{relative_path}",
                content,
            )
            for relative_path, content in sorted(source_files.items())
        )
        index_bindings.append(
            {
                "slot_id": binding.slot_id,
                "slot_version": binding.slot_version,
                "artifact_id": artifact.id,
                "artifact_digest": artifact.artifact_digest,
                "binding_digest": binding.binding_digest,
                "manifest_path": manifest_path,
                "source_root": source_root,
            }
        )

    files.append(
        DeploymentPackageFile(
            ".twin2multicloud/extensions/bindings.json",
            runtime.canonical_json(
                {
                    "schema_version": "twin-extension-binding-index.v1",
                    "twin_id": str(twin.id),
                    "bindings": index_bindings,
                }
            ),
        )
    )
    return tuple(files)


def _extension_manifest_references(
    files: tuple[DeploymentPackageFile, ...],
) -> list[dict[str, str]]:
    index_path = ".twin2multicloud/extensions/bindings.json"
    index = next((file for file in files if file.path == index_path), None)
    if index is None:
        return []
    document = _load_json_document(index.content, "extension_bindings")
    return [
        {
            "slot_id": item["slot_id"],
            "slot_version": item["slot_version"],
            "artifact_id": item["artifact_id"],
            "artifact_digest": item["artifact_digest"],
            "binding_digest": item["binding_digest"],
        }
        for item in document["bindings"]
    ]


def _materialize_deployer_artifacts(
    dc: "DeployerConfiguration",
    oc: Optional["OptimizerConfiguration"],
    providers: dict,
    *,
    include_user_functions: bool = True,
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

    if dc.state_machine_content:
        l2 = providers.get("layer_2_provider")
        filenames = {
            "aws": "state_machines/aws_step_function.json",
            "azure": "state_machines/azure_logic_app.json",
            "google": "state_machines/google_cloud_workflow.yaml",
        }
        if l2 in filenames:
            files.append(DeploymentPackageFile(filenames[l2], dc.state_machine_content))

    if include_user_functions:
        files.extend(_materialize_user_functions(dc, providers))
    files.extend(_materialize_scene_config(dc, providers))
    return tuple(files)


def _has_legacy_user_functions(dc: "DeployerConfiguration") -> bool:
    return any(
        bool(value)
        for value in (
            dc.processor_contents,
            dc.processor_requirements,
            dc.event_action_contents,
            dc.event_action_requirements,
            dc.event_feedback_content,
            dc.event_feedback_requirements,
        )
    )


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


def _build_main_config(
    twin,
    *,
    optimizer_params: dict[str, Any] | None = None,
) -> dict:
    """Build the main config.json content."""
    # Executable packages pass the immutable calculation-run parameter snapshot.
    # The optional fallback keeps this helper usable for historical read/tests.
    hot_days = 30  # default: 1 month
    cold_days = 90  # default: 3 months
    archive_days = 360  # default: 12 months
    params = optimizer_params
    if params is None and twin.optimizer_config and twin.optimizer_config.params:
        params = _json_object_from_content(
            twin.optimizer_config.params,
            "optimizer_config.params",
        )
    if params is not None:
        hot_days = _months_to_days(params.get("hotStorageDurationInMonths"), 1)
        cold_days = _months_to_days(params.get("coolStorageDurationInMonths"), 3)
        archive_days = _months_to_days(params.get("archiveStorageDurationInMonths"), 12)

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
        "archive_storage_size_in_days": archive_days,
        "mode": mode,
    }


def _build_providers_config(
    resolved_architecture: dict[str, Any],
) -> dict[str, str]:
    """Derive the baseline HCL compatibility projection from graph ownership."""

    key_by_component = {
        "component.ingestion": "layer_1_provider",
        "component.processing": "layer_2_provider",
        "component.hot-storage": "layer_3_hot_provider",
        "component.cool-storage": "layer_3_cold_provider",
        "component.archive-storage": "layer_3_archive_provider",
        "component.twin-state": "layer_4_provider",
        "component.visualization": "layer_5_provider",
    }
    providers: dict[str, str] = {}
    for assignment in resolved_architecture.get("component_assignments", []):
        logical_id = assignment.get("logical_component_id")
        key = key_by_component.get(logical_id)
        if key is None or key in providers:
            raise DeploymentPackageBuildFailed(
                "The selected architecture provider projection is invalid",
                [
                    {
                        "field": "resolved_twin_architecture.component_assignments",
                        "message": "Unknown or duplicate baseline component",
                    }
                ],
            )
        providers[key] = provider_id_for_deployer_project(assignment.get("provider"))
    if set(providers) != set(key_by_component.values()):
        raise DeploymentPackageBuildFailed(
            "The selected architecture provider projection is incomplete",
            [
                {
                    "field": "resolved_twin_architecture.component_assignments",
                    "message": "Every baseline component must be assigned once",
                }
            ],
        )
    return providers


def _build_credentials_config(twin, user_id: str) -> tuple[dict, Optional[dict]]:
    """
    Build config_credentials.json from the credential SSOT resolver.

    The returned values are secret-bearing and must only be written into the
    ephemeral project ZIP uploaded to the Deployer.
    """
    resolved = _build_deployment_credentials(twin, user_id)
    return resolved.config_credentials, resolved.gcp_credentials_json


def _build_deployment_credentials(
    twin,
    user_id: str,
    *,
    required_providers: set[str] | None = None,
) -> DeploymentCredentials:
    """Resolve deployment credentials once for config files and manifest metadata."""
    return CredentialResolutionService().resolve_deployment_credentials(
        twin,
        user_id,
        required_providers=required_providers,
    )


def _build_deployment_manifest(
    twin,
    providers: dict,
    deployment_credentials: DeploymentCredentials,
    file_names: list[str],
    secret_bearing_files: list[str] | None = None,
    *,
    extension_references: Sequence[dict[str, str]] = (),
    resolved_architecture: dict[str, Any],
    deployment_specification: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the secrets-free package manifest.

    The manifest describes package provenance and credential sources only. It
    must never contain credential payloads or decrypted secret values.
    """
    normalized_extension_references = list(extension_references)
    manifest_version = _manifest_version_for_contracts(
        resolved_architecture,
        deployment_specification,
    )
    return {
        "manifest_version": manifest_version,
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
        "calculation_run_id": deployment_specification["calculation_run_id"],
        "resolved_twin_architecture_digest": resolved_architecture["content_digest"],
        "resolved_twin_architecture": resolved_architecture,
        "resolved_deployment_specification_digest": (
            deployment_specification["digest"]
        ),
        "resolved_deployment_specification": deployment_specification,
        "credentials": {
            "providers": list(deployment_credentials.providers),
            "sources": dict(deployment_credentials.sources),
            "contains_secret_payloads": _manifest_contains_secret_payloads(),
        },
        "extensions": {
            "binding_index": (
                ".twin2multicloud/extensions/bindings.json"
                if normalized_extension_references
                else None
            ),
            "bindings": normalized_extension_references,
        },
        "compatibility": {
            "component_catalog_ref": _component_catalog_ref(
                resolved_architecture.get("architecture_profile_ref")
            ),
            "graph_resolver_version": RESOLVED_GRAPH_VERSION,
            "package_builder_version": PACKAGE_BUILDER_VERSION,
            "terraform_input_contract_version": (TERRAFORM_INPUT_CONTRACT_VERSION),
        },
    }


def _manifest_version_for_contracts(
    architecture: dict[str, Any],
    specification: dict[str, Any],
) -> str:
    """Select only an explicitly supported RTA/RDS manifest pairing."""

    pair = (
        architecture.get("schema_version"),
        specification.get("schema_version"),
    )
    if pair == (
        "resolved-twin-architecture.v1",
        "resolved-deployment-specification.v1",
    ):
        return DEPLOYMENT_MANIFEST_VERSION
    if pair == (
        "resolved-twin-architecture.v2",
        "resolved-deployment-specification.v2",
    ):
        return DEPLOYMENT_MANIFEST_V4_VERSION
    raise DeploymentPackageBuildFailed(
        "The selected deployment contracts cannot share a manifest",
        [
            {
                "code": "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
                "field": "deployment_manifest.manifest_version",
                "message": "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
            }
        ],
    )


def _selected_deployment_contracts(
    twin,
    *,
    calculation_run_id: str | None = None,
) -> SelectedDeploymentContracts:
    try:
        runs = tuple(getattr(twin, "cost_calculation_runs", None) or ())
    except TypeError:
        runs = ()
    selected = (
        [run for run in runs if getattr(run, "id", None) == calculation_run_id]
        if calculation_run_id is not None
        else [
            run
            for run in runs
            if getattr(run, "selected_for_deployment_at", None) is not None
        ]
    )
    if len(selected) != 1:
        raise DeploymentPackageBuildFailed(
            (
                "Exactly one deployment-compatible optimizer run with "
                "a resolved architecture must be selected"
            ),
            [
                {
                    "code": "DEPLOYMENT_ARCHITECTURE_MISSING",
                    "field": "cost_calculation_run",
                    "message": ("The frozen or selected optimizer run is unavailable"),
                }
            ],
        )
    try:
        run = selected[0]
        specification = validate_persisted_run_deployment_specification(run)
    except CostCalculationRunSelectionError as exc:
        raise DeploymentPackageBuildFailed(
            "The selected optimizer run is not deployment-compatible",
            [
                {
                    "field": "cost_calculation_run",
                    "message": exc.error_code,
                }
            ],
        ) from exc

    record = getattr(run, "resolved_architecture", None)
    if (
        getattr(run, "architecture_compatibility_status", None) != "ready"
        or record is None
        or getattr(record, "functional_completeness_status", None) != "complete"
    ):
        raise DeploymentPackageBuildFailed(
            "The selected optimizer run has no deployment-ready architecture",
            [
                {
                    "code": "DEPLOYMENT_ARCHITECTURE_MISSING",
                    "field": "resolved_twin_architecture",
                    "message": "DEPLOYMENT_ARCHITECTURE_MISSING",
                }
            ],
        )
    try:
        architecture = json.loads(record.canonical_json)
    except (AttributeError, json.JSONDecodeError, TypeError) as exc:
        raise DeploymentPackageBuildFailed(
            "The selected optimizer architecture is invalid",
            [
                {
                    "field": "resolved_twin_architecture",
                    "message": "DEPLOYMENT_ARCHITECTURE_INVALID",
                }
            ],
        ) from exc
    expected_digest = calculate_architecture_digest(architecture)
    if (
        architecture.get("content_digest") != expected_digest
        or getattr(record, "content_digest", None) != expected_digest
        or getattr(run, "resolved_architecture_digest", None) != expected_digest
    ):
        raise DeploymentPackageBuildFailed(
            "The selected optimizer architecture digest is invalid",
            [
                {
                    "field": "resolved_twin_architecture_digest",
                    "message": "DEPLOYMENT_ARCHITECTURE_DIGEST_MISMATCH",
                }
            ],
        )
    deployment_ref = architecture.get("deployment_specification_ref")
    if (
        architecture.get("calculation_run_id") != run.id
        or specification.specification.get("calculation_run_id") != run.id
        or not isinstance(deployment_ref, dict)
        or deployment_ref.get("calculation_run_id") != run.id
        or deployment_ref.get("schema_version") != specification.schema_version
        or deployment_ref.get("digest") != specification.digest
    ):
        raise DeploymentPackageBuildFailed(
            "The selected architecture and deployment specification differ",
            [
                {
                    "field": "resolved_twin_architecture.deployment_specification_ref",
                    "message": "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
                }
            ],
        )
    return SelectedDeploymentContracts(
        run=run,
        architecture=architecture,
        specification=dict(specification.specification),
    )


def _selected_deployment_specification(twin):
    """Historical test/helper facade; executable packages use both contracts."""

    return validate_persisted_run_deployment_specification(
        _selected_deployment_contracts(twin).run
    )


def _validate_architecture_specification_path(
    providers: dict[str, Any],
    architecture: dict[str, Any],
    specification: dict[str, Any],
) -> None:
    expected_by_key: dict[str, str] = {}
    deployer_key_by_slot = {
        "l1_ingestion": "layer_1_provider",
        "l2_processing": "layer_2_provider",
        "l3_hot_storage": "layer_3_hot_provider",
        "l3_cool_storage": "layer_3_cold_provider",
        "l3_archive_storage": "layer_3_archive_provider",
        "l4_twin_state": "layer_4_provider",
        "l5_visualization": "layer_5_provider",
    }
    for component in specification["components"]:
        slot_id = component["slot_id"]
        deployer_key = deployer_key_by_slot.get(slot_id)
        if deployer_key is None:
            continue
        expected_by_key.setdefault(
            deployer_key,
            provider_id_for_deployer_project(component["provider"]),
        )

    actual = _remove_empty_values(providers)
    if actual != expected_by_key:
        raise DeploymentPackageBuildFailed(
            "Architecture provider projection differs from the selected specification",
            [
                {
                    "field": "providers",
                    "message": "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
                }
            ],
        )
    if actual != _build_providers_config(architecture):
        raise DeploymentPackageBuildFailed(
            "Manifest provider projection differs from the selected architecture",
            [
                {
                    "field": "providers",
                    "message": "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
                }
            ],
        )


def _component_catalog_ref(
    profile_ref: dict[str, Any] | None = None,
) -> dict[str, str]:
    profile_identity = (
        (
            str(profile_ref.get("id") or ""),
            str(profile_ref.get("version") or ""),
        )
        if isinstance(profile_ref, dict)
        else ("five-layer-baseline", "1")
    )
    catalog_families = {
        ("five-layer-baseline", "1"): "baseline",
        ("five-layer-baseline", "2"): "complete-service",
        ("six-layer-eventing", "1"): "six-layer-eventing",
    }
    catalog_family = catalog_families.get(profile_identity)
    if catalog_family is None:
        raise DeploymentPackageBuildFailed(
            "The deployment architecture profile is unsupported",
            [
                {
                    "field": "compatibility.component_catalog_ref",
                    "message": "DEPLOYMENT_PROFILE_CATALOG_MISMATCH",
                }
            ],
        )
    path = (
        ARCHITECTURE_CONTRACT_ROOT
        / "component-catalogs"
        / catalog_family
        / "1"
        / "catalog.json"
    )
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        return {
            "id": catalog["catalog_id"],
            "version": catalog["catalog_version"],
            "digest": catalog["content_digest"],
        }
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise DeploymentPackageBuildFailed(
            "The deployment component catalog is unavailable",
            [
                {
                    "field": "compatibility.component_catalog_ref",
                    "message": "DEPLOYMENT_PROFILE_CATALOG_MISMATCH",
                }
            ],
        ) from exc


def _validate_returned_graph_evidence(
    evidence: dict[str, Any],
    contracts: SelectedDeploymentContracts,
) -> None:
    """Bind Deployer preflight evidence to the exact selected contracts."""

    profile_ref = contracts.architecture.get("architecture_profile_ref")
    catalog_ref = _component_catalog_ref(
        profile_ref if isinstance(profile_ref, dict) else None
    )
    expected = {
        "graph_schema_version": RESOLVED_GRAPH_VERSION,
        "calculation_run_id": contracts.run.id,
        "architecture_digest": contracts.architecture["content_digest"],
        "profile_id": (
            profile_ref.get("id") if isinstance(profile_ref, dict) else None
        ),
        "profile_version": (
            profile_ref.get("version") if isinstance(profile_ref, dict) else None
        ),
        "catalog_id": catalog_ref["id"],
        "catalog_version": catalog_ref["version"],
        "catalog_digest": catalog_ref["digest"],
        "specification_digest": contracts.specification["digest"],
    }
    if any(evidence.get(key) != value for key, value in expected.items()):
        raise DeploymentPackageBuildFailed(
            "Deployer graph evidence differs from the selected contracts",
            [
                {
                    "code": "DEPLOYMENT_GRAPH_RESUME_MISMATCH",
                    "field": "graph_evidence",
                    "message": "DEPLOYMENT_GRAPH_RESUME_MISMATCH",
                }
            ],
        )


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


def _build_optimization_config(
    oc,
    *,
    architecture_profile_ref: Mapping[str, Any] | None = None,
) -> dict:
    """
    Build config_optimization.json with the deployer-expected format.

    The deployer reads: result.inputParamsUsed.{flag} via config_loader.load_optimization_flags()
    These flags control which Terraform resources are conditionally created.
    """
    input_params = {}
    if oc.params:
        params = _json_object_from_content(oc.params, "optimizer_config.params")
        return _build_optimization_config_from_params(
            params,
            field_prefix="optimizer_config.params",
            architecture_profile_ref=architecture_profile_ref,
        )
    return {"result": {"inputParamsUsed": input_params}}


def _build_optimization_config_from_params(
    params: dict[str, Any],
    *,
    field_prefix: str = "cost_calculation_run.params_json",
    architecture_profile_ref: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, dict[str, bool]]]:
    """Project immutable calculation parameters into the Deployer flag contract."""

    _ensure_optimizer_params_are_executable(params, field_prefix=field_prefix)
    profile = _architecture_profile_identity(architecture_profile_ref)
    if profile in PHASE_8_COMPARISON_PROFILES:
        forbidden = sorted(PHASE_8_FORBIDDEN_OPTIMIZER_FIELDS & params.keys())
        if forbidden:
            _raise_package_error(
                field_prefix,
                "FORBIDDEN_PROFILE_FIELD",
                (
                    "Phase 8 comparison profiles do not accept legacy feature "
                    f"flags: {', '.join(forbidden)}"
                ),
            )
        return {"result": {"inputParamsUsed": {}}}
    input_params = {
        "useEventChecking": params.get("useEventChecking") is True,
        "triggerNotificationWorkflow": params.get("triggerNotificationWorkflow")
        is True,
        "returnFeedbackToDevice": params.get("returnFeedbackToDevice") is True,
        "integrateErrorHandling": params.get("integrateErrorHandling") is True,
        "needs3DModel": params.get("needs3DModel") is True,
    }
    return {"result": {"inputParamsUsed": input_params}}


def _architecture_profile_identity(
    reference: Mapping[str, Any] | None,
) -> tuple[str, str] | None:
    if not isinstance(reference, Mapping):
        return None
    profile_id = reference.get("id")
    version = reference.get("version")
    if not isinstance(profile_id, str) or not isinstance(version, str):
        return None
    return profile_id, version


def _validate_phase8_deployer_artifacts(
    deployer_config: Any,
    architecture_profile_ref: Mapping[str, Any] | None,
) -> None:
    if (
        _architecture_profile_identity(architecture_profile_ref)
        not in PHASE_8_COMPARISON_PROFILES
        or deployer_config is None
    ):
        return
    forbidden = [
        field
        for field in PHASE_8_FORBIDDEN_DEPLOYER_FIELDS
        if bool(getattr(deployer_config, field, None))
    ]
    if forbidden:
        _raise_package_error(
            "deployer_config",
            "FORBIDDEN_PROFILE_FIELD",
            (
                "Phase 8 comparison profiles do not accept historical user "
                f"logic or scene artifacts: {', '.join(forbidden)}"
            ),
        )


def _validate_phase8_deployment_regions(
    architecture: Mapping[str, Any],
    providers: Mapping[str, Any],
    credentials: Mapping[str, Any],
) -> None:
    """Keep deployable Phase 8 evidence inside its priced fixed regions."""

    if (
        _architecture_profile_identity(architecture.get("architecture_profile_ref"))
        not in PHASE_8_COMPARISON_PROFILES
    ):
        return
    selected = {
        normalize_provider_id(provider)
        for key, provider in providers.items()
        if key.endswith("_provider") and isinstance(provider, str) and provider
    }
    for provider in sorted(selected):
        payload = credentials.get(provider)
        if not isinstance(payload, Mapping):
            continue
        field = f"{provider}_region"
        expected = PHASE_8_FIXED_REGIONS[provider]
        if payload.get(field) != expected:
            _raise_package_error(
                f"config_credentials.{provider}.{field}",
                "DEPLOYMENT_REGION_UNSUPPORTED",
                (
                    f"{provider.upper()} is fixed to {expected} for the selected "
                    "Phase 8 comparison profile."
                ),
            )
    azure = credentials.get("azure")
    if isinstance(azure, Mapping) and providers.get("layer_1_provider") == "azure":
        expected = PHASE_8_FIXED_REGIONS["azure"]
        if azure.get("azure_region_iothub") not in {None, "", expected}:
            _raise_package_error(
                "config_credentials.azure.azure_region_iothub",
                "DEPLOYMENT_REGION_UNSUPPORTED",
                f"Azure IoT Hub is fixed to {expected} for this profile.",
            )
    if isinstance(azure, Mapping) and providers.get("layer_4_provider") == "azure":
        expected = PHASE_8_FIXED_REGIONS["azure"]
        if azure.get("azure_region_digital_twin") not in {None, "", expected}:
            _raise_package_error(
                "config_credentials.azure.azure_region_digital_twin",
                "DEPLOYMENT_REGION_UNSUPPORTED",
                f"Azure Digital Twins is fixed to {expected} for this profile.",
            )


def _validated_run_params(run: Any) -> dict[str, Any]:
    """Load the immutable calculation input snapshot used by deploy/retry/destroy."""

    raw_params = getattr(run, "params_json", None)
    if not isinstance(raw_params, str):
        _raise_package_error(
            "cost_calculation_run.params_json",
            "DEPLOYMENT_ARCHITECTURE_INVALID",
            "The selected optimizer run has no immutable parameter snapshot.",
        )
    return _json_object_from_content(
        raw_params,
        "cost_calculation_run.params_json",
    )


def _ensure_optimizer_topology_is_executable(
    oc,
    *,
    params: dict[str, Any] | None = None,
) -> None:
    """Reject legacy optimizer state before package or credential processing."""
    if oc is None or not oc.params:
        return
    resolved_params = (
        params
        if params is not None
        else _json_object_from_content(
            oc.params,
            "optimizer_config.params",
        )
    )
    try:
        _ensure_optimizer_params_are_executable(
            resolved_params,
            field_prefix="optimizer_config.params",
        )
    except DeploymentPackageBuildFailed:
        raise


def _ensure_optimizer_params_are_executable(
    params: dict[str, Any],
    *,
    field_prefix: str = "cost_calculation_run.params_json",
) -> None:
    """Validate topology flags from one immutable or legacy parameter document."""

    try:
        ensure_executable_error_handling_topology(params.get(ERROR_HANDLING_FIELD))
    except ValueError:
        _raise_package_error(
            f"{field_prefix}.{ERROR_HANDLING_FIELD}",
            UNSUPPORTED_ERROR_HANDLING_TOPOLOGY,
            UNSUPPORTED_ERROR_HANDLING_MESSAGE,
        )


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
            upstream_status if upstream_status in {400, 409, 413, 422} else 502
        )
        raise DownstreamServiceError(
            status_code=status_code,
            public_detail=(
                "Deployer project setup failed: "
                f"{_redact_deployment_message(exc.public_detail)}"
            ),
        ) from exc


async def prepare_project_for_deployment(
    twin,
    user_id: str,
    *,
    frozen_graph_evidence: dict[str, Any] | None = None,
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
    frozen_run_id = (
        frozen_graph_evidence.get("calculation_run_id")
        if isinstance(frozen_graph_evidence, dict)
        else None
    )
    contracts = _selected_deployment_contracts(
        twin,
        calculation_run_id=(frozen_run_id if isinstance(frozen_run_id, str) else None),
    )
    providers = _build_providers_config(contracts.architecture)

    # Build ZIP
    zip_data = build_project_zip(
        twin,
        user_id,
        calculation_run_id=contracts.run.id,
    )

    # Upload to Deployer
    result = await upload_project_to_deployer(resource_name, zip_data)
    operation_token = result.get("operation_token")
    if not isinstance(operation_token, str) or not operation_token:
        raise DeploymentPackageBuildFailed(
            "Deployer did not return an operation package token",
            [
                {
                    "field": "operation_token",
                    "message": "The staged operation response is incomplete",
                }
            ],
        )
    graph_evidence = result.get("graph_evidence")
    if not isinstance(graph_evidence, dict):
        raise DeploymentPackageBuildFailed(
            "Deployer did not return graph preflight evidence",
            [
                {
                    "field": "graph_evidence",
                    "message": "The staged operation response is incomplete",
                }
            ],
        )
    _validate_returned_graph_evidence(graph_evidence, contracts)

    return PreparedDeploymentProject(
        resource_name=resource_name,
        operation_token=operation_token,
        provider=provider_id_for_deployer_api(providers["layer_1_provider"]),
        graph_evidence=graph_evidence,
    )
