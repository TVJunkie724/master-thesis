"""Digest-bound, bounded account preparation for the thesis PoC."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

import file_manager
from src.architecture_profiles.graph_evidence import content_digest
from src.core.observability import redact_sensitive
from src.core.project_storage import ProjectStorage
from src.operation_packages import (
    DeploymentRequirementsInspection,
    inspect_deployment_requirements,
)


ActionExecutor = Callable[[str, str, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class AccountPreparationResult:
    project_name: str
    plan_digest: str
    requirements_digest: str
    status: str
    completed_actions: tuple[dict[str, Any], ...]
    failed_actions: tuple[dict[str, Any], ...]
    remaining_actions: tuple[dict[str, Any], ...]
    retry_safe: bool = True


def build_account_preparation_plan(
    inspection: DeploymentRequirementsInspection,
) -> dict[str, Any]:
    """Project graph requirements into an exact reviewable mutation plan."""

    actions = []
    manual_requirements = []
    for requirement in inspection.requirements:
        provider = requirement["provider"]
        capability = requirement["capability_id"]
        requirement_type = requirement["requirement_type"]
        mode = requirement["preparation_mode"]
        if mode == "confirmed_account" and (
            (provider == "azure" and requirement_type == "resource_provider")
            or (provider == "gcp" and requirement_type == "api")
        ):
            action_type = (
                "register_resource_provider"
                if provider == "azure"
                else "enable_project_api"
            )
            actions.append(
                {
                    "action_id": f"prepare.{provider}.{action_type}.{capability}",
                    "provider": provider,
                    "action_type": action_type,
                    "capability_id": capability,
                    "scope": requirement["scope"],
                    "requirement_ids": [requirement["requirement_id"]],
                    "reason": "Required by the resolved deployment graph.",
                    "persistent_after_destroy": True,
                    "destructive": False,
                }
            )
        elif mode == "manual_external" or (
            provider == "aws" and capability == "aws.outbound-identity-federation"
        ):
            manual_requirements.append(
                {
                    "requirement_id": requirement["requirement_id"],
                    "provider": provider,
                    "capability_id": capability,
                    "reason": "No bounded, reviewed PoC automation is available.",
                }
            )

    actions = sorted(actions, key=lambda item: item["action_id"])
    manual_requirements = sorted(
        manual_requirements,
        key=lambda item: item["requirement_id"],
    )
    plan_body = {
        "schema_version": "graph-account-preparation.v1",
        "graph_digest": inspection.graph_evidence["graph_digest"],
        "requirements_digest": inspection.graph_evidence["requirements_digest"],
        "actions": actions,
        "manual_requirements": manual_requirements,
    }
    return {**plan_body, "plan_digest": content_digest(plan_body)}


def execute_account_preparation(
    project_name: str,
    archive: bytes,
    *,
    expected_plan_digest: str,
    confirmed: bool,
    executor: ActionExecutor | None = None,
    project_storage: ProjectStorage | None = None,
) -> AccountPreparationResult:
    """Execute only the graph-derived, reviewed, idempotent action allowlist."""

    if not confirmed:
        raise ValueError("Explicit account-preparation confirmation is required")
    storage = project_storage or ProjectStorage()
    inspection = inspect_deployment_requirements(
        project_name,
        archive,
        project_storage=storage,
    )
    plan = build_account_preparation_plan(inspection)
    if plan["plan_digest"] != expected_plan_digest:
        raise ValueError("Account-preparation plan is stale")

    credentials = _load_credentials(project_name, archive, storage)
    action_executor = executor or _execute_provider_action
    completed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    actions = list(plan["actions"])
    for action in actions:
        provider = action["provider"]
        try:
            provider_credentials = credentials.get(provider)
            if not isinstance(provider_credentials, dict):
                raise ValueError(f"Missing {provider} deployment credentials")
            evidence = action_executor(
                provider,
                action["capability_id"],
                provider_credentials,
            )
            completed.append(
                {
                    "action_id": action["action_id"],
                    "provider": provider,
                    "capability_id": action["capability_id"],
                    "status": "ready",
                    "message": str(evidence.get("message") or "Preparation completed.")[
                        :2_000
                    ],
                }
            )
        except Exception as exc:  # noqa: BLE001 - preserve partial provider result
            failed.append(
                {
                    "action_id": action["action_id"],
                    "provider": provider,
                    "capability_id": action["capability_id"],
                    "status": "failed",
                    "message": str(redact_sensitive(exc))[:2_000],
                }
            )

    failed_ids = {item["action_id"] for item in failed}
    remaining = [action for action in actions if action["action_id"] in failed_ids]
    status = "ready" if not failed else "partial" if completed else "failed"
    return AccountPreparationResult(
        project_name=inspection.project_name,
        plan_digest=plan["plan_digest"],
        requirements_digest=plan["requirements_digest"],
        status=status,
        completed_actions=tuple(completed),
        failed_actions=tuple(failed),
        remaining_actions=tuple(remaining),
    )


def _load_credentials(
    project_name: str,
    archive: bytes,
    storage: ProjectStorage,
) -> dict[str, Any]:
    safe_name = storage.context(project_name).project_name
    path = Path(tempfile.mkdtemp(prefix="twin2multicloud-preparation-")).resolve()
    path.chmod(0o700)
    try:
        file_manager.extract_operation_archive(safe_name, archive, path)
        value = json.loads((path / "config_credentials.json").read_text("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Deployment credentials must be an object")
        return value
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _execute_provider_action(
    provider: str,
    capability_id: str,
    credentials: dict[str, Any],
) -> dict[str, Any]:
    if provider == "azure":
        return _register_azure_resource_provider(capability_id, credentials)
    if provider == "gcp":
        return _enable_gcp_api(capability_id, credentials)
    raise ValueError(f"Unsupported automated account preparation: {provider}")


def _register_azure_resource_provider(
    namespace: str,
    credentials: dict[str, Any],
) -> dict[str, Any]:
    from azure.identity import ClientSecretCredential
    from azure.mgmt.resource.resources import ResourceManagementClient

    credential = ClientSecretCredential(
        tenant_id=credentials["azure_tenant_id"],
        client_id=credentials["azure_client_id"],
        client_secret=credentials["azure_client_secret"],
    )
    client = ResourceManagementClient(
        credential,
        credentials["azure_subscription_id"],
    )
    current = client.providers.get(namespace)
    if str(getattr(current, "registration_state", "")).lower() == "registered":
        return {"message": f"{namespace} is already registered."}
    result = client.providers.register(namespace)
    state = str(getattr(result, "registration_state", "submitted"))
    return {"message": f"{namespace} registration state: {state}."}


def _enable_gcp_api(
    api: str,
    credentials: dict[str, Any],
) -> dict[str, Any]:
    from google.cloud import service_usage_v1
    from google.oauth2 import service_account

    info = json.loads(credentials["gcp_credentials_file"])
    credential = service_account.Credentials.from_service_account_info(info)
    project_id = str(credentials["gcp_project_id"])
    name = f"projects/{project_id}/services/{api}"
    client = service_usage_v1.ServiceUsageClient(credentials=credential)
    service = client.get_service(request={"name": name})
    state = getattr(service, "state", None)
    state_name = str(getattr(state, "name", state)).upper()
    if state_name.endswith("ENABLED"):
        return {"message": f"{api} is already enabled."}
    operation = client.enable_service(request={"name": name})
    operation.result(timeout=120)
    return {"message": f"{api} is enabled."}


__all__ = [
    "AccountPreparationResult",
    "build_account_preparation_plan",
    "execute_account_preparation",
]
