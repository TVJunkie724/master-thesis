"""Build and validate ResolvedDeploymentSpecification v1 from typed layer results."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker

from backend.calculation_v2.layers import ComponentDeploymentSelection
from backend.calculation_v2.strategy_context import (
    CalculationStrategyExecutionContext,
)
from backend.pricing_catalog_models import PricingCatalogContext


SCHEMA_VERSION = "resolved-deployment-specification.v1"
REGISTRY_VERSION = "resolved-deployment-dimensions.v1"
SOURCE_CURRENCY = "USD"
PROVIDERS = ("aws", "azure", "gcp")
LAYER_TO_SLOT = {
    "L1": "l1_ingestion",
    "L2": "l2_processing",
    "L3_hot": "l3_hot_storage",
    "L3_cool": "l3_cool_storage",
    "L3_archive": "l3_archive_storage",
    "L4": "l4_twin_state",
    "L5": "l5_visualization",
}
PROVIDER_LABELS = {
    "AWS": "aws",
    "Azure": "azure",
    "GCP": "gcp",
}
SECRET_KEY_FRAGMENTS = (
    "access_key",
    "client_secret",
    "connection_string",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v1"
)


class DeploymentSpecificationBuildError(ValueError):
    """Stable fail-closed error for incomplete or unsupported selections."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _fail(code: str, message: str) -> NoReturn:
    raise DeploymentSpecificationBuildError(code, message)


@lru_cache(maxsize=1)
def _contract() -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        schema = json.loads((CONTRACT_ROOT / "schema.json").read_text("utf-8"))
        registry = json.loads(
            (CONTRACT_ROOT / "deployment-dimensions.json").read_text("utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Resolved deployment contract is unavailable") from exc
    Draft202012Validator.check_schema(schema)
    if registry.get("registry_version") != REGISTRY_VERSION:
        raise RuntimeError("Resolved deployment registry version is unsupported")
    if registry.get("specification_schema_version") != SCHEMA_VERSION:
        raise RuntimeError("Resolved deployment schema and registry versions differ")
    return schema, registry


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(specification: Mapping[str, Any]) -> str:
    payload = dict(specification)
    payload.pop("digest", None)
    encoded = _canonical_json(payload).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _walk_keys(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in SECRET_KEY_FRAGMENTS):
                _fail(
                    "invalid_deployment_specification",
                    f"Secret-like field is forbidden at {path}.{key}",
                )
            _walk_keys(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_keys(nested, f"{path}[{index}]")


def _selection_payloads(layer_payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = layer_payload.get("deploymentSelections")
    if not isinstance(values, list) or not values:
        _fail(
            "incomplete_deployment_specification",
            "Selected layer has no deployment selections",
        )
    if any(not isinstance(value, Mapping) for value in values):
        _fail(
            "invalid_deployment_specification",
            "Layer deployment selections must be objects",
        )
    return values


def _required_glue_providers(
    registry: Mapping[str, Any],
    provider_by_slot: Mapping[str, str],
) -> tuple[str, ...]:
    required: set[str] = set()
    for boundary in registry["cross_cloud_glue_policy"]["boundaries"]:
        source = provider_by_slot[boundary["source_slot"]]
        target = provider_by_slot[boundary["target_slot"]]
        if source != target:
            required.add(provider_by_slot[boundary["receiver_slot"]])
    return tuple(provider for provider in PROVIDERS if provider in required)


def _required_transition_components(
    registry: Mapping[str, Any],
    provider_by_slot: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            transition["boundary_id"],
            transition["component_by_provider"][
                provider_by_slot[transition["source_slot"]]
            ],
        )
        for transition in registry["transition_runtime_policy"][
            "transitions"
        ]
    )


def _exact_value_type(value: object, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return isinstance(value, str) if expected == "string" else False


def _validate_value(
    component_id: str,
    dimension_id: str,
    value: object,
    definition: Mapping[str, Any],
) -> None:
    if not _exact_value_type(value, definition["value_type"]):
        _fail(
            "unsupported_deployment_selection",
            f"{component_id}/{dimension_id} has the wrong value type",
        )
    if "allowed_values" in definition and value not in definition["allowed_values"]:
        _fail(
            "unsupported_deployment_selection",
            f"{component_id}/{dimension_id} has an unsupported value",
        )
    if "minimum" in definition and value < definition["minimum"]:
        _fail(
            "unsupported_deployment_selection",
            f"{component_id}/{dimension_id} is below its minimum",
        )
    if "maximum" in definition and value > definition["maximum"]:
        _fail(
            "unsupported_deployment_selection",
            f"{component_id}/{dimension_id} exceeds its maximum",
        )


def _build_component(
    selection: Mapping[str, Any],
    *,
    registry: Mapping[str, Any],
    optimization_context: Mapping[str, Any],
) -> dict[str, Any]:
    component_id = selection.get("componentId")
    registered = registry["components"].get(component_id)
    if not isinstance(component_id, str) or not isinstance(registered, Mapping):
        _fail(
            "unsupported_deployment_selection",
            "Layer result contains an unknown deployment component",
        )
    values = selection.get("dimensions")
    if not isinstance(values, Mapping):
        _fail(
            "invalid_deployment_specification",
            f"{component_id} dimensions must be an object",
        )
    definitions = registered["dimensions"]
    if list(values) != list(definitions):
        _fail(
            "incomplete_deployment_specification",
            f"{component_id} dimensions differ from the canonical registry",
        )

    dimensions = []
    for dimension_id, definition in definitions.items():
        value = values[dimension_id]
        _validate_value(component_id, dimension_id, value, definition)
        resolution = registry["dimension_resolution"][dimension_id]
        if definition["classification"] == "account_scope":
            evidence_reference = f"provider_context:{registered['provider']}"
        elif resolution == "baseline_invariant":
            evidence_reference = (
                f"deployment_registry:{registry['registry_version']}"
            )
        elif resolution == "formula_input":
            evidence_reference = (
                "workload_contract:"
                f"{optimization_context['workload_contract_id']}"
            )
        else:
            evidence_reference = (
                "catalog:"
                f"{optimization_context['catalog_references'][registered['provider']]['snapshot_id']}"
            )
        dimension = {
            "dimension_id": dimension_id,
            "classification": definition["classification"],
            "value": value,
            "formula_reference": (
                f"formula_set:{optimization_context['formula_set_id']}"
            ),
            "evidence_reference": evidence_reference,
        }
        unit = registry["dimension_units"].get(dimension_id)
        if unit is not None:
            dimension["unit"] = unit
        target = definition.get("terraform_target")
        if target is not None:
            dimension["terraform_target"] = target
        dimensions.append(dimension)

    dimension_values = {
        dimension["dimension_id"]: dimension["value"] for dimension in dimensions
    }
    for constraint in registered.get("combination_constraints", []):
        selector = dimension_values[constraint["selector_dimension"]]
        dependent = dimension_values[constraint["dependent_dimension"]]
        limits = constraint["ranges_by_selector"][selector]
        if not limits["minimum"] <= dependent <= limits["maximum"]:
            _fail(
                "unsupported_deployment_selection",
                f"{component_id} contains an invalid dimension combination",
            )

    return {
        "component_id": component_id,
        "slot_id": registered["slot_id"],
        "provider": registered["provider"],
        "service_id": registered["service_id"],
        "required": True,
        "dimensions": dimensions,
    }


def _catalog_references(
    context: PricingCatalogContext,
) -> dict[str, dict[str, str]]:
    return {
        provider: {
            "snapshot_id": context.catalogs[provider].snapshot_id,
            "pricing_region": context.catalogs[provider].pricing_region,
            "content_digest": context.catalogs[provider].content_digest,
        }
        for provider in PROVIDERS
    }


def _validate_component_set(components: list[Mapping[str, Any]]) -> None:
    component_ids = [component["component_id"] for component in components]
    if len(component_ids) != len(set(component_ids)):
        _fail(
            "unsupported_deployment_selection",
            "Resolved component IDs must be unique",
        )

    target_values: dict[str, object] = {}
    for component in components:
        for dimension in component["dimensions"]:
            target = dimension.get("terraform_target")
            if target is None:
                continue
            previous = target_values.setdefault(target, dimension["value"])
            if previous != dimension["value"]:
                _fail(
                    "unsupported_deployment_selection",
                    f"Terraform target {target} has contradictory values",
                )


def build_resolved_deployment_specification(
    *,
    calculation_run_id: str,
    selected_providers: Mapping[str, str],
    provider_costs: Mapping[str, Mapping[str, Any]],
    glue_selections: Mapping[str, ComponentDeploymentSelection],
    transition_runtime_selections: Mapping[
        str,
        ComponentDeploymentSelection,
    ],
    optimization_metadata: Mapping[str, Any],
    execution_context: CalculationStrategyExecutionContext,
    pricing_catalog_context: PricingCatalogContext,
) -> dict[str, Any]:
    """Build one complete, deterministic v1 specification for the winning path."""

    schema, registry = _contract()
    if set(selected_providers) != set(LAYER_TO_SLOT):
        _fail(
            "incomplete_deployment_specification",
            "Winner does not cover every baseline slot",
        )
    if set(provider_costs) != {"AWS", "Azure", "GCP"}:
        _fail(
            "incomplete_deployment_specification",
            "Provider layer results do not cover AWS, Azure, and GCP",
        )

    optimization_context = {
        "optimization_profile_id": execution_context.optimization_profile_id,
        "optimization_profile_version": optimization_metadata.get(
            "profile_version"
        ),
        "calculation_strategy_id": execution_context.calculation_strategy_id,
        "formula_set_id": execution_context.formula_set_id,
        "workload_contract_id": execution_context.workload_contract_id,
        "pricing_registry_version": optimization_metadata.get(
            "pricing_registry_version"
        ),
        "catalog_references": _catalog_references(pricing_catalog_context),
    }

    components: list[dict[str, Any]] = []
    provider_by_slot: dict[str, str] = {}
    for layer_key, slot_id in LAYER_TO_SLOT.items():
        provider_label = selected_providers[layer_key]
        provider = PROVIDER_LABELS.get(provider_label)
        if provider is None:
            _fail(
                "deployment_specification_provider_mismatch",
                f"Winner selected unsupported provider {provider_label!r}",
            )
        provider_by_slot[slot_id] = provider
        layer_payload = provider_costs[provider_label].get(layer_key)
        if not isinstance(layer_payload, Mapping) or layer_payload.get(
            "supported"
        ) is not True:
            _fail(
                "deployment_specification_provider_mismatch",
                f"{provider_label} does not support selected layer {layer_key}",
            )

        selections = _selection_payloads(layer_payload)
        requirement = registry["slot_requirements"][slot_id].get(provider)
        if not isinstance(requirement, Mapping):
            _fail(
                "deployment_specification_provider_mismatch",
                f"{provider} does not implement {slot_id}",
            )
        actual_ids = [selection.get("componentId") for selection in selections]
        required = requirement["required_components"]
        optional = requirement["optional_components"]
        expected_ids = [
            *required,
            *(component_id for component_id in optional if component_id in actual_ids),
        ]
        if actual_ids != expected_ids:
            _fail(
                "incomplete_deployment_specification",
                f"{provider}/{slot_id} components differ from the registry",
            )
        components.extend(
            _build_component(
                selection,
                registry=registry,
                optimization_context=optimization_context,
            )
            for selection in selections
        )

    for edge_id, component_id in _required_transition_components(
        registry,
        provider_by_slot,
    ):
        selection = transition_runtime_selections.get(edge_id)
        if (
            not isinstance(selection, ComponentDeploymentSelection)
            or selection.component_id != component_id
        ):
            _fail(
                "incomplete_deployment_specification",
                f"Missing source-owned transition runtime for {edge_id}",
            )
        components.append(
            _build_component(
                selection.as_dict(),
                registry=registry,
                optimization_context=optimization_context,
            )
        )

    glue_component_by_provider = registry["cross_cloud_glue_policy"][
        "component_by_provider"
    ]
    for provider in _required_glue_providers(registry, provider_by_slot):
        selection = glue_selections.get(provider)
        if (
            not isinstance(selection, ComponentDeploymentSelection)
            or selection.component_id != glue_component_by_provider[provider]
        ):
            _fail(
                "incomplete_deployment_specification",
                f"Missing canonical cross-cloud glue selection for {provider}",
            )
        components.append(
            _build_component(
                selection.as_dict(),
                registry=registry,
                optimization_context=optimization_context,
            )
        )

    _validate_component_set(components)
    specification = {
        "schema_version": SCHEMA_VERSION,
        "calculation_run_id": calculation_run_id,
        "architecture_profile": dict(registry["architecture_profile"]),
        "optimization_context": optimization_context,
        "currency": SOURCE_CURRENCY,
        "components": components,
    }
    specification["digest"] = _digest(specification)
    _walk_keys(specification)

    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(specification),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        _fail(
            "invalid_deployment_specification",
            f"Schema validation failed at {location}: {error.message}",
        )
    return specification
