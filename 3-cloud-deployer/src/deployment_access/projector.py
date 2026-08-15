"""Project exact Terraform access bundles into a closed, secret-free contract."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .runtime_evidence import (
    DeploymentAccessRuntimeEvidence,
    DeploymentAccessRuntimeEvidenceError,
    SUPPORTED_DEPLOYMENT_ACCESS_PROFILES,
    surface_output_evidence,
)


class DeploymentAccessProjectionError(ValueError):
    """Raised when selected Layer Access evidence is absent or unsafe."""


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "deployment-access"
    / "v1"
)

SURFACE_DEFINITIONS: dict[tuple[str, str], dict[str, Any]] = {
    ("l4", "aws"): {
        "output_key": "aws_component_twin_state_output",
        "url_key": "access_url",
        "principal_key": "principal_label",
        "required_keys": {"workspace_id", "access_url", "principal_label"},
        "service_id": "aws_iot_twinmaker",
        "display_name": "AWS IoT TwinMaker",
        "auth_mode": "aws_identity_center",
        "credential_action": "none",
        "capabilities": ["entities", "component-types", "current-state", "relationships"],
        "limitations": ["no-scenes", "no-raw-telemetry"],
    },
    ("l4", "azure"): {
        "output_key": "azure_component_twin_state_output",
        "url_key": "access_url",
        "principal_key": "principal_label",
        "required_keys": {
            "instance_name",
            "endpoint",
            "access_url",
            "principal_label",
            "access_role",
        },
        "service_id": "azure_digital_twins",
        "display_name": "Azure Digital Twins Explorer",
        "auth_mode": "azure_entra",
        "credential_action": "none",
        "capabilities": ["models", "twins", "properties", "relationships"],
        "limitations": ["no-scenes", "no-raw-telemetry"],
    },
    ("l4", "gcp"): {
        "output_key": "gcp_component_twin_state_output",
        "url_key": "explorer_url",
        "principal_key": "principal_label",
        "required_keys": {
            "service",
            "materializer_service_id",
            "explorer_url",
            "principal_label",
            "authentication",
            "capabilities",
            "limitations",
            "seed_revision",
            "seed_input_digest",
        },
        "service_id": "gcp_twin_explorer",
        "display_name": "GCP Twin Explorer",
        "auth_mode": "gcp_iap",
        "credential_action": "none",
        "capabilities": ["models", "twins", "current-source-state", "direct-relationships"],
        "limitations": ["read-only", "bounded-queries", "no-scenes", "no-raw-telemetry"],
    },
    ("l5", "aws"): {
        "output_key": "aws_component_visualization_output",
        "url_key": "access_url",
        "principal_key": "principal_label",
        "required_keys": {
            "workspace_id",
            "access_url",
            "workspace_url",
            "reader_url",
            "reader_function_name",
            "principal_label",
        },
        "service_id": "aws_managed_grafana",
        "display_name": "Amazon Managed Grafana",
        "auth_mode": "aws_identity_center",
        "credential_action": "none",
        "capabilities": ["recent-raw", "hourly-rollups", "filters", "no-data-state"],
        "limitations": ["read-only-dashboard", "bounded-queries"],
    },
    ("l5", "azure"): {
        "output_key": "azure_component_visualization_output",
        "url_key": "access_url",
        "principal_key": "principal_label",
        "required_keys": {
            "workspace_name",
            "access_url",
            "workspace_url",
            "reader_url",
            "reader_function_name",
            "principal_label",
            "access_role",
        },
        "service_id": "azure_managed_grafana",
        "display_name": "Azure Managed Grafana",
        "auth_mode": "azure_entra",
        "credential_action": "none",
        "capabilities": ["recent-raw", "hourly-rollups", "filters", "no-data-state"],
        "limitations": ["read-only-dashboard", "bounded-queries"],
    },
    ("l5", "gcp"): {
        "output_key": "gcp_component_visualization_output",
        "url_key": "endpoint",
        "principal_key": "viewer_username",
        "required_keys": {
            "service",
            "endpoint",
            "viewer_username",
            "authentication",
            "certificate_sha256",
            "source_cidrs",
            "dashboard_uid",
            "dashboard_title",
            "reader_service_id",
            "viewer_credential",
            "internal_secrets_output",
            "replica_count",
            "persistent_disk_gib",
        },
        "service_id": "gcp_grafana_oss",
        "display_name": "Grafana OSS on GKE",
        "auth_mode": "generated_viewer",
        "credential_action": "rotate",
        "capabilities": ["recent-raw", "hourly-rollups", "filters", "no-data-state"],
        "limitations": ["read-only-dashboard", "bounded-queries", "self-signed-poc-certificate"],
    },
}


def _evidence_validator() -> Draft202012Validator:
    schemas = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(CONTRACT_ROOT.glob("*.schema.json"))
    ]
    registry = Registry()
    for schema in schemas:
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    evidence = next(
        schema
        for schema in schemas
        if schema["$id"].endswith("deployment-access-evidence.schema.json")
    )
    return Draft202012Validator(
        evidence,
        registry=registry,
        format_checker=FormatChecker(),
    )


def validate_deployment_access_evidence(document: dict[str, Any]) -> None:
    """Fail closed when a projected evidence document leaves the contract."""

    errors = sorted(_evidence_validator().iter_errors(document), key=lambda error: list(error.path))
    if errors:
        raise DeploymentAccessProjectionError(
            f"Deployment Access evidence violates its contract: {errors[0].message}"
        )
    for surface in document["surfaces"]:
        definition = SURFACE_DEFINITIONS.get((surface["layer"], surface["provider"]))
        if definition is None or (
            surface["service_id"],
            surface["auth"]["mode"],
            surface["auth"]["credential_action"],
        ) != (
            definition["service_id"],
            definition["auth_mode"],
            definition["credential_action"],
        ):
            raise DeploymentAccessProjectionError(
                "Deployment Access provider/service/auth combination is not supported"
            )
        parsed = urlsplit(surface["url"])
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise DeploymentAccessProjectionError(
                "Deployment Access URL must be absolute secret-free HTTPS"
            )


def _profile_ref(context: Any) -> tuple[str | None, str | None]:
    graph = getattr(context, "resolved_deployment_graph", None)
    reference = getattr(graph, "profile_ref", {}) if graph is not None else {}
    return reference.get("id"), str(reference.get("version")) if reference.get("version") is not None else None


def _selected_provider(context: Any, layer: str) -> str:
    try:
        provider = context.config.get_provider_for_layer(layer)
    except (AttributeError, KeyError) as exc:
        raise DeploymentAccessProjectionError(
            f"Layer Access cannot resolve provider for {layer}"
        ) from exc
    normalized = str(provider).strip().lower()
    if normalized == "google":
        normalized = "gcp"
    if normalized not in {"aws", "azure", "gcp"}:
        raise DeploymentAccessProjectionError(
            f"Layer Access has unsupported provider {provider!r} for {layer}"
        )
    return normalized


def _surface(
    layer: str,
    provider: str,
    outputs: dict[str, Any],
    runtime_evidence: DeploymentAccessRuntimeEvidence | None,
) -> dict[str, Any]:
    definition = SURFACE_DEFINITIONS[(layer, provider)]
    bundle = outputs.get(definition["output_key"])
    if not isinstance(bundle, dict):
        raise DeploymentAccessProjectionError(
            f"Required safe Terraform output {definition['output_key']} is absent"
        )
    missing = sorted(
        key
        for key in definition["required_keys"]
        if key not in bundle or bundle[key] in (None, "", [])
    )
    if missing:
        raise DeploymentAccessProjectionError(
            f"Safe Terraform output {definition['output_key']} is missing: {', '.join(missing)}"
        )
    if layer == "l5" and provider == "gcp" and bundle["internal_secrets_output"] is not False:
        raise DeploymentAccessProjectionError(
            "GCP visualization output did not prove that internal secrets are excluded"
        )
    try:
        output_evidence = surface_output_evidence(layer, provider, outputs)
    except DeploymentAccessRuntimeEvidenceError as exc:
        raise DeploymentAccessProjectionError(str(exc)) from exc
    runtime_surface = (
        runtime_evidence.surface(layer, provider)
        if runtime_evidence is not None
        else None
    )
    if runtime_evidence is not None and runtime_surface is None:
        raise DeploymentAccessProjectionError(
            f"Layer Access runtime evidence is missing {layer}/{provider}"
        )
    if runtime_surface is not None and runtime_surface != output_evidence:
        raise DeploymentAccessProjectionError(
            f"Layer Access runtime evidence does not match {layer}/{provider} outputs"
        )
    runtime_ready = runtime_surface is not None
    return {
        "layer": layer,
        "provider": provider,
        "service_id": definition["service_id"],
        "display_name": definition["display_name"],
        "url": str(bundle[definition["url_key"]]),
        "auth": {
            "mode": definition["auth_mode"],
            "principal_label": str(bundle[definition["principal_key"]]),
            "credential_action": definition["credential_action"],
        },
        "readiness": {
            "resource": "ready",
            "access_binding": "ready",
            "content": "ready" if runtime_ready else "pending",
            "data_probe": "ready" if runtime_ready else "pending",
            "browser_sign_in": "unverified",
        },
        "capabilities": list(definition["capabilities"]),
        "limitations": list(definition["limitations"]),
    }


def project_deployment_access_evidence(
    context: Any,
    outputs: dict[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any] | None:
    """Return exact active-profile L4/L5 evidence, or None otherwise."""

    profile_id, profile_version = _profile_ref(context)
    if (profile_id, profile_version) not in SUPPORTED_DEPLOYMENT_ACCESS_PROFILES:
        return None
    if not isinstance(outputs, dict):
        raise DeploymentAccessProjectionError("Terraform outputs must be an object")
    runtime_evidence = getattr(context, "deployment_access_runtime_evidence", None)
    if runtime_evidence is not None and not isinstance(
        runtime_evidence, DeploymentAccessRuntimeEvidence
    ):
        raise DeploymentAccessProjectionError(
            "Layer Access runtime evidence has an invalid type"
        )
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    evidence = {
        "schema_version": "deployment-access-evidence.v1",
        "profile_id": profile_id,
        "profile_version": profile_version,
        "generated_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "surfaces": [
            _surface(
                "l4",
                _selected_provider(context, "4"),
                outputs,
                runtime_evidence,
            ),
            _surface(
                "l5",
                _selected_provider(context, "5"),
                outputs,
                runtime_evidence,
            ),
        ],
    }
    validate_deployment_access_evidence(evidence)
    return evidence
