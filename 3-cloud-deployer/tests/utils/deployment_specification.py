"""Canonical standalone Six-layer fixtures for Deployer tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from src.architecture_profiles.contracts import calculate_digest as architecture_digest
from src.deployment_specification import calculate_digest as specification_digest


GENERATED_CONTRACT_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "contracts" / "generated"
)
SPECIFICATION_ROOT = (
    GENERATED_CONTRACT_ROOT / "resolved-deployment-specification" / "v2"
)
MANIFEST_ROOT = GENERATED_CONTRACT_ROOT / "deployment-manifest" / "v4"
SIX_LAYER_FIXTURE = "six-layer-aws-azure-eventing-small.json"
DEFAULT_PACKAGE_FILES = [
    "config.json",
    "config_credentials.json",
    "config_events.json",
    "config_iot_devices.json",
    "config_providers.json",
]
LOGICAL_PROVIDER_KEYS = {
    "component.ingestion": "layer_1_provider",
    "component.processing": "layer_2_provider",
    "component.hot-storage": "layer_3_hot_provider",
    "component.cool-storage": "layer_3_cold_provider",
    "component.archive-storage": "layer_3_archive_provider",
    "component.twin-state": "layer_4_provider",
    "component.visualization": "layer_5_provider",
}


def _canonical_manifest() -> dict[str, Any]:
    return json.loads(
        (MANIFEST_ROOT / "fixtures" / "valid" / SIX_LAYER_FIXTURE).read_text("utf-8")
    )


def load_specification(
    fixture_name: str = SIX_LAYER_FIXTURE,
    *,
    validity: str = "valid",
) -> dict[str, Any]:
    payload = json.loads(
        (SPECIFICATION_ROOT / "fixtures" / validity / fixture_name).read_text("utf-8")
    )
    return payload.get("specification", payload)


def provider_config_for_specification(
    specification: dict[str, Any],
) -> dict[str, str]:
    providers: dict[str, str] = {}
    for selection in specification.get("component_selections", []):
        logical_id = selection.get("logical_component_id")
        key = LOGICAL_PROVIDER_KEYS.get(logical_id)
        provider = selection.get("provider")
        if key is not None and isinstance(provider, str):
            providers.setdefault(key, provider)
    return providers


def deployment_manifest(
    specification: dict[str, Any] | None = None,
    *,
    providers: dict[str, str] | None = None,
    package_files: list[str] | None = None,
    resource_name: str = "factory",
) -> dict[str, Any]:
    manifest = deepcopy(_canonical_manifest())
    architecture = manifest["resolved_twin_architecture"]
    architecture["resolution_status"] = "publishable"
    selected_specification = deepcopy(
        specification or manifest["resolved_deployment_specification"]
    )
    selected_specification["readiness"] = {
        "status": "deployment_ready",
        "blocking_gate_ids": [],
    }
    selected_specification["digest"] = specification_digest(selected_specification)
    architecture["deployment_specification_ref"]["digest"] = selected_specification[
        "digest"
    ]
    architecture["content_digest"] = architecture_digest(architecture)
    provider_config = providers or provider_config_for_specification(
        selected_specification
    )
    manifest["resolved_deployment_specification"] = selected_specification
    manifest["resolved_deployment_specification_digest"] = selected_specification[
        "digest"
    ]
    manifest["resolved_twin_architecture_digest"] = architecture["content_digest"]
    manifest["calculation_run_id"] = selected_specification["calculation_run_id"]
    manifest["providers"] = dict(provider_config)
    manifest["package"]["files"] = list(package_files or DEFAULT_PACKAGE_FILES)
    manifest["twin"]["resource_name"] = resource_name
    manifest["twin"]["name"] = resource_name
    credential_providers = sorted(set(provider_config.values()))
    manifest["credentials"] = {
        "providers": credential_providers,
        "sources": {provider: "cloud_connection" for provider in credential_providers},
        "contains_secret_payloads": False,
    }
    return manifest
