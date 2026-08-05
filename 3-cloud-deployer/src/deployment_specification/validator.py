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
    HISTORICAL_MANIFEST_VERSION,
    MANIFEST_VERSION,
    PROVIDERS,
    SCHEMA_VERSION,
    V2_SCHEMA_VERSION,
    SLOT_ORDER,
    load_contract,
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
    if version not in {MANIFEST_VERSION, HISTORICAL_MANIFEST_VERSION}:
        _fail(
            "DEPLOYMENT_MANIFEST_VERSION_UNSUPPORTED",
            "deployment_manifest.manifest_version",
            "DeploymentManifest version is unsupported",
        )
    architecture = None
    if version == MANIFEST_VERSION:
        architecture = _validate_manifest_v3(raw_manifest)

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

    architecture_provider_by_slot = (
        _providers_from_architecture(architecture) if architecture is not None else None
    )
    for slot_id in SLOT_ORDER:
        deployer_key = registry["slots"][slot_id]["deployer_key"]
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
    if version == MANIFEST_VERSION:
        _validate_manifest_v3_metadata(
            raw_manifest,
            set(provider_by_slot.values()),
        )

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
        manifest_version=str(version),
        architecture=(
            MappingProxyType(dict(architecture)) if architecture is not None else None
        ),
    )


def _validate_manifest_v3(
    raw_manifest: Mapping[str, Any],
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
            load_manifest_schema(),
            format_checker=FormatChecker(),
        ).iter_errors(json.loads(serialized)),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].absolute_path)
        _fail(
            "DEPLOYMENT_MANIFEST_INVALID",
            f"deployment_manifest.{location}".rstrip("."),
            "DeploymentManifest does not match schema v3",
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

    registry = ArchitectureProfileRegistry()
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
    profile_ref = architecture.get("architecture_profile_ref")
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
                    "Secret-bearing fields are forbidden in DeploymentManifest v3",
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
        if slot_id is None or slot_id in providers:
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
            "Five-layer v2 deployment selections must use canonical USD",
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
            "Five-layer v2 service or formula evidence differs from the registry",
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
                "Five-layer v2 selection differs from the component registry",
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
            item["dimension_id"].rsplit(".", 1)[-1]
            for item in selection["dimensions"]
        ]
        if dimension_suffixes != registered["capacity_dimensions"]:
            _fail(
                "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
                f"resolved_deployment_specification.{selection_id}.dimensions",
                "Five-layer v2 dimensions differ from the component registry",
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
                    "Five-layer v2 dimension identity or evidence is invalid",
                )
            dimension_owners[dimension_id] = selection_id

    expected_logical_ids = set(LOGICAL_COMPONENT_TO_SLOT)
    if set(provider_by_logical) != expected_logical_ids:
        _fail(
            "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH",
            "resolved_deployment_specification.component_selections",
            "Five-layer v2 must cover every logical component",
        )
    if (
        provider_by_logical["component.hot-storage"]
        != provider_by_logical["component.visualization"]
    ):
        _fail(
            "DEPLOYMENT_SPECIFICATION_PROVIDER_MISMATCH",
            "resolved_deployment_specification.component_selections",
            "Five-layer v2 requires L3 hot and L5 provider co-location",
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
                "Five-layer v2 binding ownership is incomplete or duplicated",
            )
        binding_sources.add(source_ref)
    if binding_sources != set(dimension_owners):
        _fail(
            "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH",
            "resolved_deployment_specification.bindings",
            "Every Five-layer v2 dimension requires exactly one binding",
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


def _required_transition_component_ids(
    registry: Mapping[str, Any],
    provider_by_slot: Mapping[str, str],
) -> list[str]:
    return [
        transition["component_by_provider"][provider_by_slot[transition["source_slot"]]]
        for transition in registry["transition_runtime_policy"]["transitions"]
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
            ("resolved_deployment_specification.components.transition_runtime"),
            "Transition runtimes do not match their source storage providers",
        )
    expected_component_ids.extend(expected_transition_ids)

    component_by_provider = registry["cross_cloud_glue_policy"]["component_by_provider"]
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
    if [
        component["component_id"] for component in components
    ] != expected_component_ids:
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
    field = (
        f"resolved_deployment_specification.components.{component_id}.{dimension_id}"
    )
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
