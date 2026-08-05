"""Validation and canonicalization for resolved deployment specifications."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker

from src.schemas.pricing_catalog import PricingCatalogContext


SCHEMA_VERSION = "resolved-deployment-specification.v1"
V2_SCHEMA_VERSION = "resolved-deployment-specification.v2"
REGISTRY_VERSION = "resolved-deployment-dimensions.v1"
READY = "ready"
LEGACY_NOT_DEPLOYABLE = "legacy_not_deployable"
MAX_CANONICAL_BYTES = 256 * 1024
MAX_RECURSION_DEPTH = 16
PROVIDERS = ("aws", "azure", "gcp")
SLOT_ORDER = (
    "l1_ingestion",
    "l2_processing",
    "l3_hot_storage",
    "l3_cool_storage",
    "l3_archive_storage",
    "l4_twin_state",
    "l5_visualization",
)
PATH_KEY_BY_SLOT = {
    "l1_ingestion": "l1",
    "l2_processing": "l2",
    "l3_hot_storage": "l3_hot",
    "l3_cool_storage": "l3_cool",
    "l3_archive_storage": "l3_archive",
    "l4_twin_state": "l4",
    "l5_visualization": "l5",
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
V2_CONTRACT_ROOT = CONTRACT_ROOT.parent / "v2"
ARCHITECTURE_DEFINITIONS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
    / "definitions"
)
FIVE_LAYER_V2_WORKLOAD_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "five-layer-workload"
    / "v2"
)
V2_LOGICAL_TO_PATH = {
    "component.ingestion": "l1",
    "component.processing": "l2",
    "component.hot-storage": "l3_hot",
    "component.cool-storage": "l3_cool",
    "component.archive-storage": "l3_archive",
    "component.twin-state": "l4",
    "component.visualization": "l5",
}


@dataclass(frozen=True, slots=True)
class ValidatedResolvedDeploymentSpecification:
    specification: dict[str, Any]
    canonical_json: str
    digest: str
    schema_version: str


class ResolvedDeploymentSpecificationError(ValueError):
    """Stable, bounded validation error without provider payload values."""

    def __init__(self, code: str, field: str, message: str) -> None:
        self.code = code
        self.field = field
        super().__init__(message)


def _fail(code: str, field: str, message: str) -> NoReturn:
    raise ResolvedDeploymentSpecificationError(code, field, message)


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


@lru_cache(maxsize=1)
def _v2_contract() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        schema = json.loads((V2_CONTRACT_ROOT / "schema.json").read_text("utf-8"))
        registry = json.loads(
            (V2_CONTRACT_ROOT / "component-capacity-registry.json").read_text(
                "utf-8"
            )
        )
        profile = json.loads(
            (
                ARCHITECTURE_DEFINITIONS_ROOT
                / "profiles"
                / "five-layer-baseline"
                / "2"
                / "profile.json"
            ).read_text("utf-8")
        )
        catalog = json.loads(
            (
                ARCHITECTURE_DEFINITIONS_ROOT
                / "component-catalogs"
                / "complete-service"
                / "1"
                / "catalog.json"
            ).read_text("utf-8")
        )
        eventing = json.loads(
            (FIVE_LAYER_V2_WORKLOAD_ROOT / "eventing-scenario-catalog.json").read_text(
                "utf-8"
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Resolved deployment v2 contract is unavailable") from exc
    Draft202012Validator.check_schema(schema)
    supplied = registry.get("content_digest")
    registry_without_digest = dict(registry)
    registry_without_digest["content_digest"] = ""
    actual = "sha256:" + hashlib.sha256(
        canonical_json(registry_without_digest).encode("utf-8")
    ).hexdigest()
    if supplied != actual:
        raise RuntimeError("Resolved deployment v2 registry digest drifted")
    return schema, registry, {
        "profile": profile,
        "catalog": catalog,
        "eventing": eventing,
    }


def canonical_json(value: object) -> str:
    """Return the repository-wide canonical JSON representation."""

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
            "resolvedDeploymentSpecification",
            "Resolved deployment specification is not canonical JSON",
        )
        raise AssertionError from exc


def calculate_digest(specification: Mapping[str, Any]) -> str:
    payload = dict(specification)
    payload.pop("digest", None)
    encoded = canonical_json(payload).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate_resolved_deployment_specification(
    raw_specification: object,
    *,
    expected_run_id: str,
    expected_cheapest_path: Mapping[str, Any],
    expected_catalog_context: PricingCatalogContext,
    expected_result: Mapping[str, Any],
) -> ValidatedResolvedDeploymentSpecification:
    """Validate, bind, and canonicalize an untrusted Optimizer specification."""

    if not isinstance(raw_specification, Mapping):
        _fail(
            "DEPLOYMENT_SPECIFICATION_MISSING",
            "resolvedDeploymentSpecification",
            "Resolved deployment specification is missing",
        )
    if raw_specification.get("schema_version") == V2_SCHEMA_VERSION:
        return _validate_v2_specification(
            raw_specification,
            expected_run_id=expected_run_id,
            expected_cheapest_path=expected_cheapest_path,
            expected_catalog_context=expected_catalog_context,
            expected_result=expected_result,
        )
    _scan_payload(raw_specification)
    serialized = canonical_json(raw_specification)
    if len(serialized.encode("utf-8")) > MAX_CANONICAL_BYTES:
        _fail(
            "DEPLOYMENT_SPECIFICATION_TOO_LARGE",
            "resolvedDeploymentSpecification",
            "Resolved deployment specification exceeds the size limit",
        )
    specification = json.loads(serialized)
    schema, registry = _contract()
    schema_errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(specification),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if schema_errors:
        error = schema_errors[0]
        location = ".".join(str(part) for part in error.absolute_path)
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            f"resolvedDeploymentSpecification.{location}".rstrip("."),
            "Resolved deployment specification does not match schema v1",
        )

    if specification["calculation_run_id"] != expected_run_id:
        _fail(
            "DEPLOYMENT_SPECIFICATION_RUN_MISMATCH",
            "resolvedDeploymentSpecification.calculation_run_id",
            "Resolved deployment specification belongs to a different run",
        )
    if specification["currency"] != "USD":
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            "resolvedDeploymentSpecification.currency",
            "Deployment selections must be resolved from canonical USD state",
        )

    expected_digest = calculate_digest(specification)
    if not hmac.compare_digest(specification["digest"], expected_digest):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH",
            "resolvedDeploymentSpecification.digest",
            "Resolved deployment specification digest does not match its content",
        )

    provider_by_slot = _provider_by_slot(expected_cheapest_path)
    _validate_optimization_context(
        specification["optimization_context"],
        expected_catalog_context=expected_catalog_context,
        expected_result=expected_result,
    )
    _validate_components(
        specification["components"],
        provider_by_slot=provider_by_slot,
        registry=registry,
        optimization_context=specification["optimization_context"],
    )
    return ValidatedResolvedDeploymentSpecification(
        specification=specification,
        canonical_json=serialized,
        digest=expected_digest,
        schema_version=SCHEMA_VERSION,
    )


def _validate_v2_specification(
    raw_specification: Mapping[str, Any],
    *,
    expected_run_id: str,
    expected_cheapest_path: Mapping[str, Any],
    expected_catalog_context: PricingCatalogContext,
    expected_result: Mapping[str, Any],
) -> ValidatedResolvedDeploymentSpecification:
    _scan_payload(raw_specification)
    serialized = canonical_json(raw_specification)
    if len(serialized.encode("utf-8")) > MAX_CANONICAL_BYTES:
        _fail(
            "DEPLOYMENT_SPECIFICATION_TOO_LARGE",
            "resolvedDeploymentSpecification",
            "Resolved deployment specification exceeds the size limit",
        )
    specification = json.loads(serialized)
    schema, registry, definitions = _v2_contract()
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
            f"resolvedDeploymentSpecification.{location}".rstrip("."),
            "Resolved deployment specification does not match schema v2",
        )
    if specification["calculation_run_id"] != expected_run_id:
        _fail(
            "DEPLOYMENT_SPECIFICATION_RUN_MISMATCH",
            "resolvedDeploymentSpecification.calculation_run_id",
            "Resolved deployment specification belongs to a different run",
        )
    if specification["currency"] != "USD":
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            "resolvedDeploymentSpecification.currency",
            "Five-layer v2 deployment selections use canonical USD",
        )
    if specification["readiness"] != {
        "status": "deployment_ready",
        "blocking_gate_ids": [],
    }:
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            "resolvedDeploymentSpecification.readiness",
            "Only a blocker-free deployment-ready v2 specification may persist",
        )
    expected_digest = calculate_digest(specification)
    if not hmac.compare_digest(specification["digest"], expected_digest):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH",
            "resolvedDeploymentSpecification.digest",
            "Resolved deployment specification digest does not match its content",
        )
    _validate_v2_context(
        specification,
        expected_catalog_context=expected_catalog_context,
        expected_result=expected_result,
        registry=registry,
        definitions=definitions,
    )
    _validate_v2_selections(
        specification,
        expected_cheapest_path=expected_cheapest_path,
        expected_architecture=expected_result["resolvedTwinArchitecture"],
        registry=registry,
    )
    return ValidatedResolvedDeploymentSpecification(
        specification=specification,
        canonical_json=serialized,
        digest=expected_digest,
        schema_version=V2_SCHEMA_VERSION,
    )


def _validate_v2_context(
    specification: Mapping[str, Any],
    *,
    expected_catalog_context: PricingCatalogContext,
    expected_result: Mapping[str, Any],
    registry: Mapping[str, Any],
    definitions: Mapping[str, Any],
) -> None:
    context = specification["optimization_context"]
    architecture = expected_result.get("resolvedTwinArchitecture")
    if not isinstance(architecture, Mapping):
        _fail(
            "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
            "resolvedTwinArchitecture",
            "Five-layer v2 result is missing its resolved architecture",
        )
    expected_profile = {
        "id": definitions["profile"]["profile_id"],
        "version": definitions["profile"]["profile_version"],
        "digest": definitions["profile"]["content_digest"],
    }
    expected_catalog = {
        "id": definitions["catalog"]["catalog_id"],
        "version": definitions["catalog"]["catalog_version"],
        "digest": definitions["catalog"]["content_digest"],
    }
    scenario_ref = context["eventing_scenario_ref"]
    expected_scenario_digest = definitions["eventing"]["scenario_digests"].get(
        scenario_ref["id"]
    )
    if (
        specification["architecture_profile_ref"] != expected_profile
        or architecture.get("architecture_profile_ref") != expected_profile
        or context["service_decision_ref"] != registry["package_ref"]
        or context["component_catalog_ref"] != expected_catalog
        or context["workload_ref"] != definitions["profile"]["workload_contract_ref"]
        or architecture.get("workload_contract_ref") != context["workload_ref"]
        or context["formula_set_ref"]
        != {
            "id": "phase-08-complete-service-bundles",
            "version": "1",
            "digest": registry["pricing_ownership_digest"],
        }
        or scenario_ref.get("version") != "1"
        or scenario_ref.get("digest") != expected_scenario_digest
        or architecture.get("deployment_specification_ref")
        != {
            "schema_version": V2_SCHEMA_VERSION,
            "calculation_run_id": specification["calculation_run_id"],
            "digest": specification["digest"],
        }
    ):
        _fail(
            "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
            "resolvedDeploymentSpecification.optimization_context",
            "Five-layer v2 profile, workload, formula, or deployment evidence differs",
        )
    used_providers = {
        str(item["provider"]) for item in specification["component_selections"]
    }
    expected_pricing = [
        {
            "provider": provider,
            "digest": expected_catalog_context.catalogs[provider].content_digest,
        }
        for provider in sorted(used_providers)
    ]
    if context["pricing_evidence_refs"] != expected_pricing:
        _fail(
            "DEPLOYMENT_SPECIFICATION_CATALOG_MISMATCH",
            "resolvedDeploymentSpecification.optimization_context.pricing_evidence_refs",
            "Five-layer v2 pricing evidence does not match the run catalogs",
        )


def _validate_v2_selections(
    specification: Mapping[str, Any],
    *,
    expected_cheapest_path: Mapping[str, Any],
    expected_architecture: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> None:
    expected_provider: dict[str, str] = {}
    for logical, path_key in V2_LOGICAL_TO_PATH.items():
        raw_provider = expected_cheapest_path.get(path_key)
        if (
            not isinstance(raw_provider, str)
            or raw_provider.strip().lower() not in PROVIDERS
        ):
            _fail(
                "DEPLOYMENT_SPECIFICATION_PATH_MISMATCH",
                f"cheapest_path.{path_key}",
                "Selected provider path is incomplete or unsupported",
            )
        expected_provider[logical] = raw_provider.strip().lower()
    expected_assignments: dict[str, Mapping[str, Any]] = {}
    for assignment in expected_architecture.get("component_assignments", []):
        if not isinstance(assignment, Mapping):
            continue
        logical = assignment.get("logical_component_id")
        if isinstance(logical, str):
            expected_assignments[logical] = assignment
    if set(expected_assignments) != set(expected_provider):
        _fail(
            "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
            "resolvedTwinArchitecture.component_assignments",
            "Five-layer v2 architecture assignments are incomplete",
        )
    component_index = {
        item["component_id"]: item for item in registry["components"]
    }
    selections = specification["component_selections"]
    selection_ids: set[str] = set()
    dimension_owner: dict[str, str] = {}
    selected_components: dict[str, list[str]] = {
        logical: [] for logical in expected_provider
    }
    for selection in selections:
        selection_id = selection["selection_id"]
        component_id = selection["implementation_component_id"]
        logical = selection["logical_component_id"]
        registered = component_index.get(component_id)
        if (
            selection_id in selection_ids
            or logical not in expected_provider
            or selection["provider"] != expected_provider[logical]
            or selection_id != f"selection.{selection['provider']}.{component_id}"
            or selection["architecture_assignment_id"]
            != expected_assignments.get(logical, {}).get("assignment_id")
            or selection["region"]
            != expected_assignments.get(logical, {}).get("region")
            or selection["required"] is not True
            or registered is None
            or registered["provider"] != selection["provider"]
            or registered["component_digest"]
            != selection["implementation_component_digest"]
        ):
            _fail(
                "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
                "resolvedDeploymentSpecification.component_selections",
                "Five-layer v2 selection differs from its path or component registry",
            )
        selection_ids.add(selection_id)
        selected_components[logical].append(component_id)
        base_dimensions = [
            item["dimension_id"].rsplit(".", 1)[-1]
            for item in selection["dimensions"]
        ]
        if base_dimensions != registered["capacity_dimensions"]:
            _fail(
                "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                f"resolvedDeploymentSpecification.{selection_id}.dimensions",
                "Five-layer v2 dimensions differ from the component registry",
            )
        for dimension in selection["dimensions"]:
            dimension_id = dimension["dimension_id"]
            if (
                dimension_id in dimension_owner
                or dimension["formula_reference"]
                != "formula.phase-08-complete-service-bundles"
                or dimension["evidence_reference"]
                != registry["capacity_evidence_digest"]
            ):
                _fail(
                    "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                    f"resolvedDeploymentSpecification.{selection_id}.dimensions",
                    "Five-layer v2 dimension evidence is duplicated or unbound",
                )
            dimension_owner[dimension_id] = selection_id
    if set(expected_provider) != {
        selection["logical_component_id"] for selection in selections
    }:
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolvedDeploymentSpecification.component_selections",
            "Five-layer v2 does not cover all logical components",
        )
    for logical, assignment in expected_assignments.items():
        if (
            assignment.get("provider") != expected_provider[logical]
            or selected_components[logical]
            != assignment.get("deployment_specification_component_ids")
        ):
            _fail(
                "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
                f"resolvedDeploymentSpecification.component_selections.{logical}",
                "Five-layer v2 components differ from the resolved architecture",
            )
    binding_sources: set[str] = set()
    for binding in specification["bindings"]:
        source = binding["source_ref"]
        if (
            source in binding_sources
            or source not in dimension_owner
            or binding["destination_selection_id"] != dimension_owner[source]
        ):
            _fail(
                "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                "resolvedDeploymentSpecification.bindings",
                "Five-layer v2 binding ownership is incomplete or duplicated",
            )
        binding_sources.add(source)
    if binding_sources != set(dimension_owner):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            "resolvedDeploymentSpecification.bindings",
            "Every Five-layer v2 dimension requires exactly one binding",
        )


def _scan_payload(value: object, *, path: str = "$", depth: int = 0) -> None:
    if depth > MAX_RECURSION_DEPTH:
        _fail(
            "DEPLOYMENT_SPECIFICATION_TOO_DEEP",
            "resolvedDeploymentSpecification",
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
            _scan_payload(
                nested,
                path=f"{path}.{key}",
                depth=depth + 1,
            )
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_payload(
                nested,
                path=f"{path}[{index}]",
                depth=depth + 1,
            )


def _provider_by_slot(
    cheapest_path: Mapping[str, Any],
) -> dict[str, str]:
    providers: dict[str, str] = {}
    for slot_id, path_key in PATH_KEY_BY_SLOT.items():
        raw_provider = cheapest_path.get(path_key)
        if not isinstance(raw_provider, str):
            _fail(
                "DEPLOYMENT_SPECIFICATION_PATH_MISMATCH",
                f"cheapest_path.{path_key}",
                "Selected provider path is incomplete",
            )
        provider = raw_provider.strip().lower()
        if provider not in PROVIDERS:
            _fail(
                "DEPLOYMENT_SPECIFICATION_PATH_MISMATCH",
                f"cheapest_path.{path_key}",
                "Selected provider path contains an unsupported provider",
            )
        providers[slot_id] = provider
    return providers


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


def _validate_optimization_context(
    context: Mapping[str, Any],
    *,
    expected_catalog_context: PricingCatalogContext,
    expected_result: Mapping[str, Any],
) -> None:
    if context.get("catalog_references") != _catalog_references(
        expected_catalog_context
    ):
        _fail(
            "DEPLOYMENT_SPECIFICATION_CATALOG_MISMATCH",
            "resolvedDeploymentSpecification.optimization_context.catalog_references",
            "Deployment specification pricing evidence does not match the run",
        )

    profile = expected_result.get("optimizationProfile")
    strategy = expected_result.get("calculationStrategy")
    if not isinstance(profile, Mapping) or not isinstance(strategy, Mapping):
        _fail(
            "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
            "resolvedDeploymentSpecification.optimization_context",
            "Optimizer strategy metadata is missing",
        )
    expected_values = {
        "optimization_profile_id": expected_result.get(
            "optimization_profile_id"
        ),
        "optimization_profile_version": profile.get("profile_version"),
        "calculation_strategy_id": expected_result.get(
            "calculation_strategy_id"
        ),
        "formula_set_id": strategy.get("formula_set_id"),
        "workload_contract_id": strategy.get("workload_contract_id"),
        "pricing_registry_version": profile.get("pricing_registry_version"),
    }
    for field, expected in expected_values.items():
        if not isinstance(expected, str) or context.get(field) != expected:
            _fail(
                "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
                f"resolvedDeploymentSpecification.optimization_context.{field}",
                "Deployment specification strategy evidence does not match the run",
            )


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


def _required_transition_component_ids(
    registry: Mapping[str, Any],
    provider_by_slot: Mapping[str, str],
) -> list[str]:
    return [
        transition["component_by_provider"][
            provider_by_slot[transition["source_slot"]]
        ]
        for transition in registry["transition_runtime_policy"][
            "transitions"
        ]
    ]


def _validate_components(
    components: list[dict[str, Any]],
    *,
    provider_by_slot: Mapping[str, str],
    registry: Mapping[str, Any],
    optimization_context: Mapping[str, Any],
) -> None:
    components_by_slot: dict[str, list[dict[str, Any]]] = {
        slot_id: []
        for slot_id in (
            *SLOT_ORDER,
            "transition_runtime",
            "cross_cloud_glue",
        )
    }
    for component in components:
        components_by_slot[component["slot_id"]].append(component)

    expected_component_ids: list[str] = []
    for slot_id in SLOT_ORDER:
        provider = provider_by_slot[slot_id]
        requirement = registry["slot_requirements"].get(slot_id, {}).get(provider)
        if not isinstance(requirement, Mapping):
            _fail(
                "DEPLOYMENT_SPECIFICATION_PATH_MISMATCH",
                f"resolvedDeploymentSpecification.components.{slot_id}",
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
                f"resolvedDeploymentSpecification.components.{slot_id}",
                "Deployment components do not match the selected provider slot",
            )
        expected_component_ids.extend(expected_for_slot)

    expected_transition_ids = _required_transition_component_ids(
        registry,
        provider_by_slot,
    )
    actual_transition_ids = [
        component["component_id"]
        for component in components_by_slot["transition_runtime"]
    ]
    if actual_transition_ids != expected_transition_ids:
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolvedDeploymentSpecification.components.transition_runtime",
            "Transition runtimes do not match their source storage providers",
        )
    expected_component_ids.extend(expected_transition_ids)

    glue_component_by_provider = registry["cross_cloud_glue_policy"][
        "component_by_provider"
    ]
    expected_glue_ids = [
        glue_component_by_provider[provider]
        for provider in _required_glue_providers(registry, provider_by_slot)
    ]
    actual_glue_ids = [
        component["component_id"]
        for component in components_by_slot["cross_cloud_glue"]
    ]
    if actual_glue_ids != expected_glue_ids:
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolvedDeploymentSpecification.components.cross_cloud_glue",
            "Cross-cloud receiver components do not match the selected path",
        )
    expected_component_ids.extend(expected_glue_ids)

    actual_component_ids = [component["component_id"] for component in components]
    if actual_component_ids != expected_component_ids:
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolvedDeploymentSpecification.components",
            "Deployment component ordering or cardinality is invalid",
        )

    terraform_targets: dict[str, object] = {}
    for component in components:
        _validate_component(
            component,
            registry=registry,
            optimization_context=optimization_context,
            terraform_targets=terraform_targets,
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
            "resolvedDeploymentSpecification.components",
            "Deployment specification contains an unknown component",
        )
    for field in ("slot_id", "provider", "service_id"):
        if component[field] != registered[field]:
            _fail(
                "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
                f"resolvedDeploymentSpecification.components.{component_id}.{field}",
                "Deployment component metadata differs from the registry",
            )

    definitions = registered["dimensions"]
    dimensions = component["dimensions"]
    if [dimension["dimension_id"] for dimension in dimensions] != list(definitions):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            f"resolvedDeploymentSpecification.components.{component_id}.dimensions",
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
                f"resolvedDeploymentSpecification.components.{component_id}.{dimension_id}",
                "Deployment dimension classification differs from the registry",
            )
        for field, expected in expected_optional.items():
            if dimension.get(field) != expected:
                _fail(
                    "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                    (
                        "resolvedDeploymentSpecification.components."
                        f"{component_id}.{dimension_id}.{field}"
                    ),
                    "Deployment dimension metadata differs from the registry",
                )

        expected_formula = (
            f"formula_set:{optimization_context['formula_set_id']}"
        )
        if dimension["formula_reference"] != expected_formula:
            _fail(
                "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
                f"resolvedDeploymentSpecification.components.{component_id}.{dimension_id}",
                "Deployment dimension formula reference is not bound to the run",
            )
        expected_evidence = _expected_evidence_reference(
            registered["provider"],
            dimension_id,
            definition["classification"],
            registry=registry,
            optimization_context=optimization_context,
        )
        if dimension["evidence_reference"] != expected_evidence:
            _fail(
                "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
                f"resolvedDeploymentSpecification.components.{component_id}.{dimension_id}",
                "Deployment dimension evidence reference is not bound to the run",
            )

        target = definition.get("terraform_target")
        if target is not None:
            previous = terraform_targets.setdefault(target, dimension["value"])
            if previous != dimension["value"]:
                _fail(
                    "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                    f"resolvedDeploymentSpecification.components.{component_id}.{dimension_id}",
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
                f"resolvedDeploymentSpecification.components.{component_id}",
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
    if not valid_type:
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            f"resolvedDeploymentSpecification.components.{component_id}.{dimension_id}",
            "Deployment dimension has the wrong value type",
        )
    if "allowed_values" in definition and value not in definition["allowed_values"]:
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            f"resolvedDeploymentSpecification.components.{component_id}.{dimension_id}",
            "Deployment dimension value is unsupported",
        )
    if "minimum" in definition and value < definition["minimum"]:
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            f"resolvedDeploymentSpecification.components.{component_id}.{dimension_id}",
            "Deployment dimension value is below its minimum",
        )
    if "maximum" in definition and value > definition["maximum"]:
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            f"resolvedDeploymentSpecification.components.{component_id}.{dimension_id}",
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
        return (
            f"workload_contract:{optimization_context['workload_contract_id']}"
        )
    snapshot_id = optimization_context["catalog_references"][provider][
        "snapshot_id"
    ]
    return f"catalog:{snapshot_id}"
