"""Canonical deployment specification fixtures for Deployer tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from src.deployment_specification import calculate_digest
from src.deployment_specification.contract import SLOT_ORDER


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v1"
)
DEFAULT_PACKAGE_FILES = [
    "config.json",
    "config_iot_devices.json",
    "config_events.json",
    "config_credentials.json",
    "config_providers.json",
]


def load_registry() -> dict[str, Any]:
    return json.loads(
        (CONTRACT_ROOT / "deployment-dimensions.json").read_text("utf-8")
    )


def load_verification_matrix() -> dict[str, Any]:
    return json.loads(
        (CONTRACT_ROOT / "verification-matrix.json").read_text("utf-8")
    )


def load_specification(
    fixture_name: str = "all-aws.json",
    *,
    validity: str = "valid",
) -> dict[str, Any]:
    payload = json.loads(
        (CONTRACT_ROOT / "fixtures" / validity / fixture_name).read_text("utf-8")
    )
    return payload.get("specification", payload)


def build_specification_for_path(
    provider_by_slot: dict[str, str],
    *,
    terraform_target_overrides: dict[str, str | int | bool] | None = None,
) -> dict[str, Any]:
    """Build one valid closed-world specification from independent test inputs."""

    registry = load_registry()
    matrix = load_verification_matrix()
    overrides = terraform_target_overrides or {}
    base = load_specification()
    components: list[dict[str, Any]] = []

    for slot_id in SLOT_ORDER:
        provider = provider_by_slot[slot_id]
        requirement = registry["slot_requirements"][slot_id][provider]
        for component_id in requirement["required_components"]:
            components.append(
                _build_component(
                    component_id,
                    base=base,
                    registry=registry,
                    matrix=matrix,
                    overrides=overrides,
                )
            )

    for transition in registry["transition_runtime_policy"]["transitions"]:
        provider = provider_by_slot[transition["source_slot"]]
        components.append(
            _build_component(
                transition["component_by_provider"][provider],
                base=base,
                registry=registry,
                matrix=matrix,
                overrides=overrides,
            )
        )

    glue_providers = {
        provider_by_slot[boundary["receiver_slot"]]
        for boundary in registry["cross_cloud_glue_policy"]["boundaries"]
        if provider_by_slot[boundary["source_slot"]]
        != provider_by_slot[boundary["target_slot"]]
    }
    for provider in matrix["providers"]:
        if provider not in glue_providers:
            continue
        components.append(
            _build_component(
                registry["cross_cloud_glue_policy"]["component_by_provider"][
                    provider
                ],
                base=base,
                registry=registry,
                matrix=matrix,
                overrides=overrides,
            )
        )

    specification = {
        key: deepcopy(value)
        for key, value in base.items()
        if key not in {"components", "digest"}
    }
    specification["components"] = components
    specification["digest"] = calculate_digest(specification)
    return specification


def _build_component(
    component_id: str,
    *,
    base: dict[str, Any],
    registry: dict[str, Any],
    matrix: dict[str, Any],
    overrides: dict[str, str | int | bool],
) -> dict[str, Any]:
    definition = registry["components"][component_id]
    dimensions: list[dict[str, Any]] = []
    for dimension_id, dimension_definition in definition["dimensions"].items():
        target = dimension_definition.get("terraform_target")
        value = _dimension_value(
            component_id,
            target,
            dimension_definition,
            matrix=matrix,
            overrides=overrides,
        )
        dimension = {
            "dimension_id": dimension_id,
            "classification": dimension_definition["classification"],
            "value": value,
            "formula_reference": (
                f"formula_set:{base['optimization_context']['formula_set_id']}"
            ),
            "evidence_reference": _evidence_reference(
                definition["provider"],
                dimension_id,
                dimension_definition,
                base=base,
                registry=registry,
            ),
        }
        unit = registry["dimension_units"].get(dimension_id)
        if unit is not None:
            dimension["unit"] = unit
        if target is not None:
            dimension["terraform_target"] = target
        dimensions.append(dimension)

    return {
        "component_id": component_id,
        "slot_id": definition["slot_id"],
        "provider": definition["provider"],
        "service_id": definition["service_id"],
        "required": True,
        "dimensions": dimensions,
    }


def _dimension_value(
    component_id: str,
    terraform_target: str | None,
    definition: dict[str, Any],
    *,
    matrix: dict[str, Any],
    overrides: dict[str, str | int | bool],
) -> str | int | bool:
    if terraform_target is not None:
        if terraform_target in overrides:
            return overrides[terraform_target]
        return matrix["expected_targets_by_component"][component_id][
            terraform_target
        ]
    if definition.get("allowed_values"):
        return definition["allowed_values"][0]
    if definition["value_type"] == "integer":
        return definition["minimum"]
    if definition["value_type"] == "boolean":
        return False
    raise AssertionError(f"No deterministic test value for {component_id}")


def _evidence_reference(
    provider: str,
    dimension_id: str,
    definition: dict[str, Any],
    *,
    base: dict[str, Any],
    registry: dict[str, Any],
) -> str:
    classification = definition["classification"]
    if classification == "account_scope":
        return f"provider_context:{provider}"
    resolution = registry["dimension_resolution"][dimension_id]
    if resolution == "baseline_invariant":
        return f"deployment_registry:{registry['registry_version']}"
    if resolution == "formula_input":
        workload_id = base["optimization_context"]["workload_contract_id"]
        return f"workload_contract:{workload_id}"
    snapshot_id = base["optimization_context"]["catalog_references"][provider][
        "snapshot_id"
    ]
    return f"catalog:{snapshot_id}"


def provider_config_for_specification(
    specification: dict[str, Any],
) -> dict[str, str]:
    registry = load_registry()
    providers: dict[str, str] = {}
    for slot_id, slot in registry["slots"].items():
        deployer_key = slot["deployer_key"]
        if deployer_key is None:
            continue
        component = next(
            (
                item
                for item in specification.get("components", [])
                if item.get("slot_id") == slot_id
            ),
            None,
        )
        providers[deployer_key] = (
            component.get("provider", "aws")
            if isinstance(component, dict)
            else "aws"
        )
    return providers


def deployment_manifest(
    specification: dict[str, Any] | None = None,
    *,
    providers: dict[str, str] | None = None,
    package_files: list[str] | None = None,
    resource_name: str = "factory",
) -> dict[str, Any]:
    specification = deepcopy(specification or load_specification())
    provider_config = providers or provider_config_for_specification(specification)
    return {
        "manifest_version": "2.0",
        "producer": "test",
        "package": {
            "format": "deployer-project-zip",
            "files": list(package_files or DEFAULT_PACKAGE_FILES),
            "required_files": list(DEFAULT_PACKAGE_FILES),
            "secret_bearing_files": ["config_credentials.json"],
        },
        "twin": {"resource_name": resource_name},
        "providers": dict(provider_config),
        "calculation_run_id": specification["calculation_run_id"],
        "resolved_deployment_specification_digest": specification["digest"],
        "resolved_deployment_specification": specification,
        "credentials": {
            "providers": sorted(set(provider_config.values())),
            "sources": {
                provider: "cloud_connection"
                for provider in sorted(set(provider_config.values()))
            },
            "contains_secret_payloads": False,
        },
    }
