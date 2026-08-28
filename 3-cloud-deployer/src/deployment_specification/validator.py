"""Strict validation for manifest-bound deployment specifications."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker

from .contract import (
    PROVIDERS,
    V2_SCHEMA_VERSION,
    V4_MANIFEST_VERSION,
    SLOT_ORDER,
    load_manifest_schema,
    load_v2_contract,
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
LOGICAL_COMPONENT_TO_SLOT = {
    "component.ingestion": "l1_ingestion",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot_storage",
    "component.cool-storage": "l3_cool_storage",
    "component.archive-storage": "l3_archive_storage",
    "component.twin-state": "l4_twin_state",
    "component.visualization": "l5_visualization",
}
SUPPORTED_V4_PROFILE_REFS = {
    ("six-layer-eventing", "1"),
}
DEPLOYER_KEY_BY_SLOT = {
    "l1_ingestion": "layer_1_provider",
    "l2_processing": "layer_2_provider",
    "l3_hot_storage": "layer_3_hot_provider",
    "l3_cool_storage": "layer_3_cold_provider",
    "l3_archive_storage": "layer_3_archive_provider",
    "l4_twin_state": "layer_4_provider",
    "l5_visualization": "layer_5_provider",
}


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
    """Validate a v3 execution manifest or a frozen historical v2 manifest."""

    if not isinstance(raw_manifest, Mapping):
        _fail(
            "DEPLOYMENT_MANIFEST_REQUIRED",
            "deployment_manifest",
            "DeploymentManifest is required for deployment operations",
        )
    version = raw_manifest.get("manifest_version")
    if version != V4_MANIFEST_VERSION:
        _fail(
            "DEPLOYMENT_MANIFEST_VERSION_UNSUPPORTED",
            "deployment_manifest.manifest_version",
            "DeploymentManifest version is unsupported",
        )
    architecture = _validate_current_manifest(raw_manifest, str(version))

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

    provider_by_slot: dict[str, str] = {}
    manifest_providers = raw_manifest.get("providers")
    if not isinstance(manifest_providers, Mapping):
        _fail(
            "DEPLOYMENT_SPECIFICATION_PROVIDER_MISMATCH",
            "deployment_manifest.providers",
            "Deployment manifest provider path is missing",
        )

    architecture_provider_by_slot = (
        _providers_from_architecture(architecture) if architecture is not None else None
    )
    for slot_id in SLOT_ORDER:
        deployer_key = DEPLOYER_KEY_BY_SLOT[slot_id]
        configured = _normalize_provider(
            provider_config.get(deployer_key), deployer_key
        )
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
        if (
            architecture_provider_by_slot is not None
            and manifested != architecture_provider_by_slot[slot_id]
        ):
            _fail(
                "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
                f"deployment_manifest.providers.{deployer_key}",
                "Deployment provider projection differs from resolved architecture",
            )
        provider_by_slot[slot_id] = configured
    _validate_manifest_v3_metadata(
        raw_manifest,
        _architecture_providers(architecture),
    )

    if specification.schema_version != V2_SCHEMA_VERSION:
        _fail(
            "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
            "deployment_manifest.resolved_deployment_specification",
            "DeploymentManifest v4 requires RDS v2",
        )
    _validate_v4_architecture_specification(
        raw_manifest,
        architecture,
        specification.specification,
    )
    return ValidatedDeploymentManifest(
        manifest=MappingProxyType(dict(raw_manifest)),
        specification=specification,
        provider_by_slot=MappingProxyType(provider_by_slot),
        manifest_version=str(version),
        architecture=MappingProxyType(dict(architecture)),
    )


def _validate_current_manifest(
    raw_manifest: Mapping[str, Any],
    version: str,
) -> dict[str, Any]:
    _scan_manifest_payload(raw_manifest)
    serialized = canonical_json(raw_manifest)
    if len(serialized.encode("utf-8")) > MAX_CANONICAL_BYTES * 4:
        _fail(
            "DEPLOYMENT_MANIFEST_INVALID",
            "deployment_manifest",
            "DeploymentManifest exceeds the size limit",
        )
    errors = sorted(
        Draft202012Validator(
            load_manifest_schema(version),
            format_checker=FormatChecker(),
        ).iter_errors(json.loads(serialized)),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].absolute_path)
        _fail(
            "DEPLOYMENT_MANIFEST_INVALID",
            f"deployment_manifest.{location}".rstrip("."),
            "DeploymentManifest does not match its versioned schema",
        )

    architecture = raw_manifest.get("resolved_twin_architecture")
    if not isinstance(architecture, Mapping):
        _fail(
            "DEPLOYMENT_ARCHITECTURE_MISSING",
            "deployment_manifest.resolved_twin_architecture",
            "Resolved architecture is required",
        )
    from src.architecture_profiles import contracts
    from src.architecture_profiles.contracts import calculate_digest
    from src.architecture_profiles.registry import ArchitectureProfileRegistry

    expected_digest = calculate_digest(architecture)
    actual_digest = architecture.get("content_digest")
    manifest_digest = raw_manifest.get("resolved_twin_architecture_digest")
    if (
        not isinstance(actual_digest, str)
        or not isinstance(manifest_digest, str)
        or not hmac.compare_digest(actual_digest, expected_digest)
        or not hmac.compare_digest(manifest_digest, expected_digest)
    ):
        _fail(
            "DEPLOYMENT_ARCHITECTURE_DIGEST_MISMATCH",
            "deployment_manifest.resolved_twin_architecture_digest",
            "Resolved architecture digest does not match its content",
        )

    run_id = raw_manifest.get("calculation_run_id")
    specification = raw_manifest.get("resolved_deployment_specification")
    specification_ref = architecture.get("deployment_specification_ref")
    if (
        architecture.get("calculation_run_id") != run_id
        or not isinstance(specification, Mapping)
        or specification.get("calculation_run_id") != run_id
        or not isinstance(specification_ref, Mapping)
        or specification_ref.get("calculation_run_id") != run_id
        or specification_ref.get("schema_version")
        != specification.get("schema_version")
        or specification_ref.get("digest")
        != raw_manifest.get("resolved_deployment_specification_digest")
    ):
        _fail(
            "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
            "deployment_manifest.calculation_run_id",
            "Manifest architecture and deployment specification references differ",
        )

    profile_ref = architecture.get("architecture_profile_ref")
    profile_identity = (
        (
            str(profile_ref.get("id") or ""),
            str(profile_ref.get("version") or ""),
        )
        if isinstance(profile_ref, Mapping)
        else ("", "")
    )
    supported_profile_refs = SUPPORTED_V4_PROFILE_REFS
    if profile_identity not in supported_profile_refs:
        _fail(
            "DEPLOYMENT_PROFILE_CATALOG_MISMATCH",
            "deployment_manifest.resolved_twin_architecture.architecture_profile_ref",
            "Manifest and architecture profile versions are incompatible",
        )
    registry = ArchitectureProfileRegistry(
        profile_id=profile_identity[0],
        profile_version=profile_identity[1],
    )
    linked_documents = (
        registry.profile,
        *registry.providers.values(),
        registry.catalog,
    )
    try:
        contracts.read_contract(
            architecture,
            linked_documents=linked_documents,
        )
    except contracts.ContractError as exc:
        contract_code = str(getattr(exc, "code", ""))
        contract_path = str(getattr(exc, "path", ""))
        if contract_code == "ARCH_EDGE_UNAVAILABLE":
            code = "DEPLOYMENT_GRAPH_EDGE_UNRESOLVED"
        elif contract_code == "ARCH_DUPLICATE_ID" and "resolved_edges" in contract_path:
            code = "DEPLOYMENT_GRAPH_BINDING_DUPLICATE"
        elif contract_code == "ARCH_GRAPH_CYCLE_FORBIDDEN":
            code = "DEPLOYMENT_GRAPH_CYCLE_FORBIDDEN"
        elif contract_code == "ARCH_COMPONENT_UNAVAILABLE":
            code = "DEPLOYMENT_GRAPH_NODE_UNRESOLVED"
        elif contract_code == "ARCH_EXTENSION_BINDING_INVALID":
            code = "DEPLOYMENT_GRAPH_BINDING_INCOMPATIBLE"
        else:
            code = "DEPLOYMENT_ARCHITECTURE_INVALID"
        _fail(
            code,
            "deployment_manifest.resolved_twin_architecture",
            "Resolved architecture does not satisfy its pinned contract",
        )
    catalog_ref = raw_manifest.get("compatibility", {}).get("component_catalog_ref")
    expected_profile = {
        "id": registry.profile["profile_id"],
        "version": registry.profile["profile_version"],
        "digest": registry.profile["content_digest"],
    }
    expected_catalog = {
        "id": registry.catalog["catalog_id"],
        "version": registry.catalog["catalog_version"],
        "digest": registry.catalog["content_digest"],
    }
    if profile_ref != expected_profile or catalog_ref != expected_catalog:
        _fail(
            "DEPLOYMENT_PROFILE_CATALOG_MISMATCH",
            "deployment_manifest.compatibility",
            "Manifest profile or component catalog reference is unsupported",
        )
    return json.loads(canonical_json(architecture))


def _validate_v4_architecture_specification(
    manifest: Mapping[str, Any],
    architecture: Mapping[str, Any] | None,
    specification: Mapping[str, Any],
) -> None:
    """Require an exact, publishable RTA-v2/RDS-v2 execution pair."""

    if architecture is None:
        _fail(
            "DEPLOYMENT_ARCHITECTURE_MISSING",
            "deployment_manifest.resolved_twin_architecture",
            "DeploymentManifest v4 requires a resolved architecture",
        )
    if (
        architecture.get("schema_version") != "resolved-twin-architecture.v2"
        or architecture.get("resolution_status") != "publishable"
        or architecture.get("functional_completeness", {}).get("status") != "complete"
        or specification.get("readiness")
        != {"status": "deployment_ready", "blocking_gate_ids": []}
    ):
        _fail(
            "DEPLOYMENT_SPECIFICATION_NOT_READY",
            "deployment_manifest.resolved_deployment_specification.readiness",
            "Only a blocker-free publishable Phase 8 pair may deploy",
        )

    profile_ref = architecture["architecture_profile_ref"]
    context = specification["optimization_context"]
    catalog_ref = manifest["compatibility"]["component_catalog_ref"]
    if (
        specification["architecture_profile_ref"] != profile_ref
        or context["component_catalog_ref"] != catalog_ref
        or context["workload_ref"] != architecture["workload_contract_ref"]
    ):
        _fail(
            "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
            "deployment_manifest.resolved_deployment_specification.optimization_context",
            "Manifest v4 profile, catalog, or workload references differ",
        )

    assignments = {
        item["assignment_id"]: item for item in architecture["component_assignments"]
    }
    selected_by_assignment: dict[str, list[Mapping[str, Any]]] = {
        assignment_id: [] for assignment_id in assignments
    }
    for selection in specification["component_selections"]:
        assignment_id = selection["architecture_assignment_id"]
        assignment = assignments.get(assignment_id)
        if (
            assignment is None
            or selection["logical_component_id"] != assignment["logical_component_id"]
            or selection["provider"] != assignment["provider"]
            or selection["region"] != assignment["region"]
        ):
            _fail(
                "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
                "deployment_manifest.resolved_deployment_specification.component_selections",
                "Phase 8 selection differs from its architecture assignment",
            )
        selected_by_assignment[assignment_id].append(selection)
    for assignment_id, assignment in assignments.items():
        actual_ids = [
            item["implementation_component_id"]
            for item in selected_by_assignment[assignment_id]
        ]
        if actual_ids != assignment["deployment_specification_component_ids"]:
            _fail(
                "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
                f"deployment_manifest.resolved_twin_architecture.{assignment_id}",
                "Architecture component ownership differs from RDS v2",
            )


def _scan_manifest_payload(
    value: object,
    *,
    path: str = "$",
    depth: int = 0,
) -> None:
    """Reject secret-bearing fields while allowing credential source metadata."""

    if depth > MAX_RECURSION_DEPTH:
        _fail(
            "DEPLOYMENT_MANIFEST_INVALID",
            "deployment_manifest",
            "DeploymentManifest exceeds the nesting limit",
        )
    forbidden_fragments = {
        "accesskeyid",
        "apikey",
        "clientsecret",
        "connectionstring",
        "password",
        "privatekey",
        "refreshtoken",
        "secretaccesskey",
        "sessiontoken",
    }
    allowed_metadata_keys = {
        "containssecretpayloads",
        "platformruntimesecretreference",
        "secretbearingfiles",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            compact = re.sub(r"[^a-z0-9]", "", normalized)
            if compact not in allowed_metadata_keys and any(
                fragment in compact for fragment in forbidden_fragments
            ):
                _fail(
                    "DEPLOYMENT_MANIFEST_INVALID",
                    path,
                    "Secret-bearing fields are forbidden in DeploymentManifest",
                )
            _scan_manifest_payload(
                nested,
                path=f"{path}.{key}",
                depth=depth + 1,
            )
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_manifest_payload(
                nested,
                path=f"{path}[{index}]",
                depth=depth + 1,
            )


def _validate_manifest_v3_metadata(
    manifest: Mapping[str, Any],
    architecture_providers: set[str],
) -> None:
    package = manifest["package"]
    files = set(package["files"])
    required_files = set(package["required_files"])
    secret_files = set(package["secret_bearing_files"])
    if not required_files <= files or not secret_files <= files:
        _fail(
            "DEPLOYMENT_MANIFEST_INVALID",
            "deployment_manifest.package",
            "Manifest package file sets are inconsistent",
        )
    credentials = manifest["credentials"]
    credential_providers = {
        _normalize_provider(
            provider,
            "deployment_manifest.credentials.providers",
        )
        for provider in credentials["providers"]
    }
    credential_sources = {
        _normalize_provider(
            provider,
            "deployment_manifest.credentials.sources",
        )
        for provider in credentials["sources"]
    }
    if (
        credential_providers != architecture_providers
        or credential_sources != architecture_providers
        or credentials["contains_secret_payloads"] is not False
    ):
        _fail(
            "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH",
            "deployment_manifest.credentials",
            "Credential metadata differs from architecture provider ownership",
        )


def _providers_from_architecture(
    architecture: Mapping[str, Any],
) -> dict[str, str]:
    providers: dict[str, str] = {}
    assignments = architecture.get("component_assignments")
    if not isinstance(assignments, list):
        _fail(
            "DEPLOYMENT_ARCHITECTURE_INVALID",
            "deployment_manifest.resolved_twin_architecture.component_assignments",
            "Resolved architecture assignments are invalid",
        )
    for assignment in assignments:
        if not isinstance(assignment, Mapping):
            continue
        slot_id = LOGICAL_COMPONENT_TO_SLOT.get(
            str(assignment.get("logical_component_id"))
        )
        if slot_id is None:
            if assignment.get("logical_component_id") == "component.eventing":
                _normalize_provider(
                    assignment.get("provider"),
                    (
                        "deployment_manifest.resolved_twin_architecture."
                        "component_assignments.eventing.provider"
                    ),
                )
                continue
            _fail(
                "DEPLOYMENT_ARCHITECTURE_INVALID",
                "deployment_manifest.resolved_twin_architecture.component_assignments",
                "Resolved architecture component assignment is unknown or duplicated",
            )
        if slot_id in providers:
            _fail(
                "DEPLOYMENT_ARCHITECTURE_INVALID",
                "deployment_manifest.resolved_twin_architecture.component_assignments",
                "Resolved architecture component assignment is unknown or duplicated",
            )
        providers[slot_id] = _normalize_provider(
            assignment.get("provider"),
            (
                "deployment_manifest.resolved_twin_architecture."
                f"component_assignments.{slot_id}.provider"
            ),
        )
    if set(providers) != set(SLOT_ORDER):
        _fail(
            "DEPLOYMENT_ARCHITECTURE_INVALID",
            "deployment_manifest.resolved_twin_architecture.component_assignments",
            "Resolved architecture does not cover every baseline component",
        )
    return providers


def _architecture_providers(architecture: Mapping[str, Any]) -> set[str]:
    assignments = architecture.get("component_assignments")
    if not isinstance(assignments, list):
        return set()
    return {
        _normalize_provider(
            assignment.get("provider"),
            "deployment_manifest.resolved_twin_architecture.component_assignments",
        )
        for assignment in assignments
        if isinstance(assignment, Mapping)
    }


def validate_resolved_deployment_specification(
    raw_specification: object,
) -> ValidatedResolvedDeploymentSpecification:
    """Validate and canonicalize an untrusted versioned specification."""

    if not isinstance(raw_specification, Mapping):
        _fail(
            "DEPLOYMENT_SPECIFICATION_MISSING",
            "resolved_deployment_specification",
            "Resolved deployment specification is missing",
        )
    if raw_specification.get("schema_version") == V2_SCHEMA_VERSION:
        return _validate_v2_resolved_deployment_specification(raw_specification)
    _fail(
        "DEPLOYMENT_SPECIFICATION_VERSION_UNSUPPORTED",
        "resolved_deployment_specification.schema_version",
        "Only resolved-deployment-specification.v2 is supported",
    )


def _validate_v2_resolved_deployment_specification(
    raw_specification: Mapping[str, Any],
) -> ValidatedResolvedDeploymentSpecification:
    """Validate the generic v2 component selections without pricing again."""

    _scan_payload(raw_specification)
    serialized = canonical_json(raw_specification)
    if len(serialized.encode("utf-8")) > MAX_CANONICAL_BYTES:
        _fail(
            "DEPLOYMENT_SPECIFICATION_TOO_LARGE",
            "resolved_deployment_specification",
            "Resolved deployment specification exceeds the size limit",
        )
    specification = json.loads(serialized)
    schema, registry = load_v2_contract()
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
            "Resolved deployment specification does not match schema v2",
        )
    if specification["currency"] != "USD":
        _fail(
            "DEPLOYMENT_SPECIFICATION_INVALID",
            "resolved_deployment_specification.currency",
            "Phase 8 deployment selections must use canonical USD",
        )
    expected_digest = calculate_digest(specification)
    if not hmac.compare_digest(specification["digest"], expected_digest):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH",
            "resolved_deployment_specification.digest",
            "Resolved deployment specification digest does not match its content",
        )
    _validate_v2_component_selections(specification, registry)
    return ValidatedResolvedDeploymentSpecification(
        specification=MappingProxyType(specification),
        canonical_json=serialized,
        digest=expected_digest,
        schema_version=V2_SCHEMA_VERSION,
    )


def _validate_v2_component_selections(
    specification: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> None:
    """Bind every v2 selection and input binding to the frozen registry."""

    registered_components = {
        item["component_id"]: item for item in registry["components"]
    }
    profile_ref = specification["architecture_profile_ref"]
    profile_identity = (profile_ref["id"], profile_ref["version"])
    if profile_identity not in SUPPORTED_V4_PROFILE_REFS:
        _fail(
            "DEPLOYMENT_PROFILE_CATALOG_MISMATCH",
            "resolved_deployment_specification.architecture_profile_ref",
            "Phase 8 deployment profile is unsupported",
        )
    context = specification["optimization_context"]
    expected_formula_ref = {
        "id": "phase-08-complete-service-bundles",
        "version": "1",
        "digest": registry["pricing_ownership_digest"],
    }
    if (
        context["service_decision_ref"] != registry["package_ref"]
        or context["formula_set_ref"] != expected_formula_ref
    ):
        _fail(
            "DEPLOYMENT_SPECIFICATION_CONTEXT_MISMATCH",
            "resolved_deployment_specification.optimization_context",
            "Phase 8 service or formula evidence differs from the registry",
        )

    selection_ids: set[str] = set()
    dimension_owners: dict[str, str] = {}
    provider_by_logical: dict[str, str] = {}
    for selection in specification["component_selections"]:
        selection_id = selection["selection_id"]
        component_id = selection["implementation_component_id"]
        registered = registered_components.get(component_id)
        expected_selection_id = f"selection.{selection['provider']}.{component_id}"
        if (
            registered is None
            or selection_id in selection_ids
            or selection_id != expected_selection_id
            or selection["required"] is not True
            or selection["provider"] != registered["provider"]
            or selection["implementation_component_digest"]
            != registered["component_digest"]
        ):
            _fail(
                "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
                "resolved_deployment_specification.component_selections",
                "Phase 8 selection differs from the component registry",
            )
        logical_id = selection["logical_component_id"]
        previous_provider = provider_by_logical.setdefault(
            logical_id, selection["provider"]
        )
        if previous_provider != selection["provider"]:
            _fail(
                "DEPLOYMENT_SPECIFICATION_PROVIDER_MISMATCH",
                f"resolved_deployment_specification.{selection_id}.provider",
                "One logical component resolves to multiple providers",
            )
        selection_ids.add(selection_id)
        dimension_suffixes = [
            item["dimension_id"].rsplit(".", 1)[-1] for item in selection["dimensions"]
        ]
        if dimension_suffixes != registered["capacity_dimensions"]:
            _fail(
                "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                f"resolved_deployment_specification.{selection_id}.dimensions",
                "Phase 8 dimensions differ from the component registry",
            )
        for dimension in selection["dimensions"]:
            dimension_id = dimension["dimension_id"]
            suffix = dimension_id.rsplit(".", 1)[-1]
            expected_id = f"dimension.{selection['provider']}.{component_id}.{suffix}"
            if (
                dimension_id != expected_id
                or dimension_id in dimension_owners
                or dimension["formula_reference"]
                != "formula.phase-08-complete-service-bundles"
                or dimension["evidence_reference"]
                != registry["capacity_evidence_digest"]
            ):
                _fail(
                    "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                    f"resolved_deployment_specification.{selection_id}.dimensions",
                    "Phase 8 dimension identity or evidence is invalid",
                )
            dimension_owners[dimension_id] = selection_id

    expected_logical_ids = set(LOGICAL_COMPONENT_TO_SLOT)
    if profile_identity == ("six-layer-eventing", "1"):
        expected_logical_ids.add("component.eventing")
    if set(provider_by_logical) != expected_logical_ids:
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolved_deployment_specification.component_selections",
            "Phase 8 profile must cover every logical component",
        )
    if len(
        {
            provider_by_logical["component.hot-storage"],
            provider_by_logical["component.cool-storage"],
            provider_by_logical["component.archive-storage"],
            provider_by_logical["component.visualization"],
        }
    ) != 1:
        _fail(
            "DEPLOYMENT_SPECIFICATION_PROVIDER_MISMATCH",
            "resolved_deployment_specification.component_selections",
            "Six-layer PoC requires provider-local L3 storage and L5",
        )

    binding_sources: set[str] = set()
    for binding in specification["bindings"]:
        source_ref = binding["source_ref"]
        if (
            source_ref in binding_sources
            or source_ref not in dimension_owners
            or binding["destination_selection_id"] != dimension_owners[source_ref]
            or binding["source_kind"] != "deployment_dimension"
            or binding["resolution_stage"] != "preplan"
        ):
            _fail(
                "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                "resolved_deployment_specification.bindings",
                "Phase 8 binding ownership is incomplete or duplicated",
            )
        binding_sources.add(source_ref)
    if binding_sources != set(dimension_owners):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            "resolved_deployment_specification.bindings",
            "Every Phase 8 dimension requires exactly one binding",
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
