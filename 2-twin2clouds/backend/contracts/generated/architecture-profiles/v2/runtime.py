"""Shared, network-free runtime for architecture-profile contract v2.

This module is part of the generated contract bundle. Keep it dependency-light:
the three service readers load the byte-identical generated copy.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, NoReturn

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


SCHEMA_FILES = {
    "architecture-profile.v2": "architecture-profile.schema.json",
    "provider-implementation-profile.v2": (
        "provider-implementation-profile.schema.json"
    ),
    "deployment-component-catalog.v2": ("deployment-component-catalog.schema.json"),
    "resolved-twin-architecture.v2": ("resolved-twin-architecture.schema.json"),
    "semantic-registry.v2": "semantic-registry.schema.json",
}
MAX_DOCUMENT_BYTES = 2_000_000
MAX_DEPTH = 32
MAX_ARRAY_ITEMS = 2_048
MAX_ERRORS = 20
DECIMAL_PATTERN = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
VERSION_PATTERN = re.compile(r"^[1-9][0-9]*$")
SECRET_KEY_FRAGMENTS = (
    "access_key",
    "account_key",
    "api_key",
    "client_secret",
    "connection_string",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?:AccountKey|SharedAccessKey)=[A-Za-z0-9+/=]{12,}"),
)
SET_ARRAY_FIELDS = frozenset(
    {
        "allowed_cycle_ids",
        "allowed_input_variable_ids",
        "allowed_output_ids",
        "capability_evidence",
        "capability_requirements",
        "compatible_architecture_profile_versions",
        "compatible_catalog_versions",
        "compatible_deployment_specification_versions",
        "compatible_formula_set_versions",
        "compatible_resolver_versions",
        "compatible_runtime_versions",
        "component_assignments",
        "component_mappings",
        "components",
        "cost_category_ids",
        "cost_owner_ids",
        "cycle_contracts",
        "deployment_specification_bindings",
        "deployment_specification_component_ids",
        "deployment_specification_versions",
        "edge_implementations",
        "edge_mappings",
        "edges",
        "extension_bindings",
        "extension_slot_ids",
        "extension_slot_refs",
        "extension_slots",
        "formula_refs",
        "input_port_ids",
        "input_ports",
        "known_error_codes",
        "logical_component_ids",
        "missing_capability_ids",
        "optional_components",
        "output_port_ids",
        "output_ports",
        "package_artifacts",
        "permission_capability_ids",
        "pricing_evidence_refs",
        "pricing_model_refs",
        "provided_capability_ids",
        "provider_extra_capability_ids",
        "provider_profile_refs",
        "required_capability_ids",
        "required_permission_capabilities",
        "required_provided_capability_ids",
        "required_capability_ids",
        "required_provider_profile_ids",
        "required_responsibility_ids",
        "required_schema_versions",
        "responsibilities",
        "resolved_edges",
        "supported_contract_versions",
        "supported_providers",
        "supported_runtimes",
        "unsupported_reasons",
        "workload_field_refs",
    }
)
IDENTITY_FIELDS = (
    "responsibility_id",
    "component_id",
    "edge_id",
    "deployment_component_id",
    "edge_implementation_id",
    "artifact_id",
    "assignment_id",
    "resolved_edge_id",
    "port_id",
    "bundle_id",
)
ARRAY_IDENTITY_FIELDS = {
    "responsibilities": ("responsibility_id",),
    "components": ("component_id", "deployment_component_id"),
    "edges": ("edge_id",),
    "extension_slots": ("slot_id",),
    "component_mappings": ("component_id",),
    "edge_mappings": ("edge_id",),
    "edge_implementations": ("edge_implementation_id",),
    "package_artifacts": ("artifact_id",),
    "port_contracts": ("port_id",),
    "input_ports": ("port_id",),
    "output_ports": ("port_id",),
    "component_assignments": ("assignment_id", "logical_component_id"),
    "resolved_edges": ("resolved_edge_id", "edge_id"),
    "responsibility_totals": ("item_id",),
    "component_totals": ("item_id",),
    "edge_totals": ("item_id",),
    "cycle_contracts": ("cycle_id",),
    "extension_bindings": ("slot_id",),
    "provider_profile_refs": ("id",),
    "pricing_evidence_refs": ("id",),
}
AUDIT_TIMESTAMP_FIELDS = frozenset(
    {"created_at", "updated_at", "selected_at", "validated_at"}
)


class ContractError(ValueError):
    """Stable, bounded architecture-contract validation failure."""

    def __init__(self, code: str, path: str, message: str) -> None:
        bounded = message.replace("\n", " ")[:400]
        super().__init__(bounded)
        self.code = code
        self.path = path[:240]


def _fail(code: str, path: str, message: str) -> NoReturn:
    raise ContractError(code, path, message)


def _normalize_decimal(value: str) -> str:
    if not DECIMAL_PATTERN.fullmatch(value):
        return value
    try:
        decimal = Decimal(value)
    except InvalidOperation:
        return value
    if decimal == 0:
        return "0"
    normalized = format(decimal.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def _stable_item_key(value: object, field_name: str | None = None) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for field in ARRAY_IDENTITY_FIELDS.get(field_name or "", ()):
            candidate = value.get(field)
            if isinstance(candidate, str):
                return candidate
        for field in (
            *IDENTITY_FIELDS,
            "provider",
            "reference_id",
            "schema_version",
        ):
            candidate = value.get(field)
            if isinstance(candidate, str):
                return candidate
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def canonicalize(value: object, *, field_name: str | None = None) -> object:
    """Normalize decimals and set-like arrays for deterministic hashing."""
    if isinstance(value, Mapping):
        return {
            str(key): canonicalize(nested, field_name=str(key))
            for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        normalized = [canonicalize(nested, field_name=field_name) for nested in value]
        if field_name in SET_ARRAY_FIELDS:
            normalized.sort(key=lambda item: _stable_item_key(item, field_name))
        return normalized
    if isinstance(value, str):
        return _normalize_decimal(value)
    return value


def canonical_json(value: object) -> str:
    """Return canonical UTF-8 JSON without insignificant whitespace."""
    return json.dumps(
        canonicalize(value),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    def strip(value: object) -> object:
        if isinstance(value, Mapping):
            return {
                str(key): strip(nested)
                for key, nested in value.items()
                if key != "content_digest" and key not in AUDIT_TIMESTAMP_FIELDS
            }
        if isinstance(value, (list, tuple)):
            return [strip(nested) for nested in value]
        return value

    stripped = strip(document)
    if not isinstance(stripped, dict):
        raise RuntimeError("Architecture contract digest payload must be an object")
    return stripped


def calculate_digest(document: Mapping[str, Any]) -> str:
    encoded = canonical_json(_digest_payload(document)).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def calculate_resolution_id(document: Mapping[str, Any]) -> str:
    """Calculate the required UUIDv5 from frozen resolution inputs."""
    assignment_payload = {
        "component_assignments": document.get("component_assignments", []),
        "resolved_edges": document.get("resolved_edges", []),
    }
    tuple_value = "|".join(
        (
            str(document.get("calculation_run_id", "")),
            str(document.get("architecture_profile_ref", {}).get("digest", "")),
            str(
                document.get("optimization_bundle_ref", {}).get(
                    "compatibility_digest", ""
                )
            ),
            canonical_json(assignment_payload),
        )
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, tuple_value))


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(nested) for key, nested in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(nested) for nested in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [_thaw(nested) for nested in value]
    return copy.deepcopy(value)


@dataclass(frozen=True)
class ValidatedContract:
    schema_version: str
    stable_id: str
    version: str
    content_digest: str
    document: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        value = _thaw(self.document)
        if not isinstance(value, dict):
            raise RuntimeError("Validated architecture contract must be an object")
        return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read contract JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain an object")
    return value


def _load_schemas(bundle_root: Path) -> tuple[dict[str, dict[str, Any]], Registry]:
    schemas = {
        version: _read_json(bundle_root / filename)
        for version, filename in SCHEMA_FILES.items()
    }
    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()]
    )
    return schemas, registry


def _check_limits(value: object, path: str = "$", depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        _fail("ARCH_SCHEMA_INVALID", path, "Maximum document depth exceeded")
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _check_limits(nested, f"{path}.{key}", depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_ARRAY_ITEMS:
            _fail("ARCH_SCHEMA_INVALID", path, "Maximum array length exceeded")
        for index, nested in enumerate(value):
            _check_limits(nested, f"{path}[{index}]", depth + 1)


def _check_secrets(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in SECRET_KEY_FRAGMENTS):
                _fail(
                    "ARCH_SECRET_FIELD_FORBIDDEN",
                    f"{path}.{key}",
                    "Secret-like field name is forbidden",
                )
            _check_secrets(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _check_secrets(nested, f"{path}[{index}]")
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
            _fail(
                "ARCH_SECRET_FIELD_FORBIDDEN",
                path,
                "Credential-shaped value is forbidden",
            )


def _check_decimal_canonical(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _check_decimal_canonical(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _check_decimal_canonical(nested, f"{path}[{index}]")
    elif (
        isinstance(value, str)
        and DECIMAL_PATTERN.fullmatch(value)
        and _normalize_decimal(value) != value
    ):
        _fail(
            "ARCH_SCHEMA_INVALID",
            path,
            "Decimal string is not in canonical form",
        )


def _check_duplicate_ids(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(nested, list):
                for identity_field in ARRAY_IDENTITY_FIELDS.get(str(key), ()):
                    identifiers = [
                        item.get(identity_field)
                        for item in nested
                        if isinstance(item, Mapping)
                        and isinstance(item.get(identity_field), str)
                    ]
                    if len(identifiers) != len(set(identifiers)):
                        _fail(
                            "ARCH_DUPLICATE_ID",
                            f"{path}.{key}",
                            f"Duplicate {identity_field}",
                        )
            _check_duplicate_ids(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _check_duplicate_ids(nested, f"{path}[{index}]")


def _validate_schema(
    document: Mapping[str, Any],
    schema: dict[str, Any],
    registry: Registry,
) -> None:
    validator = Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        _fail(
            "ARCH_SCHEMA_INVALID",
            location,
            f"Schema validation failed for rule {error.validator}",
        )


def _by_id(
    items: Iterable[Mapping[str, Any]], field: str
) -> dict[str, Mapping[str, Any]]:
    return {str(item[field]): item for item in items}


def _require_refs(
    values: Iterable[str],
    available: set[str],
    path: str,
) -> None:
    for value in values:
        if value not in available:
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                path,
                f"Unknown reference {value}",
            )


def _check_profile(document: Mapping[str, Any], registry: Mapping[str, Any]) -> None:
    responsibilities = _by_id(document["responsibilities"], "responsibility_id")
    components = _by_id(document["components"], "component_id")
    slots = _by_id(document["extension_slots"], "slot_id")
    port_contracts = {item["port_id"] for item in registry["port_contracts"]}
    for index, responsibility in enumerate(document["responsibilities"]):
        _require_refs(
            responsibility["logical_component_ids"],
            set(components),
            f"responsibilities[{index}].logical_component_ids",
        )
        expected_components = {
            component_id
            for component_id, component in components.items()
            if component["responsibility_id"] == responsibility["responsibility_id"]
        }
        if set(responsibility["logical_component_ids"]) != expected_components:
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"responsibilities[{index}].logical_component_ids",
                "Responsibility component ownership is not bidirectionally exact",
            )
    evaluation_orders = [
        item["evaluation_order"] for item in document["responsibilities"]
    ]
    if len(evaluation_orders) != len(set(evaluation_orders)):
        _fail(
            "ARCH_DUPLICATE_ID",
            "responsibilities",
            "Responsibility evaluation order must be unique",
        )
    for index, component in enumerate(document["components"]):
        if component["responsibility_id"] not in responsibilities:
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"components[{index}].responsibility_id",
                "Unknown responsibility",
            )
        _require_refs(
            component["input_port_ids"],
            port_contracts,
            f"components[{index}].input_port_ids",
        )
        _require_refs(
            component["output_port_ids"],
            port_contracts,
            f"components[{index}].output_port_ids",
        )
        _require_refs(
            component["extension_slot_ids"],
            set(slots),
            f"components[{index}].extension_slot_ids",
        )
    adjacency: dict[str, set[str]] = {
        component_id: set() for component_id in components
    }
    for index, edge in enumerate(document["edges"]):
        source = edge["source_component_id"]
        destination = edge["destination_component_id"]
        if source not in components or destination not in components:
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"edges[{index}]",
                "Edge references an unknown component",
            )
        if edge["source_port_id"] not in components[source]["output_port_ids"]:
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"edges[{index}].source_port_id",
                "Edge source port is not owned by its component",
            )
        if edge["destination_port_id"] not in components[destination]["input_port_ids"]:
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"edges[{index}].destination_port_id",
                "Edge destination port is not owned by its component",
            )
        adjacency[source].add(destination)

    next_index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    strongly_connected: list[set[str]] = []

    def visit(component_id: str) -> None:
        nonlocal next_index
        indexes[component_id] = next_index
        lowlinks[component_id] = next_index
        next_index += 1
        stack.append(component_id)
        on_stack.add(component_id)
        for target in sorted(adjacency[component_id]):
            if target not in indexes:
                visit(target)
                lowlinks[component_id] = min(
                    lowlinks[component_id],
                    lowlinks[target],
                )
            elif target in on_stack:
                lowlinks[component_id] = min(
                    lowlinks[component_id],
                    indexes[target],
                )
        if lowlinks[component_id] == indexes[component_id]:
            connected: set[str] = set()
            while stack:
                member = stack.pop()
                on_stack.remove(member)
                connected.add(member)
                if member == component_id:
                    break
            strongly_connected.append(connected)

    for component_id in sorted(components):
        if component_id not in indexes:
            visit(component_id)
    cyclic_components = [
        connected
        for connected in strongly_connected
        if len(connected) > 1
        or any(member in adjacency[member] for member in connected)
    ]
    expected_cycle_ids = {
        "cycle."
        + ".".join(sorted(member.removeprefix("component.") for member in connected))
        for connected in cyclic_components
    }
    graph_policy = document["graph_policy"]
    if cyclic_components and graph_policy["cycle_policy"] == "acyclic":
        _fail(
            "ARCH_GRAPH_CYCLE_FORBIDDEN",
            "graph_policy.cycle_policy",
            "Profile graph contains a forbidden cycle",
        )
    if (
        graph_policy["cycle_policy"] == "allowlisted"
        and set(graph_policy["allowed_cycle_ids"]) != expected_cycle_ids
    ):
        _fail(
            "ARCH_GRAPH_CYCLE_FORBIDDEN",
            "graph_policy.allowed_cycle_ids",
            "Allowlisted cycle IDs do not exactly cover strongly connected components",
        )
    registered_cycles = {item["cycle_id"] for item in registry["cycle_contracts"]}
    _require_refs(
        graph_policy["allowed_cycle_ids"],
        registered_cycles,
        "graph_policy.allowed_cycle_ids",
    )

    bundle = document["optimization_bundle"]
    workload_ref = document["workload_contract_ref"]
    if (
        bundle["workload_contract_id"] != workload_ref["id"]
        or bundle["workload_contract_version"] != workload_ref["version"]
    ):
        _fail(
            "ARCH_BUNDLE_INCOMPATIBLE",
            "workload_contract_ref",
            "Top-level workload contract differs from the optimization bundle",
        )
    compatible_bundles = registry["compatible_optimization_bundles"]
    match = next(
        (
            candidate
            for candidate in compatible_bundles
            if candidate["optimization_strategy_id"]
            == bundle["optimization_strategy_id"]
            and candidate["optimization_strategy_version"]
            == bundle["optimization_strategy_version"]
        ),
        None,
    )
    coupled_fields = (
        "calculation_strategy_id",
        "calculation_strategy_version",
        "formula_set_id",
        "formula_set_version",
        "scoring_strategy_id",
        "scoring_strategy_version",
        "pricing_registry_id",
        "pricing_registry_versions",
        "workload_contract_id",
        "workload_contract_version",
        "deployment_specification_versions",
        "compatibility_digest",
    )
    if match is None or any(match[field] != bundle[field] for field in coupled_fields):
        _fail(
            "ARCH_BUNDLE_INCOMPATIBLE",
            "optimization_bundle",
            "Optimization, calculation, formula, workload, pricing, and deployment versions are not a registered compatible bundle",
        )


def _check_semantic_registry(document: Mapping[str, Any]) -> None:
    expected_errors = {
        "ARCH_SCHEMA_INVALID",
        "ARCH_VERSION_UNSUPPORTED",
        "ARCH_DIGEST_MISMATCH",
        "ARCH_DUPLICATE_ID",
        "ARCH_REFERENCE_UNRESOLVED",
        "ARCH_GRAPH_CYCLE_FORBIDDEN",
        "ARCH_CAPABILITY_INCOMPLETE",
        "ARCH_BUNDLE_INCOMPATIBLE",
        "ARCH_COMPONENT_UNAVAILABLE",
        "ARCH_EDGE_UNAVAILABLE",
        "ARCH_DEPLOYMENT_SPEC_INCOMPATIBLE",
        "ARCH_EXTENSION_BINDING_INVALID",
        "ARCH_SECRET_FIELD_FORBIDDEN",
    }
    if set(document["known_error_codes"]) != expected_errors:
        _fail(
            "ARCH_SCHEMA_INVALID",
            "known_error_codes",
            "Semantic registry does not expose the complete stable error contract",
        )
    expected_limits = {
        "max_document_bytes": MAX_DOCUMENT_BYTES,
        "max_depth": MAX_DEPTH,
        "max_array_items": MAX_ARRAY_ITEMS,
        "max_errors": MAX_ERRORS,
    }
    if document["limits"] != expected_limits:
        _fail(
            "ARCH_SCHEMA_INVALID",
            "limits",
            "Semantic registry limits differ from the executable validator",
        )
    ownership = {
        (item["contract_kind"], item["field_path"]): (
            item["author"],
            item["mutability"],
        )
        for item in document["field_ownership"]
    }
    if len(ownership) != len(document["field_ownership"]):
        _fail(
            "ARCH_DUPLICATE_ID",
            "field_ownership",
            "Field ownership contains a duplicate contract path",
        )
    expected_definition_owners = {
        ("architecture-profile.v2", "/"),
        ("provider-implementation-profile.v2", "/"),
        ("deployment-component-catalog.v2", "/"),
    }
    if not expected_definition_owners.issubset(ownership):
        _fail(
            "ARCH_SCHEMA_INVALID",
            "field_ownership",
            "Repository definition ownership is incomplete",
        )
    if ownership.get(("resolved-twin-architecture.v2", "/calculation_run_id")) != (
        "management_api_input",
        "immutable_input",
    ):
        _fail(
            "ARCH_SCHEMA_INVALID",
            "field_ownership",
            "Calculation run ownership is not Management API input",
        )
    required_resolution_fields = {
        "schema_version",
        "resolution_id",
        "resolution_status",
        "architecture_profile_ref",
        "optimization_bundle_ref",
        "provider_profile_refs",
        "workload_contract_ref",
        "pricing_evidence_refs",
        "component_assignments",
        "resolved_edges",
        "extension_bindings",
        "deployment_specification_ref",
        "cost_summary",
        "functional_completeness",
        "content_digest",
    }
    optimizer_owned = {
        field_path.removeprefix("/")
        for (contract_kind, field_path), owner in ownership.items()
        if contract_kind == "resolved-twin-architecture.v2"
        and owner == ("optimizer_derived", "immutable_derived")
    }
    if optimizer_owned != required_resolution_fields:
        _fail(
            "ARCH_SCHEMA_INVALID",
            "field_ownership",
            "Optimizer-derived resolution field ownership is incomplete",
        )
    bundle_identities = {
        (
            item["optimization_strategy_id"],
            item["optimization_strategy_version"],
        )
        for item in document["compatible_optimization_bundles"]
    }
    if len(bundle_identities) != len(document["compatible_optimization_bundles"]):
        _fail(
            "ARCH_DUPLICATE_ID",
            "compatible_optimization_bundles",
            "Optimization bundle identity is duplicated",
        )
    deployment_versions = [
        item["schema_version"]
        for item in document["deployment_specification_compatibility"]
    ]
    if len(deployment_versions) != len(set(deployment_versions)):
        _fail(
            "ARCH_DUPLICATE_ID",
            "deployment_specification_compatibility",
            "Deployment specification compatibility is duplicated",
        )
    for index, bundle in enumerate(document["compatible_optimization_bundles"]):
        digest_input = dict(bundle)
        supplied = digest_input.pop("compatibility_digest")
        encoded = canonical_json(digest_input).encode("utf-8")
        expected = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
        if supplied != expected:
            _fail(
                "ARCH_BUNDLE_INCOMPATIBLE",
                f"compatible_optimization_bundles[{index}].compatibility_digest",
                "Optimization bundle compatibility digest is invalid",
            )


def _linked_by_version(
    linked_documents: Iterable[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = {}
    for document in linked_documents:
        result.setdefault(str(document.get("schema_version")), []).append(document)
    return result


def _check_provider_profile(
    document: Mapping[str, Any],
    linked: dict[str, list[Mapping[str, Any]]],
) -> None:
    profiles = linked.get("architecture-profile.v2", [])
    matching_profile = next(
        (
            profile
            for profile in profiles
            if profile["profile_id"] == document["architecture_profile_ref"]["id"]
            and profile["profile_version"]
            == document["architecture_profile_ref"]["version"]
        ),
        None,
    )
    if matching_profile is None:
        return
    if (
        document["lifecycle_status"] == "active"
        and matching_profile["lifecycle_status"] != "active"
    ):
        _fail(
            "ARCH_VERSION_UNSUPPORTED",
            "architecture_profile_ref",
            "Active provider profile must reference an active architecture profile",
        )
    if (
        matching_profile["content_digest"]
        != document["architecture_profile_ref"]["digest"]
    ):
        _fail(
            "ARCH_DIGEST_MISMATCH",
            "architecture_profile_ref.digest",
            "Architecture profile reference digest differs from linked profile",
        )
    component_ids = {item["component_id"] for item in matching_profile["components"]}
    edge_ids = {item["edge_id"] for item in matching_profile["edges"]}
    mapped_components = {
        item["component_id"] for item in document["component_mappings"]
    }
    mapped_edges = {item["edge_id"] for item in document["edge_mappings"]}
    if document["supported"] and component_ids != mapped_components:
        _fail(
            "ARCH_COMPONENT_UNAVAILABLE",
            "component_mappings",
            "Provider mappings do not cover every logical component",
        )
    if not mapped_components.issubset(component_ids):
        _fail(
            "ARCH_REFERENCE_UNRESOLVED",
            "component_mappings",
            "Provider mappings contain an unknown logical component",
        )
    if document["supported"] and edge_ids != mapped_edges:
        _fail(
            "ARCH_EDGE_UNAVAILABLE",
            "edge_mappings",
            "Provider mappings do not cover every logical edge",
        )
    if not mapped_edges.issubset(edge_ids):
        _fail(
            "ARCH_REFERENCE_UNRESOLVED",
            "edge_mappings",
            "Provider mappings contain an unknown logical edge",
        )
    required_capabilities = {
        capability
        for component in matching_profile["components"]
        for capability in component["required_capability_ids"]
    }
    provided = set(document["capability_claims"]["provided_capability_ids"])
    missing = sorted(required_capabilities - provided)
    declared_missing = sorted(document["capability_claims"]["missing_capability_ids"])
    if missing != declared_missing:
        _fail(
            "ARCH_CAPABILITY_INCOMPLETE",
            "capability_claims",
            "Declared missing capabilities differ from mapped evidence",
        )
    if document["supported"] and (missing or document["unsupported_reasons"]):
        _fail(
            "ARCH_CAPABILITY_INCOMPLETE",
            "capability_claims",
            "Supported provider profile is not functionally complete",
        )
    if not document["supported"] and not document["unsupported_reasons"]:
        _fail(
            "ARCH_CAPABILITY_INCOMPLETE",
            "unsupported_reasons",
            "Unsupported provider profile requires a stable reason",
        )
    component_by_id = _by_id(matching_profile["components"], "component_id")
    for index, mapping in enumerate(document["component_mappings"]):
        required = set(
            component_by_id[mapping["component_id"]]["required_capability_ids"]
        )
        if set(mapping["required_capability_ids"]) != required or not required.issubset(
            set(mapping["provided_capability_ids"])
        ):
            _fail(
                "ARCH_CAPABILITY_INCOMPLETE",
                f"component_mappings[{index}]",
                "Component mapping capability coverage differs from the logical profile",
            )

    catalogs = linked.get("deployment-component-catalog.v2", [])
    if not catalogs:
        return
    compatible_catalog_refs = {
        (item["id"], item["version"])
        for item in document["compatibility"]["compatible_catalog_versions"]
    }
    catalog = next(
        (
            candidate
            for candidate in catalogs
            if (candidate["catalog_id"], candidate["catalog_version"])
            in compatible_catalog_refs
        ),
        None,
    )
    if catalog is None:
        _fail(
            "ARCH_COMPONENT_UNAVAILABLE",
            "compatibility.compatible_catalog_versions",
            "No linked compatible deployment component catalog",
        )
    if (
        document["lifecycle_status"] == "active"
        and catalog["lifecycle_status"] != "active"
    ):
        _fail(
            "ARCH_VERSION_UNSUPPORTED",
            "compatibility.compatible_catalog_versions",
            "Active provider profile must reference an active catalog",
        )
    catalog_components = _by_id(catalog["components"], "deployment_component_id")
    catalog_edges = _by_id(catalog["edge_implementations"], "edge_implementation_id")
    for index, mapping in enumerate(document["component_mappings"]):
        candidates = mapping["deployment_component_candidates"]
        for candidate_id in candidates:
            candidate = catalog_components.get(candidate_id)
            if candidate is None or candidate["provider"] != document["provider"]:
                _fail(
                    "ARCH_COMPONENT_UNAVAILABLE",
                    f"component_mappings[{index}].deployment_component_candidates",
                    "Provider mapping references an unavailable catalog component",
                )
        deployment_component_ids = {
            binding["component_id"]
            for candidate_id in candidates
            for binding in catalog_components[candidate_id][
                "deployment_specification_bindings"
            ]
        }
        if deployment_component_ids != set(
            mapping["deployment_specification_component_ids"]
        ):
            _fail(
                "ARCH_DEPLOYMENT_SPEC_INCOMPATIBLE",
                f"component_mappings[{index}].deployment_specification_component_ids",
                "Provider mapping and catalog deployment bindings differ",
            )
    for index, mapping in enumerate(document["edge_mappings"]):
        edge = catalog_edges.get(mapping["edge_implementation_id"])
        if edge is None or edge["provider"] != document["provider"]:
            _fail(
                "ARCH_EDGE_UNAVAILABLE",
                f"edge_mappings[{index}].edge_implementation_id",
                "Provider mapping references an unavailable edge implementation",
            )
        if (
            edge["source_output_port_id"] != mapping["catalog_output_port_id"]
            or edge["destination_input_port_id"] != mapping["catalog_input_port_id"]
            or edge["mechanism"] != mapping["mechanism"]
        ):
            _fail(
                "ARCH_EDGE_UNAVAILABLE",
                f"edge_mappings[{index}]",
                "Provider edge mapping differs from its catalog implementation",
            )


def _check_catalog(
    document: Mapping[str, Any],
    linked: dict[str, list[Mapping[str, Any]]],
) -> None:
    artifacts = {
        (item["artifact_id"], item["artifact_version"])
        for item in document["package_artifacts"]
    }
    for index, artifact in enumerate(document["package_artifacts"]):
        for reference in artifact["dependency_artifact_refs"]:
            if (reference["id"], reference["version"]) not in artifacts:
                _fail(
                    "ARCH_REFERENCE_UNRESOLVED",
                    f"package_artifacts[{index}].dependency_artifact_refs",
                    "Unknown package artifact dependency",
                )
    for index, component in enumerate(document["components"]):
        reference = component["package_artifact_ref"]
        if (reference["id"], reference["version"]) not in artifacts:
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"components[{index}].package_artifact_ref",
                "Unknown package artifact",
            )
        input_ports = {item["port_id"] for item in component["input_ports"]}
        output_ports = {item["port_id"] for item in component["output_ports"]}
        if input_ports & output_ports:
            _fail(
                "ARCH_DUPLICATE_ID",
                f"components[{index}]",
                "Component input and output port IDs overlap",
            )
        runtime_contract = component["runtime_contract"]
        if (
            runtime_contract["timeout_seconds_min"]
            > runtime_contract["timeout_seconds_max"]
            or runtime_contract["memory_mb_min"] > runtime_contract["memory_mb_max"]
        ):
            _fail(
                "ARCH_COMPONENT_UNAVAILABLE",
                f"components[{index}].runtime_contract",
                "Runtime minimum exceeds maximum",
            )
    profiles = linked.get("architecture-profile.v2", [])
    if not profiles:
        return
    linked_profile_refs = {
        (profile["profile_id"], profile["profile_version"]) for profile in profiles
    }
    catalog_profile_refs = {
        (reference["id"], reference["version"])
        for item in (*document["components"], *document["edge_implementations"])
        for reference in item["compatibility"]["architecture_profile_versions"]
    }
    if catalog_profile_refs.isdisjoint(linked_profile_refs):
        return
    logical_component_ids = {
        item["component_id"] for profile in profiles for item in profile["components"]
    }
    logical_edge_ids = {
        item["edge_id"] for profile in profiles for item in profile["edges"]
    }
    logical_edges = {
        item["edge_id"]: item for profile in profiles for item in profile["edges"]
    }
    deployment_component_ids = {
        item["deployment_component_id"] for item in document["components"]
    }
    extension_slots = {
        item["slot_id"]: item
        for profile in profiles
        for item in profile["extension_slots"]
    }
    for index, component in enumerate(document["components"]):
        _require_refs(
            component["logical_component_ids"],
            logical_component_ids,
            f"components[{index}].logical_component_ids",
        )
        for slot_ref in component["extension_slot_refs"]:
            slot = extension_slots.get(slot_ref["id"])
            if (
                slot is None
                or slot["slot_version"] != slot_ref["version"]
                or slot["component_id"] not in component["logical_component_ids"]
            ):
                _fail(
                    "ARCH_REFERENCE_UNRESOLVED",
                    f"components[{index}].extension_slot_refs",
                    "Catalog extension slot is not owned by a mapped logical component",
                )
    for index, edge in enumerate(document["edge_implementations"]):
        _require_refs(
            edge["logical_edge_ids"],
            logical_edge_ids,
            f"edge_implementations[{index}].logical_edge_ids",
        )
        for logical_edge_id in edge["logical_edge_ids"]:
            logical_edge = logical_edges[logical_edge_id]
            payload_ref = edge["payload_contract_ref"]
            if (
                payload_ref["id"] != logical_edge["edge_contract_id"]
                or payload_ref["version"] != logical_edge["edge_contract_version"]
                or canonical_json(edge["delivery_requirements"])
                != canonical_json(logical_edge["delivery_requirements"])
            ):
                _fail(
                    "ARCH_EDGE_UNAVAILABLE",
                    f"edge_implementations[{index}]",
                    "Catalog edge payload or delivery contract differs",
                )
        _require_refs(
            edge["glue_component_ids"],
            deployment_component_ids,
            f"edge_implementations[{index}].glue_component_ids",
        )


def _check_resolved(
    document: Mapping[str, Any],
    linked: dict[str, list[Mapping[str, Any]]],
    registry: Mapping[str, Any],
) -> None:
    if document["resolution_id"] != calculate_resolution_id(document):
        _fail(
            "ARCH_DIGEST_MISMATCH",
            "resolution_id",
            "Resolution UUIDv5 does not match canonical frozen inputs",
        )
    profiles = linked.get("architecture-profile.v2", [])
    profile_ref = document["architecture_profile_ref"]
    profile = next(
        (
            candidate
            for candidate in profiles
            if candidate["profile_id"] == profile_ref["id"]
            and candidate["profile_version"] == profile_ref["version"]
        ),
        None,
    )
    if profile is None:
        return
    if (
        document["resolution_status"] == "publishable"
        and profile["lifecycle_status"] != "active"
    ):
        _fail(
            "ARCH_VERSION_UNSUPPORTED",
            "architecture_profile_ref",
            "Publishable resolution must reference an active architecture profile",
        )
    if profile["content_digest"] != profile_ref["digest"]:
        _fail(
            "ARCH_DIGEST_MISMATCH",
            "architecture_profile_ref.digest",
            "Linked architecture profile digest differs",
        )
    resolution_bundle = document["optimization_bundle_ref"]
    expected_bundle = {
        field: profile["optimization_bundle"][field]
        for field in (
            "optimization_strategy_id",
            "optimization_strategy_version",
            "calculation_strategy_id",
            "calculation_strategy_version",
            "formula_set_id",
            "formula_set_version",
            "scoring_strategy_id",
            "scoring_strategy_version",
            "compatibility_digest",
        )
    }
    if resolution_bundle != expected_bundle:
        _fail(
            "ARCH_BUNDLE_INCOMPATIBLE",
            "optimization_bundle_ref",
            "Resolution optimization bundle differs from the linked profile",
        )
    provider_profiles = {
        (candidate["implementation_profile_id"], candidate["provider"]): candidate
        for candidate in linked.get("provider-implementation-profile.v2", [])
    }
    top_provider_refs = {
        (reference["id"], reference["provider"]): reference
        for reference in document["provider_profile_refs"]
    }
    catalogs = linked.get("deployment-component-catalog.v2", [])
    referenced_provider_profiles = [
        provider_profiles[key] for key in top_provider_refs if key in provider_profiles
    ]
    compatible_catalog_sets = [
        {
            (reference["id"], reference["version"])
            for reference in provider_profile["compatibility"][
                "compatible_catalog_versions"
            ]
        }
        for provider_profile in referenced_provider_profiles
    ]
    common_catalog_refs = (
        set.intersection(*compatible_catalog_sets) if compatible_catalog_sets else set()
    )
    matching_catalogs = [
        candidate
        for candidate in catalogs
        if (candidate["catalog_id"], candidate["catalog_version"])
        in common_catalog_refs
    ]
    if catalogs and len(matching_catalogs) != 1:
        _fail(
            "ARCH_COMPONENT_UNAVAILABLE",
            "component_assignments",
            "Resolution does not have exactly one commonly compatible linked catalog",
        )
    catalog = matching_catalogs[0] if matching_catalogs else None
    if (
        document["resolution_status"] == "publishable"
        and catalog is not None
        and catalog["lifecycle_status"] != "active"
    ):
        _fail(
            "ARCH_VERSION_UNSUPPORTED",
            "component_assignments",
            "Publishable resolution must reference an active component catalog",
        )
    catalog_components = (
        _by_id(catalog["components"], "deployment_component_id")
        if catalog is not None
        else {}
    )
    catalog_edges = (
        _by_id(catalog["edge_implementations"], "edge_implementation_id")
        if catalog is not None
        else {}
    )
    assignments = _by_id(document["component_assignments"], "assignment_id")
    by_component = {
        assignment["logical_component_id"]: assignment
        for assignment in document["component_assignments"]
    }
    storage_bundle = [
        by_component.get(component_id)
        for component_id in (
            "component.hot-storage",
            "component.cool-storage",
            "component.archive-storage",
            "component.visualization",
        )
    ]
    if all(storage_bundle) and len(
        {assignment["provider"] for assignment in storage_bundle}
    ) != 1:
        _fail(
            "ARCH_BUNDLE_INCOMPATIBLE",
            "component_assignments",
            "Six-layer PoC requires provider-local L3 storage and L5",
        )
    expected_components = {item["component_id"] for item in profile["components"]}
    if set(by_component) != expected_components:
        _fail(
            "ARCH_COMPONENT_UNAVAILABLE",
            "component_assignments",
            "Resolution does not assign every required logical component exactly once",
        )
    profile_components = _by_id(profile["components"], "component_id")
    used_provider_refs: set[tuple[str, str]] = set()
    for index, assignment in enumerate(document["component_assignments"]):
        logical = profile_components[assignment["logical_component_id"]]
        if assignment["responsibility_id"] != logical["responsibility_id"]:
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"component_assignments[{index}].responsibility_id",
                "Assignment responsibility differs from the logical component",
            )
        implementation_ref = assignment["provider_implementation_profile_ref"]
        provider_key = (implementation_ref["id"], assignment["provider"])
        used_provider_refs.add(provider_key)
        provider_profile = provider_profiles.get(provider_key)
        top_ref = top_provider_refs.get(provider_key)
        if (
            provider_profile is None
            or top_ref is None
            or provider_profile["implementation_profile_version"]
            != implementation_ref["version"]
            or provider_profile["content_digest"] != implementation_ref["digest"]
            or top_ref["digest"] != implementation_ref["digest"]
        ):
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"component_assignments[{index}].provider_implementation_profile_ref",
                "Assignment provider profile is not pinned by the resolution",
            )
        if not provider_profile["supported"] or (
            document["resolution_status"] == "publishable"
            and provider_profile["lifecycle_status"] != "active"
        ):
            _fail(
                "ARCH_CAPABILITY_INCOMPLETE",
                f"component_assignments[{index}].provider_implementation_profile_ref",
                "Publishable resolution uses an inactive or unsupported provider profile",
            )
        if not set(logical["required_capability_ids"]).issubset(
            set(assignment["capability_evidence"])
        ):
            _fail(
                "ARCH_CAPABILITY_INCOMPLETE",
                f"component_assignments[{index}].capability_evidence",
                "Assignment lacks logical capability evidence",
            )
        if catalog is not None:
            catalog_component = catalog_components.get(
                assignment["deployment_component_id"]
            )
            if (
                catalog_component is None
                or catalog_component["component_version"]
                != assignment["deployment_component_version"]
                or catalog_component["provider"] != assignment["provider"]
                or catalog_component["service_id"] != assignment["service_id"]
                or assignment["logical_component_id"]
                not in catalog_component["logical_component_ids"]
            ):
                _fail(
                    "ARCH_COMPONENT_UNAVAILABLE",
                    f"component_assignments[{index}].deployment_component_id",
                    "Assignment differs from its catalog component",
                )
            catalog_spec_components = {
                binding["component_id"]
                for binding in catalog_component["deployment_specification_bindings"]
            }
            selected_spec_components = set(
                assignment["deployment_specification_component_ids"]
            )
            if not selected_spec_components.issubset(catalog_spec_components):
                _fail(
                    "ARCH_DEPLOYMENT_SPEC_INCOMPATIBLE",
                    (
                        f"component_assignments[{index}]."
                        "deployment_specification_component_ids"
                    ),
                    "Assignment deployment components are not catalog bindings",
                )
    if used_provider_refs != set(top_provider_refs):
        _fail(
            "ARCH_REFERENCE_UNRESOLVED",
            "provider_profile_refs",
            "Resolution provider profile refs do not exactly match assignments",
        )
    resolved_by_edge = {edge["edge_id"]: edge for edge in document["resolved_edges"]}
    expected_edges = {item["edge_id"] for item in profile["edges"]}
    if set(resolved_by_edge) != expected_edges:
        _fail(
            "ARCH_EDGE_UNAVAILABLE",
            "resolved_edges",
            "Resolution does not implement every required logical edge exactly once",
        )
    for index, edge in enumerate(document["resolved_edges"]):
        if (
            edge["source_assignment_id"] not in assignments
            or edge["destination_assignment_id"] not in assignments
        ):
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"resolved_edges[{index}]",
                "Resolved edge references an unknown assignment",
            )
        logical_edge = next(
            item for item in profile["edges"] if item["edge_id"] == edge["edge_id"]
        )
        source_assignment = assignments[edge["source_assignment_id"]]
        destination_assignment = assignments[edge["destination_assignment_id"]]
        if (
            source_assignment["logical_component_id"]
            != logical_edge["source_component_id"]
            or destination_assignment["logical_component_id"]
            != logical_edge["destination_component_id"]
        ):
            _fail(
                "ARCH_REFERENCE_UNRESOLVED",
                f"resolved_edges[{index}]",
                "Resolved edge assignments differ from the logical edge",
            )
        if catalog is not None:
            catalog_edge = catalog_edges.get(edge["edge_implementation_id"])
            if (
                catalog_edge is None
                or edge["mechanism"] != catalog_edge["mechanism"]
                or edge["source_port_id"] != catalog_edge["source_output_port_id"]
                or edge["destination_port_id"]
                != catalog_edge["destination_input_port_id"]
                or source_assignment["deployment_component_id"]
                not in catalog_edge["source_component_ids"]
                or destination_assignment["deployment_component_id"]
                not in catalog_edge["destination_component_ids"]
            ):
                _fail(
                    "ARCH_EDGE_UNAVAILABLE",
                    f"resolved_edges[{index}].edge_implementation_id",
                    "Resolved edge differs from its catalog implementation",
                )
    required = set(document["functional_completeness"]["required_capability_ids"])
    provided = set(document["functional_completeness"]["provided_capability_ids"])
    if document["functional_completeness"][
        "missing_capability_ids"
    ] or not required.issubset(provided):
        _fail(
            "ARCH_CAPABILITY_INCOMPLETE",
            "functional_completeness",
            "Publishable resolution has missing required capabilities",
        )
    expected_capabilities = {
        capability
        for component in profile["components"]
        for capability in component["required_capability_ids"]
    }
    if required != expected_capabilities or provided != expected_capabilities:
        _fail(
            "ARCH_CAPABILITY_INCOMPLETE",
            "functional_completeness",
            "Completeness capabilities differ from the logical profile",
        )
    expected_slots = {item["slot_id"] for item in profile["extension_slots"]}
    actual_slots = {item["slot_id"] for item in document["extension_bindings"]}
    if expected_slots != actual_slots:
        _fail(
            "ARCH_EXTENSION_BINDING_INVALID",
            "extension_bindings",
            "Extension bindings do not cover the profile slots exactly",
        )
    slots_by_id = _by_id(profile["extension_slots"], "slot_id")
    assignment_by_component = {
        item["logical_component_id"]: item for item in document["component_assignments"]
    }
    for index, binding in enumerate(document["extension_bindings"]):
        slot = slots_by_id[binding["slot_id"]]
        if (
            binding["slot_version"] != slot["slot_version"]
            or binding["logical_component_id"] != slot["component_id"]
            or binding["validation_contract_version"]
            != slot["configuration_contract_ref"]["version"]
        ):
            _fail(
                "ARCH_EXTENSION_BINDING_INVALID",
                f"extension_bindings[{index}]",
                "Extension binding differs from the logical slot contract",
            )
        assignment = assignment_by_component.get(binding["logical_component_id"])
        if assignment is None:
            _fail(
                "ARCH_EXTENSION_BINDING_INVALID",
                f"extension_bindings[{index}].logical_component_id",
                "Extension binding has no resolved component assignment",
            )
        if catalog is not None:
            catalog_component = catalog_components[
                assignment["deployment_component_id"]
            ]
            allowed_slot_refs = {
                (reference["id"], reference["version"])
                for reference in catalog_component["extension_slot_refs"]
            }
            if (binding["slot_id"], binding["slot_version"]) not in allowed_slot_refs:
                _fail(
                    "ARCH_EXTENSION_BINDING_INVALID",
                    f"extension_bindings[{index}]",
                    "Selected deployment component does not allow the extension slot",
                )
    deployment_ref = document["deployment_specification_ref"]
    compatibility = next(
        (
            item
            for item in registry["deployment_specification_compatibility"]
            if item["schema_version"] == deployment_ref["schema_version"]
        ),
        None,
    )
    if (
        compatibility is None
        or profile_ref["id"] not in compatibility["architecture_profile_ids"]
        or profile_ref["version"] not in compatibility["architecture_profile_versions"]
    ):
        _fail(
            "ARCH_DEPLOYMENT_SPEC_INCOMPATIBLE",
            "deployment_specification_ref",
            "Deployment specification is incompatible with the profile",
        )
    if deployment_ref["calculation_run_id"] != document["calculation_run_id"]:
        _fail(
            "ARCH_DEPLOYMENT_SPEC_INCOMPATIBLE",
            "deployment_specification_ref.calculation_run_id",
            "Deployment specification belongs to another calculation run",
        )
    component_amounts = {
        item["item_id"]: Decimal(item["monthly_amount"])
        for item in document["cost_summary"]["component_totals"]
    }
    edge_amounts = {
        item["item_id"]: Decimal(item["monthly_amount"])
        for item in document["cost_summary"]["edge_totals"]
    }
    responsibility_amounts = {
        item["item_id"]: Decimal(item["monthly_amount"])
        for item in document["cost_summary"]["responsibility_totals"]
    }
    if (
        set(component_amounts) != expected_components
        or set(edge_amounts) != expected_edges
    ):
        _fail(
            "ARCH_SCHEMA_INVALID",
            "cost_summary",
            "Cost summary does not cover all components and edges",
        )
    expected_responsibilities = {
        item["responsibility_id"] for item in profile["responsibilities"]
    }
    if set(responsibility_amounts) != expected_responsibilities:
        _fail(
            "ARCH_SCHEMA_INVALID",
            "cost_summary.responsibility_totals",
            "Cost summary does not cover all responsibilities",
        )
    assignment_costs = {
        item["logical_component_id"]: Decimal(
            item["cost_contribution"]["monthly_amount"]
        )
        for item in document["component_assignments"]
    }
    resolved_edge_costs = {
        item["edge_id"]: Decimal(item["cost_contribution"]["monthly_amount"])
        for item in document["resolved_edges"]
    }
    cost_currency = document["cost_summary"]["currency"]
    if any(
        item["cost_contribution"]["currency"] != cost_currency
        for item in (
            *document["component_assignments"],
            *document["resolved_edges"],
        )
    ):
        _fail(
            "ARCH_SCHEMA_INVALID",
            "cost_summary.currency",
            "Assignment and edge cost currencies must match the cost summary",
        )
    expected_responsibility_amounts = {
        responsibility_id: sum(
            (
                assignment_costs[component["component_id"]]
                for component in profile["components"]
                if component["responsibility_id"] == responsibility_id
            ),
            Decimal("0"),
        )
        for responsibility_id in expected_responsibilities
    }
    if (
        component_amounts != assignment_costs
        or edge_amounts != resolved_edge_costs
        or responsibility_amounts != expected_responsibility_amounts
    ):
        _fail(
            "ARCH_SCHEMA_INVALID",
            "cost_summary",
            "Cost summary differs from assignment or edge contributions",
        )
    expected_total = sum(component_amounts.values(), Decimal("0")) + sum(
        edge_amounts.values(), Decimal("0")
    )
    if Decimal(document["cost_summary"]["monthly_total"]) != expected_total:
        _fail(
            "ARCH_SCHEMA_INVALID",
            "cost_summary.monthly_total",
            "Monthly total differs from component and edge totals",
        )
    if catalog is not None:
        validation_payload = {
            "capabilities": sorted(expected_capabilities),
            "profile_digest": profile["content_digest"],
            "catalog_digest": catalog["content_digest"],
        }
        expected_validation_digest = f"sha256:{hashlib.sha256(canonical_json(validation_payload).encode('utf-8')).hexdigest()}"
        if (
            document["functional_completeness"]["validation_digest"]
            != expected_validation_digest
        ):
            _fail(
                "ARCH_DIGEST_MISMATCH",
                "functional_completeness.validation_digest",
                "Functional completeness digest differs from linked evidence",
            )


def validate_lifecycle_transition(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> None:
    """Reject backward lifecycle transitions for one exact definition version."""
    previous_schema = previous.get("schema_version")
    current_schema = current.get("schema_version")
    if previous_schema != current_schema or previous_schema not in {
        "architecture-profile.v2",
        "provider-implementation-profile.v2",
        "deployment-component-catalog.v2",
    }:
        _fail(
            "ARCH_VERSION_UNSUPPORTED",
            "schema_version",
            "Lifecycle transition requires the same supported contract kind",
        )
    previous_id, previous_version = _identity(previous)
    current_id, current_version = _identity(current)
    if (previous_id, previous_version) != (current_id, current_version):
        _fail(
            "ARCH_VERSION_UNSUPPORTED",
            "$",
            "Lifecycle transition cannot change identity or version",
        )
    allowed = {
        "draft": {"draft", "active", "retired"},
        "active": {"active", "deprecated", "retired"},
        "deprecated": {"deprecated", "retired"},
        "retired": {"retired"},
    }
    previous_status = str(previous["lifecycle_status"])
    current_status = str(current["lifecycle_status"])
    if current_status not in allowed.get(previous_status, set()):
        _fail(
            "ARCH_VERSION_UNSUPPORTED",
            "lifecycle_status",
            f"Lifecycle transition {previous_status} -> {current_status} is forbidden",
        )


def _identity(document: Mapping[str, Any]) -> tuple[str, str]:
    version = str(document["schema_version"])
    if version == "architecture-profile.v2":
        return str(document["profile_id"]), str(document["profile_version"])
    if version == "provider-implementation-profile.v2":
        return (
            str(document["implementation_profile_id"]),
            str(document["implementation_profile_version"]),
        )
    if version == "deployment-component-catalog.v2":
        return str(document["catalog_id"]), str(document["catalog_version"])
    if version == "resolved-twin-architecture.v2":
        return str(document["resolution_id"]), "1"
    return str(document["registry_id"]), str(document["registry_version"])


def _validate_document_impl(
    document: Mapping[str, Any],
    *,
    bundle_root: Path | None = None,
    linked_documents: Iterable[Mapping[str, Any]] = (),
) -> ValidatedContract:
    """Validate one contract and return an immutable typed view."""
    mutable = copy.deepcopy(dict(document))
    try:
        encoded = json.dumps(
            mutable,
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail(
            "ARCH_SCHEMA_INVALID",
            "$",
            f"Document is not finite JSON ({type(exc).__name__})",
        )
    if len(encoded) > MAX_DOCUMENT_BYTES:
        _fail("ARCH_SCHEMA_INVALID", "$", "Maximum document size exceeded")
    _check_limits(mutable)
    _check_secrets(mutable)
    _check_decimal_canonical(mutable)
    schema_version = mutable.get("schema_version")
    if schema_version not in SCHEMA_FILES:
        _fail(
            "ARCH_VERSION_UNSUPPORTED",
            "schema_version",
            "Unsupported schema version",
        )
    _check_duplicate_ids(mutable)
    root = bundle_root or Path(__file__).resolve().parent
    schemas, schema_registry = _load_schemas(root)
    _validate_schema(mutable, schemas[str(schema_version)], schema_registry)
    supplied_digest = mutable.get("content_digest")
    calculated_digest = calculate_digest(mutable)
    if supplied_digest != calculated_digest:
        _fail(
            "ARCH_DIGEST_MISMATCH",
            "content_digest",
            "Content digest does not match canonical contract content",
        )
    semantic_registry = _read_json(root / "semantic-registry.json")
    linked = _linked_by_version(linked_documents)
    if schema_version == "architecture-profile.v2":
        _check_profile(mutable, semantic_registry)
    elif schema_version == "provider-implementation-profile.v2":
        _check_provider_profile(mutable, linked)
    elif schema_version == "deployment-component-catalog.v2":
        _check_catalog(mutable, linked)
    elif schema_version == "resolved-twin-architecture.v2":
        _check_resolved(mutable, linked, semantic_registry)
    elif schema_version == "semantic-registry.v2":
        _check_semantic_registry(mutable)
    stable_id, version = _identity(mutable)
    return ValidatedContract(
        schema_version=str(schema_version),
        stable_id=stable_id,
        version=version,
        content_digest=calculated_digest,
        document=_freeze(mutable),
    )


def validation_log_record(
    document: Mapping[str, Any],
    *,
    result: str,
    error_code: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, str | None]:
    """Return bounded payload-free observability metadata."""
    schema_version = str(document.get("schema_version", "unknown"))[:80]
    identity_fields = {
        "architecture-profile.v2": ("profile_id", "profile_version"),
        "provider-implementation-profile.v2": (
            "implementation_profile_id",
            "implementation_profile_version",
        ),
        "deployment-component-catalog.v2": ("catalog_id", "catalog_version"),
        "resolved-twin-architecture.v2": ("resolution_id", None),
        "semantic-registry.v2": ("registry_id", "registry_version"),
    }
    identity_field, version_field = identity_fields.get(
        schema_version,
        (None, None),
    )
    candidate_id = (
        str(document.get(identity_field, "")) if identity_field is not None else ""
    )
    uuid_is_safe = False
    try:
        uuid.UUID(candidate_id)
    except (ValueError, AttributeError):
        pass
    else:
        uuid_is_safe = True
    stable_id = (
        candidate_id
        if len(candidate_id) <= 160
        and (STABLE_ID_PATTERN.fullmatch(candidate_id) or uuid_is_safe)
        else "invalid"
    )
    candidate_version = (
        str(document.get(version_field, "")) if version_field is not None else "1"
    )
    version = (
        candidate_version
        if len(candidate_version) <= 12 and VERSION_PATTERN.fullmatch(candidate_version)
        else "invalid"
    )
    digest = document.get("content_digest")
    safe_digest = (
        str(digest)
        if isinstance(digest, str) and DIGEST_PATTERN.fullmatch(digest)
        else None
    )
    return {
        "contract_kind": schema_version,
        "contract_id": stable_id,
        "contract_version": version,
        "content_digest": safe_digest,
        "result": result[:32],
        "error_code": error_code[:80] if error_code else None,
        "correlation_id": correlation_id[:120] if correlation_id else None,
    }


def validate_document(
    document: Mapping[str, Any],
    *,
    bundle_root: Path | None = None,
    linked_documents: Iterable[Mapping[str, Any]] = (),
    logger: Any | None = None,
    correlation_id: str | None = None,
) -> ValidatedContract:
    """Validate one document and optionally emit safe structured metadata."""
    try:
        validated = _validate_document_impl(
            document,
            bundle_root=bundle_root,
            linked_documents=linked_documents,
        )
    except ContractError as exc:
        if logger is not None:
            logger.info(
                "architecture_contract_validation",
                extra={
                    "architecture_contract": validation_log_record(
                        document,
                        result="rejected",
                        error_code=exc.code,
                        correlation_id=correlation_id,
                    )
                },
            )
        raise
    if logger is not None:
        logger.info(
            "architecture_contract_validation",
            extra={
                "architecture_contract": validation_log_record(
                    document,
                    result="accepted",
                    correlation_id=correlation_id,
                )
            },
        )
    return validated


def validate_bundle(
    documents: Iterable[Mapping[str, Any]],
    *,
    bundle_root: Path | None = None,
) -> tuple[ValidatedContract, ...]:
    """Validate a linked bundle with deterministic cross-document semantics."""
    copied = tuple(copy.deepcopy(dict(document)) for document in documents)
    identities: set[tuple[str, str, str]] = set()
    for index, document in enumerate(copied):
        schema_version = document.get("schema_version")
        if schema_version not in SCHEMA_FILES:
            continue
        try:
            stable_id, version = _identity(document)
        except KeyError:
            continue
        identity = (str(schema_version), stable_id, version)
        if identity in identities:
            _fail(
                "ARCH_DUPLICATE_ID",
                f"$[{index}]",
                "Linked contract bundle contains a duplicate versioned identity",
            )
        identities.add(identity)
    return tuple(
        validate_document(
            document,
            bundle_root=bundle_root,
            linked_documents=copied,
        )
        for document in copied
    )
