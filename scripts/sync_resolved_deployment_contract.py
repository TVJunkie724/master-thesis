#!/usr/bin/env python3
"""Validate and synchronize the ResolvedDeploymentSpecification contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_NAME = "resolved-deployment-specification"
SOURCE_ROOT = ROOT / "contracts" / CONTRACT_NAME
SOURCE_V1 = SOURCE_ROOT / "v1"
GENERATED_ROOTS = (
    ROOT / "2-twin2clouds" / "backend" / "contracts" / "generated",
    ROOT / "twin2multicloud_backend" / "src" / "contracts" / "generated",
    ROOT / "3-cloud-deployer" / "src" / "contracts" / "generated",
)
BASELINE_SLOTS = (
    "l1_ingestion",
    "l2_processing",
    "l3_hot_storage",
    "l3_cool_storage",
    "l3_archive_storage",
    "l4_twin_state",
    "l5_visualization",
)
PROVIDERS = ("aws", "azure", "gcp")
VALID_FIXTURE_COUNT = 3
INVALID_FIXTURE_COUNT = 17
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


class ContractError(ValueError):
    """Stable, bounded contract validation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> NoReturn:
    raise ContractError(code, message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def canonical_json(value: object) -> str:
    """Return the cross-service canonical JSON representation."""
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def calculate_digest(specification: dict[str, Any]) -> str:
    """Calculate the v1 digest without trusting the supplied digest field."""
    digest_input = dict(specification)
    digest_input.pop("digest", None)
    encoded = canonical_json(digest_input).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _walk_keys(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
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


def _validate_schema(
    specification: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(specification), key=lambda item: list(item.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        _fail(
            "invalid_deployment_specification",
            f"Schema validation failed at {location}: {error.message}",
        )


def _exact_python_type(value: object, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def _validate_registry(
    registry: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    Draft202012Validator.check_schema(schema)
    if registry.get("registry_version") != "resolved-deployment-dimensions.v1":
        raise RuntimeError("Registry version must be resolved-deployment-dimensions.v1")
    if (
        registry.get("specification_schema_version")
        != "resolved-deployment-specification.v1"
    ):
        raise RuntimeError("Registry and specification schema versions differ")

    slots = registry.get("slots")
    requirements = registry.get("slot_requirements")
    components = registry.get("components")
    if not isinstance(slots, dict) or tuple(slots) != (*BASELINE_SLOTS, "cross_cloud_glue"):
        raise RuntimeError("Registry slots must use canonical baseline ordering")
    if not isinstance(requirements, dict) or tuple(requirements) != BASELINE_SLOTS:
        raise RuntimeError("Slot requirements must cover every baseline slot in order")
    if not isinstance(components, dict) or not components:
        raise RuntimeError("Registry components must be a non-empty object")

    glue_policy = registry.get("cross_cloud_glue_policy")
    if not isinstance(glue_policy, dict):
        raise RuntimeError("Cross-cloud glue policy must be an object")
    component_by_provider = glue_policy.get("component_by_provider")
    boundaries = glue_policy.get("boundaries")
    if not isinstance(component_by_provider, dict) or tuple(component_by_provider) != PROVIDERS:
        raise RuntimeError("Glue policy must map every provider in canonical order")
    if not isinstance(boundaries, list) or not boundaries:
        raise RuntimeError("Glue policy must define baseline boundaries")
    boundary_ids: set[str] = set()
    for boundary in boundaries:
        if not isinstance(boundary, dict) or set(boundary) != {
            "boundary_id",
            "source_slot",
            "target_slot",
            "receiver_slot",
        }:
            raise RuntimeError("Glue boundary has an invalid shape")
        boundary_id = boundary["boundary_id"]
        source_slot = boundary["source_slot"]
        target_slot = boundary["target_slot"]
        receiver_slot = boundary["receiver_slot"]
        if not isinstance(boundary_id, str) or boundary_id in boundary_ids:
            raise RuntimeError("Glue boundary identifiers must be unique strings")
        boundary_ids.add(boundary_id)
        if source_slot not in BASELINE_SLOTS or target_slot not in BASELINE_SLOTS:
            raise RuntimeError(f"Glue boundary {boundary_id} references an unknown slot")
        if receiver_slot not in {source_slot, target_slot}:
            raise RuntimeError(f"Glue boundary {boundary_id} has an invalid receiver")

    referenced_components: set[str] = set()
    for slot_id, providers in requirements.items():
        if not isinstance(providers, dict):
            raise RuntimeError(f"{slot_id} provider requirements must be an object")
        for provider, requirement in providers.items():
            if provider not in PROVIDERS:
                raise RuntimeError(f"{slot_id} has unknown provider {provider}")
            required = requirement.get("required_components")
            optional = requirement.get("optional_components")
            if not isinstance(required, list) or not required:
                raise RuntimeError(f"{slot_id}/{provider} has no required components")
            if not isinstance(optional, list):
                raise RuntimeError(f"{slot_id}/{provider} optional components must be a list")
            component_ids = required + optional
            if len(component_ids) != len(set(component_ids)):
                raise RuntimeError(f"{slot_id}/{provider} repeats a component")
            for component_id in component_ids:
                component = components.get(component_id)
                if not isinstance(component, dict):
                    raise RuntimeError(f"Unknown required component {component_id}")
                if component.get("slot_id") != slot_id:
                    raise RuntimeError(f"{component_id} has the wrong slot")
                if component.get("provider") != provider:
                    raise RuntimeError(f"{component_id} has the wrong provider")
                if component_id in referenced_components:
                    raise RuntimeError(f"{component_id} is listed by multiple requirements")
                referenced_components.add(component_id)

    registered_dimension_ids: set[str] = set()
    targets: dict[str, tuple[str, str, str, str]] = {}
    for component_id, component in components.items():
        slot_id = component.get("slot_id")
        provider = component.get("provider")
        if slot_id not in slots or provider not in PROVIDERS:
            raise RuntimeError(f"{component_id} has an invalid slot/provider")
        if slot_id != "cross_cloud_glue" and component_id not in referenced_components:
            raise RuntimeError(f"{component_id} is absent from slot requirements")
        if slot_id == "cross_cloud_glue" and component_id in referenced_components:
            raise RuntimeError(f"{component_id} cannot be a baseline slot component")

        dimensions = component.get("dimensions")
        if not isinstance(dimensions, dict) or not dimensions:
            raise RuntimeError(f"{component_id} has no dimensions")
        for dimension_id, dimension in dimensions.items():
            registered_dimension_ids.add(dimension_id)
            classification = dimension.get("classification")
            value_type = dimension.get("value_type")
            if classification not in registry["classifications"]:
                raise RuntimeError(f"{component_id}/{dimension_id} has invalid classification")
            if value_type not in {"string", "integer", "boolean"}:
                raise RuntimeError(f"{component_id}/{dimension_id} has invalid value type")
            if dimension.get("required") is not True:
                raise RuntimeError(f"{component_id}/{dimension_id} must be required")
            target = dimension.get("terraform_target")
            if classification == "deployable_selection":
                if not isinstance(target, str) or not target:
                    raise RuntimeError(f"{component_id}/{dimension_id} needs a target")
                signature = (
                    dimension_id,
                    classification,
                    value_type,
                    canonical_json(dimension.get("allowed_values")),
                )
                previous = targets.setdefault(target, signature)
                if previous != signature:
                    raise RuntimeError(f"Terraform target {target} has conflicting definitions")
            elif target is not None:
                raise RuntimeError(f"{component_id}/{dimension_id} must not have a target")

        combination_constraints = component.get("combination_constraints", [])
        if not isinstance(combination_constraints, list):
            raise RuntimeError(
                f"{component_id} combination constraints must be a list"
            )
        for constraint in combination_constraints:
            if not isinstance(constraint, dict) or set(constraint) != {
                "selector_dimension",
                "dependent_dimension",
                "ranges_by_selector",
            }:
                raise RuntimeError(
                    f"{component_id} has an invalid combination constraint"
                )
            selector_id = constraint["selector_dimension"]
            dependent_id = constraint["dependent_dimension"]
            selector = dimensions.get(selector_id)
            dependent = dimensions.get(dependent_id)
            if not isinstance(selector, dict) or not isinstance(dependent, dict):
                raise RuntimeError(
                    f"{component_id} combination constraint references an unknown dimension"
                )
            allowed_values = selector.get("allowed_values")
            if (
                not isinstance(allowed_values, list)
                or not allowed_values
                or any(not isinstance(value, str) for value in allowed_values)
            ):
                raise RuntimeError(
                    f"{component_id}/{selector_id} must select string values"
                )
            if dependent.get("value_type") != "integer":
                raise RuntimeError(
                    f"{component_id}/{dependent_id} must be an integer dimension"
                )
            ranges = constraint["ranges_by_selector"]
            if not isinstance(ranges, dict) or set(ranges) != set(allowed_values):
                raise RuntimeError(
                    f"{component_id} combination ranges must cover every selector value"
                )
            for selector_value, limits in ranges.items():
                if not isinstance(limits, dict) or set(limits) != {
                    "minimum",
                    "maximum",
                }:
                    raise RuntimeError(
                        f"{component_id}/{selector_value} has an invalid range"
                    )
                minimum = limits["minimum"]
                maximum = limits["maximum"]
                if (
                    not _exact_python_type(minimum, "integer")
                    or not _exact_python_type(maximum, "integer")
                    or minimum > maximum
                ):
                    raise RuntimeError(
                        f"{component_id}/{selector_value} has invalid integer limits"
                    )
                if minimum < dependent.get("minimum", minimum):
                    raise RuntimeError(
                        f"{component_id}/{selector_value} is below the global minimum"
                    )
                if maximum > dependent.get("maximum", maximum):
                    raise RuntimeError(
                        f"{component_id}/{selector_value} exceeds the global maximum"
                    )

    resolutions = registry.get("dimension_resolution")
    resolution_types = registry.get("resolution_types")
    if not isinstance(resolutions, dict) or set(resolutions) != registered_dimension_ids:
        raise RuntimeError("Dimension resolution map must cover every dimension exactly")
    if not isinstance(resolution_types, list) or any(
        resolution not in resolution_types for resolution in resolutions.values()
    ):
        raise RuntimeError("Dimension resolution map contains an invalid origin")

    units = registry.get("dimension_units")
    if not isinstance(units, dict):
        raise RuntimeError("Dimension units must be an object")
    integer_ids = {
        dimension_id
        for component in components.values()
        for dimension_id, dimension in component["dimensions"].items()
        if dimension["value_type"] == "integer"
    }
    if set(units) != integer_ids or any(
        not isinstance(unit, str) or not unit for unit in units.values()
    ):
        raise RuntimeError("Every quantitative integer dimension needs one canonical unit")
    for provider, component_id in component_by_provider.items():
        component = components.get(component_id)
        if (
            not isinstance(component, dict)
            or component.get("slot_id") != "cross_cloud_glue"
            or component.get("provider") != provider
        ):
            raise RuntimeError(f"Glue component mapping is invalid for {provider}")


def _required_components(
    registry: dict[str, Any],
    slot_id: str,
    provider: str,
) -> tuple[list[str], list[str]]:
    provider_requirements = registry["slot_requirements"].get(slot_id, {}).get(provider)
    if not provider_requirements:
        _fail(
            "deployment_specification_provider_mismatch",
            f"Provider {provider} does not support slot {slot_id}",
        )
    return (
        provider_requirements["required_components"],
        provider_requirements["optional_components"],
    )


def _required_glue_components(
    registry: dict[str, Any],
    providers_by_slot: dict[str, str],
) -> list[str]:
    required_providers: set[str] = set()
    for boundary in registry["cross_cloud_glue_policy"]["boundaries"]:
        source_provider = providers_by_slot[boundary["source_slot"]]
        target_provider = providers_by_slot[boundary["target_slot"]]
        if source_provider != target_provider:
            required_providers.add(providers_by_slot[boundary["receiver_slot"]])
    component_by_provider = registry["cross_cloud_glue_policy"][
        "component_by_provider"
    ]
    return [
        component_by_provider[provider]
        for provider in PROVIDERS
        if provider in required_providers
    ]


def validate_specification(
    specification: dict[str, Any],
    registry: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """Validate one specification structurally and against the closed-world registry."""
    _walk_keys(specification)
    _validate_schema(specification, schema)
    if specification["digest"] != calculate_digest(specification):
        _fail(
            "deployment_specification_digest_mismatch",
            "Specification digest does not match canonical content",
        )

    components = specification["components"]
    component_ids = [component["component_id"] for component in components]
    if len(component_ids) != len(set(component_ids)):
        _fail(
            "unsupported_deployment_selection",
            "Component identifiers must be unique",
        )

    components_by_slot: dict[str, list[dict[str, Any]]] = {
        slot_id: [] for slot_id in (*BASELINE_SLOTS, "cross_cloud_glue")
    }
    for component in components:
        components_by_slot[component["slot_id"]].append(component)

    expected_order: list[str] = []
    providers_by_slot: dict[str, str] = {}
    for slot_id in BASELINE_SLOTS:
        slot_components = components_by_slot[slot_id]
        if not slot_components:
            _fail(
                "incomplete_deployment_specification",
                f"Slot {slot_id} has no components",
            )
        providers = {component["provider"] for component in slot_components}
        if len(providers) != 1:
            _fail(
                "deployment_specification_provider_mismatch",
                f"Slot {slot_id} contains multiple providers",
            )
        provider = next(iter(providers))
        providers_by_slot[slot_id] = provider
        required, optional = _required_components(registry, slot_id, provider)
        actual = [component["component_id"] for component in slot_components]
        missing = [component_id for component_id in required if component_id not in actual]
        unknown = [
            component_id
            for component_id in actual
            if component_id not in required and component_id not in optional
        ]
        if unknown:
            _fail(
                "unsupported_deployment_selection",
                f"Slot {slot_id} contains unsupported components",
            )
        if missing:
            _fail(
                "incomplete_deployment_specification",
                f"Slot {slot_id} is missing {','.join(missing)}",
            )
        expected_order.extend(required)
        expected_order.extend(component_id for component_id in optional if component_id in actual)

    actual_glue = [
        component["component_id"]
        for component in components_by_slot["cross_cloud_glue"]
    ]
    expected_glue = _required_glue_components(registry, providers_by_slot)
    if any(component_id not in registry["components"] for component_id in actual_glue):
        _fail(
            "unsupported_deployment_selection",
            "Cross-cloud glue contains an unknown component",
        )
    if actual_glue != expected_glue:
        _fail(
            "incomplete_deployment_specification",
            "Cross-cloud glue does not match the selected provider boundaries",
        )
    expected_order.extend(expected_glue)

    if component_ids != expected_order:
        _fail(
            "unsupported_deployment_selection",
            "Components are not in canonical registry order",
        )

    target_values: dict[str, object] = {}
    for component in components:
        component_id = component["component_id"]
        registered = registry["components"].get(component_id)
        if not registered:
            _fail(
                "unsupported_deployment_selection",
                f"Unknown component {component_id}",
            )
        if (
            component["slot_id"] != registered["slot_id"]
            or component["provider"] != registered["provider"]
            or component["service_id"] != registered["service_id"]
        ):
            _fail(
                "deployment_specification_provider_mismatch",
                f"Component {component_id} does not match its registry tuple",
            )

        dimensions = component["dimensions"]
        dimension_ids = [dimension["dimension_id"] for dimension in dimensions]
        if len(dimension_ids) != len(set(dimension_ids)):
            _fail(
                "unsupported_deployment_selection",
                f"Component {component_id} repeats a dimension",
            )
        expected_dimensions = list(registered["dimensions"])
        if dimension_ids != expected_dimensions:
            _fail(
                "incomplete_deployment_specification",
                f"Component {component_id} dimensions differ from the registry",
            )

        dimension_values: dict[str, object] = {}
        for dimension in dimensions:
            dimension_id = dimension["dimension_id"]
            definition = registered["dimensions"][dimension_id]
            if dimension["classification"] != definition["classification"]:
                _fail(
                    "unsupported_deployment_selection",
                    f"Dimension {dimension_id} has the wrong classification",
                )
            value = dimension["value"]
            dimension_values[dimension_id] = value
            if not _exact_python_type(value, definition["value_type"]):
                _fail(
                    "unsupported_deployment_selection",
                    f"Dimension {dimension_id} has the wrong value type",
                )
            if "allowed_values" in definition and value not in definition["allowed_values"]:
                _fail(
                    "unsupported_deployment_selection",
                    f"Dimension {dimension_id} has an unsupported value",
                )
            if "minimum" in definition and value < definition["minimum"]:
                _fail(
                    "unsupported_deployment_selection",
                    f"Dimension {dimension_id} is below its minimum",
                )
            if "maximum" in definition and value > definition["maximum"]:
                _fail(
                    "unsupported_deployment_selection",
                    f"Dimension {dimension_id} is above its maximum",
                )

            expected_unit = registry["dimension_units"].get(dimension_id)
            if dimension.get("unit") != expected_unit:
                _fail(
                    "unsupported_deployment_selection",
                    f"Dimension {dimension_id} has the wrong unit",
                )
            target = definition.get("terraform_target")
            if dimension.get("terraform_target") != target:
                _fail(
                    "unsupported_deployment_selection",
                    f"Dimension {dimension_id} has the wrong Terraform target",
                )

            context = specification["optimization_context"]
            expected_formula_reference = f"formula_set:{context['formula_set_id']}"
            if dimension["formula_reference"] != expected_formula_reference:
                _fail(
                    "unsupported_deployment_selection",
                    f"Dimension {dimension_id} has an unbound formula reference",
                )
            resolution = registry["dimension_resolution"][dimension_id]
            if definition["classification"] == "account_scope":
                expected_evidence_reference = (
                    f"provider_context:{component['provider']}"
                )
            elif resolution == "baseline_invariant":
                expected_evidence_reference = (
                    f"deployment_registry:{registry['registry_version']}"
                )
            elif resolution == "formula_input":
                expected_evidence_reference = (
                    f"workload_contract:{context['workload_contract_id']}"
                )
            else:
                expected_evidence_reference = (
                    "catalog:"
                    f"{context['catalog_references'][component['provider']]['snapshot_id']}"
                )
            if dimension["evidence_reference"] != expected_evidence_reference:
                _fail(
                    "unsupported_deployment_selection",
                    f"Dimension {dimension_id} has an unbound evidence reference",
                )
            if target:
                previous = target_values.setdefault(target, value)
                if previous != value:
                    _fail(
                        "unsupported_deployment_selection",
                        f"Terraform target {target} has contradictory values",
                    )

        for constraint in registered.get("combination_constraints", []):
            selector_id = constraint["selector_dimension"]
            dependent_id = constraint["dependent_dimension"]
            selector_value = dimension_values[selector_id]
            dependent_value = dimension_values[dependent_id]
            limits = constraint["ranges_by_selector"][selector_value]
            if not limits["minimum"] <= dependent_value <= limits["maximum"]:
                _fail(
                    "unsupported_deployment_selection",
                    (
                        f"Dimension {dependent_id} is invalid for "
                        f"{selector_id}={selector_value}"
                    ),
                )


def _default_value(definition: dict[str, Any]) -> object:
    if "allowed_values" in definition:
        return definition["allowed_values"][0]
    return definition.get("minimum", 1)


def _build_component(
    component_id: str,
    registry: dict[str, Any],
    optimization_context: dict[str, Any],
) -> dict[str, Any]:
    registered = registry["components"][component_id]
    dimensions = []
    for dimension_id, definition in registered["dimensions"].items():
        resolution = registry["dimension_resolution"][dimension_id]
        if definition["classification"] == "account_scope":
            evidence_reference = f"provider_context:{registered['provider']}"
        elif resolution == "baseline_invariant":
            evidence_reference = f"deployment_registry:{registry['registry_version']}"
        elif resolution == "formula_input":
            evidence_reference = (
                f"workload_contract:{optimization_context['workload_contract_id']}"
            )
        else:
            evidence_reference = (
                "catalog:"
                f"{optimization_context['catalog_references'][registered['provider']]['snapshot_id']}"
            )
        dimension: dict[str, Any] = {
            "dimension_id": dimension_id,
            "classification": definition["classification"],
            "value": _default_value(definition),
            "formula_reference": (
                f"formula_set:{optimization_context['formula_set_id']}"
            ),
            "evidence_reference": evidence_reference,
        }
        unit = registry["dimension_units"].get(dimension_id)
        if unit:
            dimension["unit"] = unit
        if definition.get("terraform_target"):
            dimension["terraform_target"] = definition["terraform_target"]
        dimensions.append(dimension)
    return {
        "component_id": component_id,
        "slot_id": registered["slot_id"],
        "provider": registered["provider"],
        "service_id": registered["service_id"],
        "required": True,
        "dimensions": dimensions,
    }


def _build_specification(
    registry: dict[str, Any],
    providers_by_slot: dict[str, str],
) -> dict[str, Any]:
    component_ids: list[str] = []
    for slot_id in BASELINE_SLOTS:
        provider = providers_by_slot[slot_id]
        required, _ = _required_components(registry, slot_id, provider)
        component_ids.extend(required)
    component_ids.extend(_required_glue_components(registry, providers_by_slot))
    optimization_context = {
        "optimization_profile_id": "cost_minimization_v1",
        "optimization_profile_version": "2026.06.08",
        "calculation_strategy_id": "cost_calculation_v2",
        "formula_set_id": "cost_formula_set_v1",
        "workload_contract_id": "digital_twin_workload_v1",
        "pricing_registry_version": "2026.07.17",
        "catalog_references": {
            "aws": {
                "snapshot_id": f"pcs_{'a' * 64}",
                "pricing_region": "eu-central-1",
                "content_digest": f"sha256:{'1' * 64}",
            },
            "azure": {
                "snapshot_id": f"pcs_{'b' * 64}",
                "pricing_region": "westeurope",
                "content_digest": f"sha256:{'2' * 64}",
            },
            "gcp": {
                "snapshot_id": f"pcs_{'c' * 64}",
                "pricing_region": "europe-west1",
                "content_digest": f"sha256:{'3' * 64}",
            },
        },
    }
    specification: dict[str, Any] = {
        "schema_version": "resolved-deployment-specification.v1",
        "calculation_run_id": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        "architecture_profile": {
            "profile_id": "five-layer-baseline",
            "profile_version": "1",
        },
        "optimization_context": optimization_context,
        "currency": "USD",
        "components": [
            _build_component(component_id, registry, optimization_context)
            for component_id in component_ids
        ],
        "digest": "",
    }
    specification["digest"] = calculate_digest(specification)
    return specification


def _redigest(specification: dict[str, Any]) -> dict[str, Any]:
    specification["digest"] = calculate_digest(specification)
    return specification


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def generate_fixtures(registry: dict[str, Any]) -> None:
    """Generate deterministic reference fixtures from reviewed scenario choices."""
    all_aws = _build_specification(
        registry,
        {slot_id: "aws" for slot_id in BASELINE_SLOTS},
    )
    all_azure = _build_specification(
        registry,
        {slot_id: "azure" for slot_id in BASELINE_SLOTS},
    )
    mixed = _build_specification(
        registry,
        {
            "l1_ingestion": "gcp",
            "l2_processing": "azure",
            "l3_hot_storage": "gcp",
            "l3_cool_storage": "aws",
            "l3_archive_storage": "gcp",
            "l4_twin_state": "azure",
            "l5_visualization": "aws",
        },
    )
    valid_root = SOURCE_V1 / "fixtures" / "valid"
    invalid_root = SOURCE_V1 / "fixtures" / "invalid"
    for fixture_root in (valid_root, invalid_root):
        if fixture_root.exists():
            shutil.rmtree(fixture_root)
    _write_json(valid_root / "all-aws.json", all_aws)
    _write_json(valid_root / "all-azure.json", all_azure)
    _write_json(valid_root / "mixed-providers.json", mixed)

    invalid: dict[str, tuple[str, dict[str, Any]]] = {}

    secret_field = copy.deepcopy(all_aws)
    secret_field["client_secret"] = None
    invalid["secret-like-field"] = (
        "invalid_deployment_specification",
        _redigest(secret_field),
    )

    unknown_field = copy.deepcopy(all_aws)
    unknown_field["debug"] = True
    invalid["unknown-field"] = (
        "invalid_deployment_specification",
        _redigest(unknown_field),
    )

    unknown_component = copy.deepcopy(all_aws)
    unknown_component["components"][0]["component_id"] = "l1.aws.unknown"
    invalid["unknown-component"] = (
        "unsupported_deployment_selection",
        _redigest(unknown_component),
    )

    wrong_classification = copy.deepcopy(all_aws)
    dimension = wrong_classification["components"][1]["dimensions"][0]
    dimension["classification"] = "usage_tier"
    dimension.pop("terraform_target")
    invalid["wrong-classification"] = (
        "unsupported_deployment_selection",
        _redigest(wrong_classification),
    )

    unbound_formula = copy.deepcopy(all_aws)
    unbound_formula["components"][0]["dimensions"][0][
        "formula_reference"
    ] = "formula_set:unknown"
    invalid["unbound-formula-reference"] = (
        "unsupported_deployment_selection",
        _redigest(unbound_formula),
    )

    unbound_evidence = copy.deepcopy(all_aws)
    unbound_evidence["components"][0]["dimensions"][0][
        "evidence_reference"
    ] = "catalog:unknown"
    invalid["unbound-evidence-reference"] = (
        "unsupported_deployment_selection",
        _redigest(unbound_evidence),
    )

    invalid_value = copy.deepcopy(all_azure)
    invalid_value["components"][0]["dimensions"][0]["value"] = "X9"
    invalid["unknown-value"] = (
        "unsupported_deployment_selection",
        _redigest(invalid_value),
    )

    invalid_iot_hub_free_capacity = copy.deepcopy(all_azure)
    iot_hub = next(
        component
        for component in invalid_iot_hub_free_capacity["components"]
        if component["component_id"] == "l1.azure.iot_hub"
    )
    iot_dimensions = {
        dimension["dimension_id"]: dimension for dimension in iot_hub["dimensions"]
    }
    iot_dimensions["azure.iot_hub.capacity"]["value"] = 2
    invalid["iot-hub-f1-capacity"] = (
        "unsupported_deployment_selection",
        _redigest(invalid_iot_hub_free_capacity),
    )

    invalid_iot_hub_s3_capacity = copy.deepcopy(all_azure)
    iot_hub = next(
        component
        for component in invalid_iot_hub_s3_capacity["components"]
        if component["component_id"] == "l1.azure.iot_hub"
    )
    iot_dimensions = {
        dimension["dimension_id"]: dimension for dimension in iot_hub["dimensions"]
    }
    iot_dimensions["azure.iot_hub.sku"]["value"] = "S3"
    iot_dimensions["azure.iot_hub.capacity"]["value"] = 11
    invalid["iot-hub-s3-capacity"] = (
        "unsupported_deployment_selection",
        _redigest(invalid_iot_hub_s3_capacity),
    )

    duplicate_component = copy.deepcopy(all_aws)
    duplicate_component["components"].insert(
        1,
        copy.deepcopy(duplicate_component["components"][0]),
    )
    invalid["duplicate-component"] = (
        "unsupported_deployment_selection",
        _redigest(duplicate_component),
    )

    missing_component = copy.deepcopy(all_aws)
    del missing_component["components"][0]
    invalid["missing-required-component"] = (
        "incomplete_deployment_specification",
        _redigest(missing_component),
    )

    missing_glue = copy.deepcopy(mixed)
    missing_glue["components"] = [
        component
        for component in missing_glue["components"]
        if component["component_id"] != "glue.aws.lambda"
    ]
    invalid["missing-cross-cloud-glue"] = (
        "incomplete_deployment_specification",
        _redigest(missing_glue),
    )

    unnecessary_glue = copy.deepcopy(all_aws)
    unnecessary_glue["components"].append(
        _build_component(
            "glue.aws.lambda",
            registry,
            unnecessary_glue["optimization_context"],
        )
    )
    invalid["unnecessary-cross-cloud-glue"] = (
        "incomplete_deployment_specification",
        _redigest(unnecessary_glue),
    )

    unsupported_gcp = copy.deepcopy(all_aws)
    l4_component = next(
        component
        for component in unsupported_gcp["components"]
        if component["slot_id"] == "l4_twin_state"
    )
    l4_component["provider"] = "gcp"
    invalid["unsupported-gcp-l4"] = (
        "deployment_specification_provider_mismatch",
        _redigest(unsupported_gcp),
    )

    provider_mismatch = copy.deepcopy(mixed)
    provider_mismatch["components"][0]["provider"] = "aws"
    invalid["provider-slot-mismatch"] = (
        "deployment_specification_provider_mismatch",
        _redigest(provider_mismatch),
    )

    duplicate_dimension = copy.deepcopy(all_aws)
    duplicate_dimension["components"][1]["dimensions"].append(
        copy.deepcopy(duplicate_dimension["components"][1]["dimensions"][0])
    )
    invalid["duplicate-dimension"] = (
        "unsupported_deployment_selection",
        _redigest(duplicate_dimension),
    )

    digest_tamper = copy.deepcopy(all_aws)
    digest_tamper["currency"] = "EUR"
    invalid["digest-tamper"] = (
        "deployment_specification_digest_mismatch",
        digest_tamper,
    )

    for name, (expected_error, specification) in invalid.items():
        _write_json(
            invalid_root / f"{name}.json",
            {
                "expected_error": expected_error,
                "specification": specification,
            },
        )


def _source_files() -> list[Path]:
    return sorted(
        path
        for path in SOURCE_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


def _contract_tree_digest() -> str:
    digest = hashlib.sha256()
    for path in _source_files():
        relative = path.relative_to(SOURCE_ROOT).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def validate_source() -> tuple[dict[str, Any], dict[str, Any]]:
    schema = _read_json(SOURCE_V1 / "schema.json")
    registry = _read_json(SOURCE_V1 / "deployment-dimensions.json")
    _validate_registry(registry, schema)

    valid_paths = sorted((SOURCE_V1 / "fixtures" / "valid").glob("*.json"))
    invalid_paths = sorted((SOURCE_V1 / "fixtures" / "invalid").glob("*.json"))
    if (
        len(valid_paths) != VALID_FIXTURE_COUNT
        or len(invalid_paths) != INVALID_FIXTURE_COUNT
    ):
        raise RuntimeError("Canonical positive and negative fixture matrix is incomplete")

    for path in valid_paths:
        validate_specification(_read_json(path), registry, schema)

    for path in invalid_paths:
        wrapper = _read_json(path)
        expected_error = wrapper.get("expected_error")
        specification = wrapper.get("specification")
        if not isinstance(expected_error, str) or not isinstance(specification, dict):
            raise RuntimeError(f"{path} has an invalid negative-fixture wrapper")
        try:
            validate_specification(specification, registry, schema)
        except ContractError as exc:
            if exc.code != expected_error:
                raise RuntimeError(
                    f"{path} expected {expected_error}, got {exc.code}: {exc}"
                ) from exc
        else:
            raise RuntimeError(f"{path} unexpectedly passed validation")
    return registry, schema


def synchronize() -> None:
    tree_digest = _contract_tree_digest()
    for generated_root in GENERATED_ROOTS:
        target = generated_root / CONTRACT_NAME
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(SOURCE_ROOT, target)
        (target / ".contract-sha256").write_text(tree_digest + "\n", encoding="utf-8")


def check_synchronized() -> None:
    expected_files = {
        path.relative_to(SOURCE_ROOT): path.read_bytes() for path in _source_files()
    }
    tree_digest = _contract_tree_digest()
    for generated_root in GENERATED_ROOTS:
        target = generated_root / CONTRACT_NAME
        if not target.is_dir():
            raise RuntimeError(f"Missing generated contract copy: {target}")
        actual_files = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file() and path.name != ".contract-sha256"
        }
        if actual_files != expected_files:
            raise RuntimeError(f"Generated contract copy is stale: {target}")
        marker = target / ".contract-sha256"
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != tree_digest:
            raise RuntimeError(f"Generated contract digest is stale: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate-fixtures",
        action="store_true",
        help="Regenerate the reviewed canonical fixture matrix.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Validate the source and refresh all generated service copies.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate source fixtures and require byte-identical generated copies.",
    )
    args = parser.parse_args()
    if not (args.generate_fixtures or args.sync or args.check):
        parser.error("at least one action is required")

    try:
        schema = _read_json(SOURCE_V1 / "schema.json")
        registry = _read_json(SOURCE_V1 / "deployment-dimensions.json")
        _validate_registry(registry, schema)
        if args.generate_fixtures:
            generate_fixtures(registry)
        validate_source()
        if args.sync:
            synchronize()
        if args.check:
            check_synchronized()
    except (ContractError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Resolved deployment contract is valid and synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
