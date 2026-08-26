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


V2_SCHEMA_VERSION = "resolved-deployment-specification.v2"
READY = "ready"
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
V2_CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v2"
)
ARCHITECTURE_DEFINITIONS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
    / "definitions"
)
SIX_LAYER_WORKLOAD_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "six-layer-workload"
    / "v1"
)
V2_LOGICAL_TO_PATH = {
    "component.ingestion": "l1",
    "component.processing": "l2",
    "component.hot-storage": "l3_hot",
    "component.cool-storage": "l3_cool",
    "component.archive-storage": "l3_archive",
    "component.twin-state": "l4",
    "component.visualization": "l5",
    "component.eventing": "eventing",
}
V2_PROFILE_CATALOGS = {
    ("six-layer-eventing", "1"): (
        "six-layer-eventing",
        "six-layer-eventing-component-catalog",
        "1",
    ),
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
def _v2_contract() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        schema = json.loads((V2_CONTRACT_ROOT / "schema.json").read_text("utf-8"))
        registry = json.loads(
            (V2_CONTRACT_ROOT / "component-capacity-registry.json").read_text("utf-8")
        )
        eventing = json.loads(
            (SIX_LAYER_WORKLOAD_ROOT / "eventing-scenario-catalog.json").read_text(
                "utf-8"
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Resolved deployment v2 contract is unavailable") from exc
    Draft202012Validator.check_schema(schema)
    supplied = registry.get("content_digest")
    registry_without_digest = dict(registry)
    registry_without_digest["content_digest"] = ""
    actual = (
        "sha256:"
        + hashlib.sha256(
            canonical_json(registry_without_digest).encode("utf-8")
        ).hexdigest()
    )
    if supplied != actual:
        raise RuntimeError("Resolved deployment v2 registry digest drifted")
    return schema, registry, eventing


@lru_cache(maxsize=len(V2_PROFILE_CATALOGS))
def _v2_definitions(
    profile_id: str,
    profile_version: str,
) -> dict[str, Any]:
    catalog_ref = V2_PROFILE_CATALOGS.get((profile_id, profile_version))
    if catalog_ref is None:
        raise RuntimeError("Resolved deployment v2 profile is unsupported")
    catalog_directory, catalog_id, catalog_version = catalog_ref
    try:
        profile = json.loads(
            (
                ARCHITECTURE_DEFINITIONS_ROOT
                / "profiles"
                / profile_id
                / profile_version
                / "profile.json"
            ).read_text("utf-8")
        )
        catalog = json.loads(
            (
                ARCHITECTURE_DEFINITIONS_ROOT
                / "component-catalogs"
                / catalog_directory
                / catalog_version
                / "catalog.json"
            ).read_text("utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Resolved deployment v2 definitions are unavailable"
        ) from exc
    if (
        profile.get("profile_id") != profile_id
        or profile.get("profile_version") != profile_version
        or catalog.get("catalog_id") != catalog_id
        or catalog.get("catalog_version") != catalog_version
    ):
        raise RuntimeError("Resolved deployment v2 definition identity drifted")
    return {"profile": profile, "catalog": catalog}


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
    if raw_specification.get("schema_version") != V2_SCHEMA_VERSION:
        _fail(
            "DEPLOYMENT_SPECIFICATION_VERSION_UNSUPPORTED",
            "resolvedDeploymentSpecification.schema_version",
            "Only resolved-deployment-specification.v2 is supported",
        )
    return _validate_v2_specification(
        raw_specification,
        expected_run_id=expected_run_id,
        expected_cheapest_path=expected_cheapest_path,
        expected_catalog_context=expected_catalog_context,
        expected_result=expected_result,
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
    schema, registry, eventing = _v2_contract()
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
    if specification["currency"] not in {"USD", "EUR"} or specification[
        "currency"
    ] != expected_result.get("currency"):
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            "resolvedDeploymentSpecification.currency",
            "Phase 8 deployment selections must match the result currency",
        )
    readiness = specification["readiness"]
    ready = readiness == {
        "status": "deployment_ready",
        "blocking_gate_ids": [],
    }
    offline = readiness.get("status") == "offline_contract_fixture" and bool(
        readiness.get("blocking_gate_ids")
    )
    if not ready and not offline:
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            "resolvedDeploymentSpecification.readiness",
            "V2 readiness evidence must be coherently ready or evaluation-only",
        )
    expected_digest = calculate_digest(specification)
    if not hmac.compare_digest(specification["digest"], expected_digest):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH",
            "resolvedDeploymentSpecification.digest",
            "Resolved deployment specification digest does not match its content",
        )
    profile_ref = specification["architecture_profile_ref"]
    definitions = {
        **_v2_definitions(profile_ref["id"], profile_ref["version"]),
        "eventing": eventing,
    }
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
        profile=definitions["profile"],
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
            "Phase 8 result is missing its resolved architecture",
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
            "Phase 8 profile, workload, formula, or deployment evidence differs",
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
            "Phase 8 pricing evidence does not match the run catalogs",
        )


def _validate_v2_selections(
    specification: Mapping[str, Any],
    *,
    expected_cheapest_path: Mapping[str, Any],
    expected_architecture: Mapping[str, Any],
    registry: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> None:
    expected_provider: dict[str, str] = {}
    logical_components = {
        str(item["component_id"])
        for item in profile.get("components", [])
        if isinstance(item, Mapping) and isinstance(item.get("component_id"), str)
    }
    if not logical_components or not logical_components.issubset(V2_LOGICAL_TO_PATH):
        _fail(
            "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
            "resolvedDeploymentSpecification.architecture_profile_ref",
            "The v2 profile contains unsupported logical components",
        )
    for logical in sorted(logical_components):
        path_key = V2_LOGICAL_TO_PATH[logical]
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
            "Phase 8 architecture assignments are incomplete",
        )
    component_index = {item["component_id"]: item for item in registry["components"]}
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
                "Phase 8 selection differs from its path or component registry",
            )
        selection_ids.add(selection_id)
        selected_components[logical].append(component_id)
        base_dimensions = [
            item["dimension_id"].rsplit(".", 1)[-1] for item in selection["dimensions"]
        ]
        if base_dimensions != registered["capacity_dimensions"]:
            _fail(
                "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                f"resolvedDeploymentSpecification.{selection_id}.dimensions",
                "Phase 8 dimensions differ from the component registry",
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
                    "Phase 8 dimension evidence is duplicated or unbound",
                )
            dimension_owner[dimension_id] = selection_id
    if set(expected_provider) != {
        selection["logical_component_id"] for selection in selections
    }:
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolvedDeploymentSpecification.component_selections",
            "Phase 8 result does not cover all logical components",
        )
    for logical, assignment in expected_assignments.items():
        if assignment.get("provider") != expected_provider[
            logical
        ] or selected_components[logical] != assignment.get(
            "deployment_specification_component_ids"
        ):
            _fail(
                "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
                f"resolvedDeploymentSpecification.component_selections.{logical}",
                "Phase 8 components differ from the resolved architecture",
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
                "Phase 8 binding ownership is incomplete or duplicated",
            )
        binding_sources.add(source)
    if binding_sources != set(dimension_owner):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            "resolvedDeploymentSpecification.bindings",
            "Every Phase 8 dimension requires exactly one binding",
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
