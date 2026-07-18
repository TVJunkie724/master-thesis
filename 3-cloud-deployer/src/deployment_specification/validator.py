"""Strict validation for manifest-bound deployment specifications."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker

from .contract import (
    MANIFEST_VERSION,
    PROVIDERS,
    SCHEMA_VERSION,
    SLOT_ORDER,
    load_contract,
)
from .errors import DeploymentSpecificationError
from .models import (
    ValidatedDeploymentManifest,
    ValidatedResolvedDeploymentSpecification,
)


MAX_CANONICAL_BYTES = 256 * 1024
MAX_RECURSION_DEPTH = 16
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
PROVIDER_ALIASES = {"google": "gcp"}


def _fail(code: str, field: str, message: str) -> NoReturn:
    raise DeploymentSpecificationError(code, field, message)


def canonical_json(value: object) -> str:
    """Return the cross-service canonical JSON representation."""

    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            "resolved_deployment_specification",
            "Resolved deployment specification is not canonical JSON",
        )
        raise AssertionError from exc


def calculate_digest(specification: Mapping[str, Any]) -> str:
    """Calculate a specification digest without trusting its digest field."""

    payload = dict(specification)
    payload.pop("digest", None)
    encoded = canonical_json(payload).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate_deployment_manifest(
    raw_manifest: object,
    provider_config: Mapping[str, Any],
) -> ValidatedDeploymentManifest:
    """Validate Manifest v2 and bind it to the selected provider path."""

    if not isinstance(raw_manifest, Mapping):
        _fail(
            "DEPLOYMENT_MANIFEST_REQUIRED",
            "deployment_manifest",
            "DeploymentManifest v2 is required for deployment operations",
        )
    if raw_manifest.get("manifest_version") != MANIFEST_VERSION:
        _fail(
            "DEPLOYMENT_MANIFEST_VERSION_UNSUPPORTED",
            "deployment_manifest.manifest_version",
            "DeploymentManifest version is unsupported",
        )

    specification = validate_resolved_deployment_specification(
        raw_manifest.get("resolved_deployment_specification")
    )
    if raw_manifest.get("calculation_run_id") != specification.specification.get(
        "calculation_run_id"
    ):
        _fail(
            "DEPLOYMENT_SPECIFICATION_RUN_MISMATCH",
            "deployment_manifest.calculation_run_id",
            "Deployment manifest and specification reference different runs",
        )
    manifest_digest = raw_manifest.get("resolved_deployment_specification_digest")
    if not isinstance(manifest_digest, str) or not hmac.compare_digest(
        manifest_digest, specification.digest
    ):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH",
            "deployment_manifest.resolved_deployment_specification_digest",
            "Deployment manifest and specification digests differ",
        )

    _, registry = load_contract()
    provider_by_slot: dict[str, str] = {}
    manifest_providers = raw_manifest.get("providers")
    if not isinstance(manifest_providers, Mapping):
        _fail(
            "DEPLOYMENT_SPECIFICATION_PROVIDER_MISMATCH",
            "deployment_manifest.providers",
            "Deployment manifest provider path is missing",
        )

    for slot_id in SLOT_ORDER:
        deployer_key = registry["slots"][slot_id]["deployer_key"]
        configured = _normalize_provider(provider_config.get(deployer_key), deployer_key)
        manifested = _normalize_provider(
            manifest_providers.get(deployer_key),
            f"deployment_manifest.providers.{deployer_key}",
        )
        if configured != manifested:
            _fail(
                "DEPLOYMENT_SPECIFICATION_PROVIDER_MISMATCH",
                f"deployment_manifest.providers.{deployer_key}",
                "Deployment manifest provider differs from project configuration",
            )
        provider_by_slot[slot_id] = configured

    _validate_components(
        list(specification.specification["components"]),
        provider_by_slot=provider_by_slot,
        registry=registry,
        optimization_context=specification.specification["optimization_context"],
    )
    return ValidatedDeploymentManifest(
        manifest=MappingProxyType(dict(raw_manifest)),
        specification=specification,
        provider_by_slot=MappingProxyType(provider_by_slot),
    )


def validate_resolved_deployment_specification(
    raw_specification: object,
) -> ValidatedResolvedDeploymentSpecification:
    """Validate and canonicalize an untrusted v1 specification."""

    if not isinstance(raw_specification, Mapping):
        _fail(
            "DEPLOYMENT_SPECIFICATION_MISSING",
            "resolved_deployment_specification",
            "Resolved deployment specification is missing",
        )
    _scan_payload(raw_specification)
    serialized = canonical_json(raw_specification)
    if len(serialized.encode("utf-8")) > MAX_CANONICAL_BYTES:
        _fail(
            "DEPLOYMENT_SPECIFICATION_TOO_LARGE",
            "resolved_deployment_specification",
            "Resolved deployment specification exceeds the size limit",
        )

    specification = json.loads(serialized)
    schema, registry = load_contract()
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(specification),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].absolute_path)
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            f"resolved_deployment_specification.{location}".rstrip("."),
            "Resolved deployment specification does not match schema v1",
        )
    if specification["currency"] != "USD":
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            "resolved_deployment_specification.currency",
            "Deployment selections must use canonical USD state",
        )

    expected_digest = calculate_digest(specification)
    if not hmac.compare_digest(specification["digest"], expected_digest):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH",
            "resolved_deployment_specification.digest",
            "Resolved deployment specification digest does not match its content",
        )

    _validate_registered_components(
        specification["components"],
        registry=registry,
        optimization_context=specification["optimization_context"],
    )
    return ValidatedResolvedDeploymentSpecification(
        specification=MappingProxyType(specification),
        canonical_json=serialized,
        digest=expected_digest,
        schema_version=SCHEMA_VERSION,
    )


def _scan_payload(value: object, *, path: str = "$", depth: int = 0) -> None:
    if depth > MAX_RECURSION_DEPTH:
        _fail(
            "DEPLOYMENT_SPECIFICATION_TOO_DEEP",
            "resolved_deployment_specification",
            "Resolved deployment specification exceeds the nesting limit",
        )
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in SECRET_KEY_FRAGMENTS):
                _fail(
                    "DEPLOYMENT_SPECIFICATION_SECRET_FIELD",
                    path,
                    "Secret-like fields are forbidden in deployment specifications",
                )
            _scan_payload(nested, path=f"{path}.{key}", depth=depth + 1)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_payload(nested, path=f"{path}[{index}]", depth=depth + 1)


def _normalize_provider(value: object, field: str) -> str:
    if not isinstance(value, str):
        _fail(
            "DEPLOYMENT_SPECIFICATION_PROVIDER_MISMATCH",
            field,
            "Deployment provider path is incomplete",
        )
    normalized = PROVIDER_ALIASES.get(value.strip().lower(), value.strip().lower())
    if normalized not in PROVIDERS:
        _fail(
            "DEPLOYMENT_SPECIFICATION_PROVIDER_MISMATCH",
            field,
            "Deployment provider path contains an unsupported provider",
        )
    return normalized


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


def _validate_components(
    components: list[dict[str, Any]],
    *,
    provider_by_slot: Mapping[str, str],
    registry: Mapping[str, Any],
    optimization_context: Mapping[str, Any],
) -> None:
    components_by_slot: dict[str, list[dict[str, Any]]] = {
        slot_id: [] for slot_id in (*SLOT_ORDER, "cross_cloud_glue")
    }
    for component in components:
        components_by_slot[component["slot_id"]].append(component)

    expected_component_ids: list[str] = []
    for slot_id in SLOT_ORDER:
        provider = provider_by_slot[slot_id]
        requirement = registry["slot_requirements"].get(slot_id, {}).get(provider)
        if not isinstance(requirement, Mapping):
            _fail(
                "DEPLOYMENT_SPECIFICATION_PROVIDER_MISMATCH",
                f"resolved_deployment_specification.components.{slot_id}",
                "Selected provider does not implement the required slot",
            )
        actual_ids = [
            component["component_id"] for component in components_by_slot[slot_id]
        ]
        required = list(requirement["required_components"])
        optional = list(requirement["optional_components"])
        expected_for_slot = [
            *required,
            *(component_id for component_id in optional if component_id in actual_ids),
        ]
        if actual_ids != expected_for_slot:
            _fail(
                "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
                f"resolved_deployment_specification.components.{slot_id}",
                "Deployment components do not match the selected provider slot",
            )
        expected_component_ids.extend(expected_for_slot)

    component_by_provider = registry["cross_cloud_glue_policy"][
        "component_by_provider"
    ]
    expected_glue_ids = [
        component_by_provider[provider]
        for provider in _required_glue_providers(registry, provider_by_slot)
    ]
    actual_glue_ids = [
        component["component_id"]
        for component in components_by_slot["cross_cloud_glue"]
    ]
    if actual_glue_ids != expected_glue_ids:
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolved_deployment_specification.components.cross_cloud_glue",
            "Cross-cloud receiver components do not match the selected path",
        )
    expected_component_ids.extend(expected_glue_ids)
    if [component["component_id"] for component in components] != expected_component_ids:
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolved_deployment_specification.components",
            "Deployment component ordering or cardinality is invalid",
        )

    _validate_registered_components(
        components,
        registry=registry,
        optimization_context=optimization_context,
    )


def _validate_registered_components(
    components: list[dict[str, Any]],
    *,
    registry: Mapping[str, Any],
    optimization_context: Mapping[str, Any],
) -> None:
    targets: dict[str, object] = {}
    seen_components: set[str] = set()
    for component in components:
        component_id = component["component_id"]
        if component_id in seen_components:
            _fail(
                "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
                "resolved_deployment_specification.components",
                "Deployment specification repeats a component",
            )
        seen_components.add(component_id)
        _validate_component(
            component,
            registry=registry,
            optimization_context=optimization_context,
            terraform_targets=targets,
        )


def _validate_component(
    component: Mapping[str, Any],
    *,
    registry: Mapping[str, Any],
    optimization_context: Mapping[str, Any],
    terraform_targets: dict[str, object],
) -> None:
    component_id = component["component_id"]
    registered = registry["components"].get(component_id)
    if not isinstance(registered, Mapping):
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolved_deployment_specification.components",
            "Deployment specification contains an unknown component",
        )
    for field in ("slot_id", "provider", "service_id"):
        if component[field] != registered[field]:
            _fail(
                "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
                f"resolved_deployment_specification.components.{component_id}.{field}",
                "Deployment component metadata differs from the registry",
            )

    definitions = registered["dimensions"]
    dimensions = component["dimensions"]
    if [dimension["dimension_id"] for dimension in dimensions] != list(definitions):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            f"resolved_deployment_specification.components.{component_id}.dimensions",
            "Deployment dimensions differ from the registry",
        )

    values: dict[str, object] = {}
    for dimension in dimensions:
        dimension_id = dimension["dimension_id"]
        definition = definitions[dimension_id]
        _validate_dimension_value(
            component_id,
            dimension_id,
            dimension["value"],
            definition,
        )
        expected_optional = {
            "unit": registry["dimension_units"].get(dimension_id),
            "terraform_target": definition.get("terraform_target"),
        }
        if dimension["classification"] != definition["classification"]:
            _fail(
                "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                f"resolved_deployment_specification.components.{component_id}.{dimension_id}",
                "Deployment dimension classification differs from the registry",
            )
        for field, expected in expected_optional.items():
            if dimension.get(field) != expected:
                _fail(
                    "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                    (
                        "resolved_deployment_specification.components."
                        f"{component_id}.{dimension_id}.{field}"
                    ),
                    "Deployment dimension metadata differs from the registry",
                )

        expected_formula = f"formula_set:{optimization_context['formula_set_id']}"
        if dimension["formula_reference"] != expected_formula:
            _fail(
                "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
                f"resolved_deployment_specification.components.{component_id}.{dimension_id}",
                "Deployment dimension formula reference is not bound to the run",
            )
        if dimension["evidence_reference"] != _expected_evidence_reference(
            registered["provider"],
            dimension_id,
            definition["classification"],
            registry=registry,
            optimization_context=optimization_context,
        ):
            _fail(
                "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
                f"resolved_deployment_specification.components.{component_id}.{dimension_id}",
                "Deployment dimension evidence reference is not bound to the run",
            )

        target = definition.get("terraform_target")
        if target is not None:
            previous = terraform_targets.setdefault(target, dimension["value"])
            if previous != dimension["value"]:
                _fail(
                    "DEPLOYMENT_SPECIFICATION_TARGET_CONFLICT",
                    f"resolved_deployment_specification.components.{component_id}.{dimension_id}",
                    "Deployment dimensions contain contradictory Terraform targets",
                )
        values[dimension_id] = dimension["value"]

    for constraint in registered.get("combination_constraints", []):
        selector = values[constraint["selector_dimension"]]
        dependent = values[constraint["dependent_dimension"]]
        limits = constraint["ranges_by_selector"][selector]
        if not limits["minimum"] <= dependent <= limits["maximum"]:
            _fail(
                "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                f"resolved_deployment_specification.components.{component_id}",
                "Deployment dimension combination is unsupported",
            )


def _validate_dimension_value(
    component_id: str,
    dimension_id: str,
    value: object,
    definition: Mapping[str, Any],
) -> None:
    expected_type = definition["value_type"]
    valid_type = (
        isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "integer"
        else isinstance(value, bool)
        if expected_type == "boolean"
        else isinstance(value, str)
    )
    field = f"resolved_deployment_specification.components.{component_id}.{dimension_id}"
    if not valid_type:
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            field,
            "Deployment dimension has the wrong value type",
        )
    if "allowed_values" in definition and value not in definition["allowed_values"]:
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            field,
            "Deployment dimension value is unsupported",
        )
    if "minimum" in definition and value < definition["minimum"]:
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            field,
            "Deployment dimension value is below its minimum",
        )
    if "maximum" in definition and value > definition["maximum"]:
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            field,
            "Deployment dimension value exceeds its maximum",
        )


def _expected_evidence_reference(
    provider: str,
    dimension_id: str,
    classification: str,
    *,
    registry: Mapping[str, Any],
    optimization_context: Mapping[str, Any],
) -> str:
    resolution = registry["dimension_resolution"][dimension_id]
    if classification == "account_scope":
        return f"provider_context:{provider}"
    if resolution == "baseline_invariant":
        return f"deployment_registry:{registry['registry_version']}"
    if resolution == "formula_input":
        return f"workload_contract:{optimization_context['workload_contract_id']}"
    snapshot_id = optimization_context["catalog_references"][provider]["snapshot_id"]
    return f"catalog:{snapshot_id}"
