"""Network-free Phase 8.3 catalog completeness and drift gate."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import hcl2
import yaml

from .registry import ArchitectureProfileRegistry, DEFINITIONS_ROOT


@dataclass
class CatalogCheckError(RuntimeError):
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} at {self.path}: {self.message}"


def _fail(code: str, path: str, message: str) -> None:
    raise CatalogCheckError(code, path, message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail("CATALOG_PACKAGE_REFERENCE_INVALID", str(path), type(exc).__name__)
    if not isinstance(payload, dict):
        _fail("CATALOG_PACKAGE_REFERENCE_INVALID", str(path), "Expected object")
    return payload


def _file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (
            candidate / "contracts" / "architecture-profiles"
        ).is_dir() and (candidate / "3-cloud-deployer" / "src" / "terraform").is_dir():
            return candidate
    _fail(
        "CATALOG_PACKAGE_REFERENCE_INVALID",
        "repository_root",
        "The complete repository must be mounted for the cross-project drift gate",
    )


def _artifact_digest(root: Path, source: str) -> str:
    source_path = root / source
    if not source_path.exists() or source_path.is_symlink():
        _fail("CATALOG_PACKAGE_REFERENCE_INVALID", source, "Missing or unsafe source")
    paths = [source_path] if source_path.is_file() else sorted(source_path.rglob("*"))
    digest = hashlib.sha256()
    count = 0
    for path in paths:
        if path.is_symlink():
            _fail(
                "CATALOG_PACKAGE_REFERENCE_INVALID",
                path.relative_to(root).as_posix(),
                "Package sources must not contain symbolic links",
            )
        if (
            not path.is_file()
            or "__pycache__" in path.parts
            or ".git" in path.parts
            or path.suffix.lower() == ".zip"
            or path.name.startswith(".git")
            or path.name == ".DS_Store"
        ):
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        count += 1
    if count == 0:
        _fail("CATALOG_PACKAGE_REFERENCE_INVALID", source, "Empty package source")
    return f"sha256:{digest.hexdigest()}"


def _verify_artifact_handler(root: Path, artifact: dict[str, Any]) -> None:
    handler = artifact["platform_handler"]
    if handler in {
        "provider.shared-runtime",
        "provider-selected.user-package",
        "terraform.managed",
    }:
        return
    module_name, separator, function_name = handler.partition(".")
    source = root / artifact["repository_source_path"]
    module_path = (
        source.with_suffix(".py")
        if source.is_file() and source.stem == module_name
        else source / f"{module_name}.py"
    )
    if not separator or not module_path.is_file():
        _fail(
            "CATALOG_PACKAGE_REFERENCE_INVALID",
            artifact["artifact_id"],
            f"Handler module does not exist: {handler}",
        )
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        _fail(
            "CATALOG_PACKAGE_REFERENCE_INVALID",
            artifact["artifact_id"],
            f"Handler module is invalid ({type(exc).__name__})",
        )
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if function_name not in functions and not (
        module_name == "function_app" and function_name == "main" and functions
    ):
        _fail(
            "CATALOG_PACKAGE_REFERENCE_INVALID",
            artifact["artifact_id"],
            f"Handler callable does not exist: {handler}",
        )


def _hcl_symbols(terraform_root: Path) -> tuple[set[str], set[str], set[str]]:
    resources: set[str] = set()
    variables: set[str] = set()
    outputs: set[str] = set()

    def normalize(value: object) -> str:
        return str(value).strip('"')

    for path in sorted(terraform_root.glob("*.tf")):
        try:
            with path.open("r", encoding="utf-8") as stream:
                document = hcl2.load(stream)
        except Exception as exc:
            _fail(
                "CATALOG_TERRAFORM_REFERENCE_INVALID",
                path.name,
                f"HCL parser rejected source ({type(exc).__name__})",
            )
        for block in document.get("resource", []):
            for resource_type, instances in block.items():
                resources.update(
                    f"{normalize(resource_type)}.{normalize(name)}"
                    for name in instances
                )
        for block in document.get("variable", []):
            variables.update(normalize(name) for name in block)
        for block in document.get("output", []):
            outputs.update(normalize(name) for name in block)
    return resources, variables, outputs


def _yaml_mapping(path: Path, key: str) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    value = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(value, dict):
        _fail(
            "CATALOG_PRICING_REFERENCE_INVALID",
            path.relative_to(path.parents[2]).as_posix(),
            f"Missing mapping {key}",
        )
    return value


def _check_unique(values: Iterable[str], code: str, path: str) -> None:
    materialized = list(values)
    if len(materialized) != len(set(materialized)):
        _fail(code, path, "Duplicate ownership is forbidden")


def check_catalog_completeness(
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Validate definitions against HCL, packages, pricing, permissions and slots."""
    root = (
        repository_root.resolve()
        if repository_root is not None
        else _repository_root(Path(__file__).resolve())
    )
    registry = ArchitectureProfileRegistry()
    profile = registry.profile
    catalog = registry.catalog
    providers = registry.providers
    manifest = _read_json(DEFINITIONS_ROOT / "manifest.json")
    definition_digests = manifest["definition_digests"]
    if (
        definition_digests["profile"] != profile["content_digest"]
        or definition_digests["catalog"] != catalog["content_digest"]
        or any(
            definition_digests["providers"][provider]
            != document["content_digest"]
            for provider, document in providers.items()
        )
    ):
        _fail(
            "CATALOG_SOURCE_DECISION_STALE",
            "manifest.definition_digests",
            "Definition manifest digest differs from the validated bundle",
        )
    actual_counts = {
        "logical_components": len(profile["components"]),
        "logical_edges": len(profile["edges"]),
        "deployment_components": len(catalog["components"]),
        "edge_implementations": len(catalog["edge_implementations"]),
        "package_artifacts": len(catalog["package_artifacts"]),
        "provider_profiles": len(providers),
    }
    if manifest["counts"] != actual_counts:
        _fail(
            "CATALOG_SOURCE_DECISION_STALE",
            "manifest.counts",
            "Definition manifest counts differ from the validated bundle",
        )
    decision = _read_json(
        root
        / "contracts"
        / "architecture-inventory"
        / "v1"
        / "five-layer-baseline-v1-decision.json"
    )
    inventory = _read_json(
        root / "contracts" / "architecture-inventory" / "v1" / "current-graph.json"
    )
    source_digests = manifest["source_digests"]
    if source_digests["baseline_decision"] != decision["content_digest"]:
        _fail(
            "CATALOG_SOURCE_DECISION_STALE",
            "manifest.source_digests.baseline_decision",
            "Baseline decision digest differs",
        )
    if source_digests["architecture_inventory"] != inventory["content_digest"]:
        _fail(
            "CATALOG_SOURCE_DECISION_STALE",
            "manifest.source_digests.architecture_inventory",
            "Architecture inventory digest differs",
        )
    deployment_dimensions_path = (
        root
        / "contracts"
        / "resolved-deployment-specification"
        / "v1"
        / "deployment-dimensions.json"
    )
    extension_registry_path = (
        root
        / "contracts"
        / "user-function-extension"
        / "v1"
        / "registry.json"
    )
    if source_digests["deployment_dimensions"] != _file_digest(
        deployment_dimensions_path
    ):
        _fail(
            "CATALOG_SOURCE_DECISION_STALE",
            "manifest.source_digests.deployment_dimensions",
            "Deployment dimension digest differs",
        )
    if source_digests["user_function_extension"] != _file_digest(
        extension_registry_path
    ):
        _fail(
            "CATALOG_SOURCE_DECISION_STALE",
            "manifest.source_digests.user_function_extension",
            "User-function extension registry digest differs",
        )
    package_builder_root = (
        root
        / "3-cloud-deployer"
        / "src"
        / "providers"
        / "terraform"
        / "package_builders"
    )
    for name, expected_digest in source_digests["package_builders"].items():
        if _file_digest(package_builder_root / f"{name}.py") != expected_digest:
            _fail(
                "CATALOG_PACKAGE_DIGEST_MISMATCH",
                f"manifest.source_digests.package_builders.{name}",
                "Pinned package builder digest differs",
            )
    if (
        profile["profile_id"] != decision["profile_id"]
        or profile["profile_version"] != decision["profile_version"]
        or [
            responsibility["responsibility_id"]
            for responsibility in profile["responsibilities"]
        ]
        != [
            responsibility["responsibility_id"]
            for responsibility in decision["required_responsibilities"]
        ]
        or list(profile["optimization_slot_ids"])
        != decision["optimization_slots"]
        or list(profile["functional_completeness_rules"])
        != decision["functional_completeness_rules"]
        or len(profile["responsibilities"]) != 5
        or len(profile["components"]) != 7
        or len(profile["edges"]) != 6
        or [item["slot_id"] for item in profile["extension_slots"]]
        != ["processor.telemetry"]
    ):
        _fail(
            "CATALOG_COMPONENT_MISSING",
            "profile",
            "Baseline decision-to-profile cardinality differs",
        )

    resources, variables, outputs = _hcl_symbols(
        root / "3-cloud-deployer" / "src" / "terraform"
    )
    claimed_resources: list[str] = []
    dimension_registry = _read_json(deployment_dimensions_path)
    dimension_components = dimension_registry["components"]
    permission_capabilities = {
        provider: set(
            _read_json(
                root
                / "3-cloud-deployer"
                / "docs"
                / "references"
                / "permission_sets"
                / f"{provider}_thesis_demo_v1.json"
            )["capabilities"]
        )
        for provider in ("aws", "azure", "gcp")
    }
    formula_sets = _yaml_mapping(
        root / "2-twin2clouds" / "pricing_registry" / "formula_sets.yaml",
        "formula_sets",
    )
    formula_ids = {
        formula_id
        for formula_set in formula_sets.values()
        for formula_id in formula_set["formulas"]
    }
    intent_registry = yaml.safe_load(
        (
            root / "2-twin2clouds" / "pricing_registry" / "intents.yaml"
        ).read_text(encoding="utf-8")
    )
    intent_ids = set(intent_registry["intents"])
    pricing_root = root / "2-twin2clouds" / "pricing_registry"
    for name, expected_digest in source_digests["pricing_registries"].items():
        path = pricing_root / f"{name}.yaml"
        if _file_digest(path) != expected_digest:
            _fail(
                "CATALOG_PRICING_REFERENCE_INVALID",
                f"manifest.source_digests.pricing_registries.{name}",
                "Pinned pricing registry digest differs",
            )
    optimization_bundles = _yaml_mapping(
        pricing_root / "optimization_bundles.yaml", "bundles"
    )
    calculation_strategies = _yaml_mapping(
        pricing_root / "calculation_strategies.yaml",
        "calculation_strategies",
    )
    service_models = _yaml_mapping(
        pricing_root / "service_models.yaml", "service_models"
    )
    workload_contracts = _yaml_mapping(
        pricing_root / "workload_contracts.yaml", "workload_contracts"
    )
    optimization = profile["optimization_bundle"]
    optimization_declaration = optimization_bundles.get(
        optimization["optimization_strategy_id"]
    )
    if optimization_declaration is None:
        _fail(
            "CATALOG_PRICING_REFERENCE_INVALID",
            "profile.optimization_bundle.optimization_strategy_id",
            "Unknown optimization bundle",
        )
    exact_bundle_fields = {
        "calculation_strategy_id": optimization_declaration[
            "calculation_strategy_id"
        ],
        "formula_set_id": optimization_declaration["formula_set_id"],
        "scoring_strategy_id": optimization_declaration["scoring_strategy_id"],
        "workload_contract_id": optimization_declaration["workload_contract_id"],
    }
    for field, expected in exact_bundle_fields.items():
        if optimization[field] != expected:
            _fail(
                "CATALOG_PRICING_REFERENCE_INVALID",
                f"profile.optimization_bundle.{field}",
                f"Expected current registry ID {expected}",
            )
    calculation = calculation_strategies.get(
        optimization["calculation_strategy_id"]
    )
    if (
        calculation is None
        or calculation["formula_set_id"] != optimization["formula_set_id"]
        or calculation["workload_contract_id"]
        != optimization["workload_contract_id"]
        or calculation["calculation_model_id"] not in service_models
        or optimization["formula_set_id"] not in formula_sets
        or optimization["workload_contract_id"] not in workload_contracts
        or profile["workload_contract_ref"]["id"]
        != optimization["workload_contract_id"]
        or optimization["pricing_registry_id"] != "pricing-registry"
    ):
        _fail(
            "CATALOG_PRICING_REFERENCE_INVALID",
            "profile.optimization_bundle",
            "Optimization, calculation, formula, service, or workload refs drift",
        )

    artifact_by_id = {
        artifact["artifact_id"]: artifact for artifact in catalog["package_artifacts"]
    }
    _check_unique(
        (
            artifact["artifact_id"]
            for artifact in catalog["package_artifacts"]
        ),
        "CATALOG_DUPLICATE_OWNERSHIP",
        "catalog.package_artifacts.artifact_id",
    )
    _check_unique(
        (
            artifact["repository_source_path"]
            for artifact in catalog["package_artifacts"]
        ),
        "CATALOG_DUPLICATE_OWNERSHIP",
        "catalog.package_artifacts.repository_source_path",
    )
    decision_component_owners: list[str] = []
    for artifact in catalog["package_artifacts"]:
        decision_component_owners.extend(artifact["decision_implementation_ids"])
        actual = _artifact_digest(root, artifact["repository_source_path"])
        if actual != artifact["source_digest"]:
            _fail(
                "CATALOG_PACKAGE_DIGEST_MISMATCH",
                artifact["artifact_id"],
                "Canonical package source digest differs",
            )
        _verify_artifact_handler(root, artifact)
        for dependency in artifact["dependency_artifact_refs"]:
            if dependency["id"] not in artifact_by_id:
                _fail(
                    "CATALOG_PACKAGE_REFERENCE_INVALID",
                    artifact["artifact_id"],
                    "Unknown package dependency",
                )

    claimed_dimension_components: list[str] = []
    for component in catalog["components"]:
        component_id = component["deployment_component_id"]
        decision_component_owners.extend(component["decision_implementation_ids"])
        if component["package_artifact_ref"]["id"] not in artifact_by_id:
            _fail(
                "CATALOG_PACKAGE_REFERENCE_INVALID",
                component_id,
                "Unknown component package artifact",
            )
        binding = component["terraform_binding"]
        for address in binding["resource_addresses"]:
            if address not in resources:
                _fail(
                    "CATALOG_TERRAFORM_REFERENCE_INVALID",
                    component_id,
                    f"Unknown Terraform resource {address}",
                )
            claimed_resources.append(address)
        input_symbols = {
            item["terraform_variable"] for item in binding["input_bindings"]
        }
        if input_symbols - variables:
            _fail(
                "CATALOG_TERRAFORM_REFERENCE_INVALID",
                component_id,
                "Unknown Terraform input variable",
            )
        output_symbols = {
            item["terraform_output"] for item in binding["outputs"]
        }
        if output_symbols - outputs:
            _fail(
                "CATALOG_TERRAFORM_REFERENCE_INVALID",
                component_id,
                "Unknown Terraform output",
            )
        expected_input_ids = {
            item["input_id"] for item in binding["input_bindings"]
        }
        if expected_input_ids != set(binding["allowed_input_variable_ids"]):
            _fail(
                "CATALOG_DEPLOYMENT_BINDING_INVALID",
                component_id,
                "Input allowlist and symbol bindings differ",
            )
        expected_service_ids: set[str] = set()
        for deployment_binding in component["deployment_specification_bindings"]:
            specification_id = deployment_binding["component_id"]
            specification = dimension_components.get(specification_id)
            if specification is None:
                _fail(
                    "CATALOG_DEPLOYMENT_BINDING_INVALID",
                    component_id,
                    f"Unknown deployment component {specification_id}",
                )
            claimed_dimension_components.append(specification_id)
            expected_service_ids.add(specification["service_id"])
            if specification["slot_id"] != deployment_binding["slot_id"]:
                _fail(
                    "CATALOG_DEPLOYMENT_BINDING_INVALID",
                    component_id,
                    "Deployment slot differs from dimension registry",
                )
            expected_variables = {
                dimension["terraform_target"]
                for dimension in specification.get("dimensions", {}).values()
                if "terraform_target" in dimension
            }
            if not expected_variables.issubset(input_symbols):
                _fail(
                    "CATALOG_DEPLOYMENT_BINDING_INVALID",
                    component_id,
                    "Deployable dimension lacks its Terraform input",
                )
            for dimension in specification.get("dimensions", {}).values():
                if (
                    dimension["classification"]
                    in {"account_scope", "usage_tier"}
                    and "terraform_target" in dimension
                ):
                    _fail(
                        "CATALOG_DEPLOYMENT_BINDING_INVALID",
                        component_id,
                        "Account or usage dimension became a Terraform selection",
                    )
        if (
            set(component["service_ids"]) != expected_service_ids
            or component["service_id"] not in expected_service_ids
        ):
            _fail(
                "CATALOG_DEPLOYMENT_BINDING_INVALID",
                component_id,
                "Provider service IDs differ from the deployment dimensions",
            )
        for formula_id in component["formula_refs"]:
            if formula_id not in formula_ids:
                _fail(
                    "CATALOG_FORMULA_REFERENCE_INVALID",
                    component_id,
                    f"Unknown formula {formula_id}",
                )
        for pricing_ref in component["pricing_model_refs"]:
            if pricing_ref.removeprefix("pricing-intent.") not in intent_ids:
                _fail(
                    "CATALOG_PRICING_REFERENCE_INVALID",
                    component_id,
                    f"Unknown pricing intent {pricing_ref}",
                )
        provider = component["provider"]
        for permission in component["required_permission_capabilities"]:
            capability = permission.rsplit(".", 1)[-1].replace("-", "_")
            if capability not in permission_capabilities[provider]:
                _fail(
                    "CATALOG_PERMISSION_REFERENCE_INVALID",
                    component_id,
                    f"Permission capability {capability} is not in thesis-demo-v1",
                )
    _check_unique(
        claimed_dimension_components,
        "CATALOG_DUPLICATE_OWNERSHIP",
        "catalog.components.deployment_specification_bindings",
    )
    if set(claimed_dimension_components) != set(dimension_components):
        missing = sorted(set(dimension_components) - set(claimed_dimension_components))
        _fail(
            "CATALOG_COMPONENT_MISSING",
            "catalog.components.deployment_specification_bindings",
            f"Deployment dimension coverage differs; missing={missing}",
        )
    expected_component_decisions = {
        item["target_implementation_id"]
        for item in decision["component_decisions"]
        if item["action"] == "retain"
        and item["implementation_owner_phase"]
        in {"Phase 8.3", "Phase 8.3 after #113"}
    }
    _check_unique(
        decision_component_owners,
        "CATALOG_DUPLICATE_OWNERSHIP",
        "catalog.decision_implementation_ids",
    )
    if set(decision_component_owners) != expected_component_decisions:
        _fail(
            "CATALOG_COMPONENT_MISSING",
            "catalog.decision_implementation_ids",
            "Phase 8.1 component decision coverage differs",
        )
    _check_unique(
        claimed_resources,
        "CATALOG_DUPLICATE_OWNERSHIP",
        "catalog.components.terraform_binding.resource_addresses",
    )
    logical_edges = {
        edge["edge_id"]: edge for edge in profile["edges"]
    }
    decision_edges = {
        item["target_edge_id"]: item
        for item in decision["edge_decisions"]
        if item["implementation_owner_phase"] == "Phase 8.3"
    }
    catalog_component_ids = {
        component["deployment_component_id"] for component in catalog["components"]
    }
    claimed_decision_edges: list[str] = []
    for edge in catalog["edge_implementations"]:
        edge_id = edge["edge_implementation_id"]
        claimed_decision_edges.extend(edge["decision_edge_ids"])
        decision_edge = decision_edges.get(edge["decision_edge_ids"][0])
        if (
            decision_edge is None
            or edge["mechanism"] != decision_edge["mechanism"]
            or edge["payload_contract_ref"]["id"]
            != decision_edge["payload_envelope"]["schema_id"]
            or edge["payload_contract_ref"]["version"]
            != decision_edge["payload_envelope"]["version"]
            or edge["trust_contract_ref"]["id"]
            != decision_edge["trust_boundary_id"]
        ):
            _fail(
                "CATALOG_EDGE_MISSING",
                edge_id,
                "Phase 8.1 edge decision mapping differs",
            )
        for component_id in (
            *edge["source_component_ids"],
            *edge["destination_component_ids"],
        ):
            if (
                component_id not in catalog_component_ids
                and not component_id.startswith("platform.")
            ):
                _fail(
                    "CATALOG_EDGE_MISSING",
                    edge_id,
                    f"Unknown edge component {component_id}",
                )
        for formula_id in edge["formula_refs"]:
            if formula_id not in formula_ids:
                _fail(
                    "CATALOG_FORMULA_REFERENCE_INVALID",
                    edge_id,
                    f"Unknown edge formula {formula_id}",
                )
        for pricing_ref in edge["pricing_model_refs"]:
            if pricing_ref.removeprefix("pricing-intent.") not in intent_ids:
                _fail(
                    "CATALOG_PRICING_REFERENCE_INVALID",
                    edge_id,
                    f"Unknown edge pricing intent {pricing_ref}",
                )
        if edge["logical_edge_ids"]:
            logical = logical_edges[edge["logical_edge_ids"][0]]
            if (
                edge["payload_contract_ref"]["id"] != logical["edge_contract_id"]
                or dict(edge["delivery_requirements"])
                != dict(logical["delivery_requirements"])
            ):
                _fail(
                    "CATALOG_EDGE_MISSING",
                    edge_id,
                    "Payload or delivery contract differs from the logical edge",
                )
        if edge["provider"] != "platform":
            for permission in edge["required_permission_capabilities"]:
                parts = permission.split(".")
                permission_provider = parts[1]
                capability = parts[-1].replace("-", "_")
                if (
                    permission_provider not in permission_capabilities
                    or capability
                    not in permission_capabilities[permission_provider]
                ):
                    _fail(
                        "CATALOG_PERMISSION_REFERENCE_INVALID",
                        edge_id,
                        f"Unknown edge permission capability {permission}",
                    )
        for glue_component_id in edge["glue_component_ids"]:
            glue_component = next(
                (
                    component
                    for component in catalog["components"]
                    if component["deployment_component_id"] == glue_component_id
                ),
                None,
            )
            if glue_component is None or glue_component["component_kind"] != "adapter":
                _fail(
                    "CATALOG_EDGE_MISSING",
                    edge_id,
                    f"Unknown glue adapter {glue_component_id}",
                )
        if (
            edge["transfer_route_class"] == "cross_provider"
            and not edge["glue_component_ids"]
        ):
            _fail(
                "CATALOG_EDGE_MISSING",
                edge_id,
                "Cross-provider edge lacks an explicit glue adapter",
            )
    _check_unique(
        claimed_decision_edges,
        "CATALOG_DUPLICATE_OWNERSHIP",
        "catalog.edge_implementations.decision_edge_ids",
    )
    if set(claimed_decision_edges) != set(decision_edges):
        _fail(
            "CATALOG_EDGE_MISSING",
            "catalog.edge_implementations.decision_edge_ids",
            "Phase 8.1 edge decision coverage differs",
        )

    extension_registry = _read_json(extension_registry_path)
    extension_slot = next(
        (
            slot
            for slot in extension_registry["slots"]
            if slot["slot_id"] == "processor.telemetry"
        ),
        None,
    )
    if extension_slot is None:
        _fail(
            "CATALOG_EXTENSION_SLOT_INVALID",
            "processor.telemetry",
            "The #113 extension slot is absent",
        )
    for provider in ("aws", "azure", "gcp"):
        component = next(
            (
                item
                for item in catalog["components"]
                if item["deployment_component_id"]
                == f"deployment.{provider}.processing"
            ),
            None,
        )
        if component is None:
            _fail(
                "CATALOG_EXTENSION_SLOT_INVALID",
                provider,
                "Provider processing component is absent",
            )
        if [
            (reference["id"], reference["version"])
            for reference in component["extension_slot_refs"]
        ] != [("processor.telemetry", "1")]:
            _fail(
                "CATALOG_EXTENSION_SLOT_INVALID",
                component["deployment_component_id"],
                "Extension slot reference differs",
            )
        adapter_ids = {
            adapter["provider"]: adapter["adapter_id"]
            for adapter in extension_slot["runtime_contract"]["provider_adapters"]
        }
        if (
            component["runtime_contract"]["platform_handler_adapter_id"]
            != adapter_ids[provider]
            or artifact_by_id[component["package_artifact_ref"]["id"]][
                "user_source_policy"
            ]
            != "validated_extension_slot"
        ):
            _fail(
                "CATALOG_EXTENSION_SLOT_INVALID",
                component["deployment_component_id"],
                "Provider adapter or wrapper policy differs from #113",
            )

    expected_provider_shapes = {
        "aws": (7, 5, "profile-target-not-implemented"),
        "azure": (7, 5, "profile-target-not-implemented"),
        "gcp": (5, 4, "profile-provider-capability-incomplete"),
    }
    provider_report = {}
    for provider, (components, edges, reason) in expected_provider_shapes.items():
        document = providers[provider]
        actual = (
            len(document["component_mappings"]),
            len(document["edge_mappings"]),
            document["unsupported_reasons"][0]["reason_code"],
        )
        if actual != (components, edges, reason) or document["supported"]:
            _fail(
                "PROVIDER_PROFILE_INCOMPLETE",
                provider,
                "Provider status differs from the Phase 8.1 admissibility decision",
            )
        for mapping in document["component_mappings"]:
            if any(
                service_model_ref not in service_models
                for service_model_ref in mapping["service_model_refs"]
            ):
                _fail(
                    "CATALOG_PRICING_REFERENCE_INVALID",
                    provider,
                    "Provider profile references an unknown service model",
                )
        provider_report[provider] = {
            "supported": False,
            "component_mappings": components,
            "edge_mappings": edges,
            "missing_capability_ids": list(
                document["capability_claims"]["missing_capability_ids"]
            ),
            "reason_code": reason,
        }

    fixture_report = {}
    for path in sorted((DEFINITIONS_ROOT / "fixtures").rglob("*.json")):
        fixture = _read_json(path)
        if (
            fixture["architecture_profile_ref"]["digest"]
            != profile["content_digest"]
            or fixture["catalog_ref"]["digest"] != catalog["content_digest"]
        ):
            _fail(
                "CATALOG_SOURCE_DECISION_STALE",
                path.name,
                "Completeness fixture digest differs",
            )
        fixture_report[fixture["scenario_id"]] = {
            "status": fixture["expected_status"],
            "reason_code": fixture["expected_reason_code"],
        }
    if set(fixture_report) != {
        "scenario.all-aws",
        "scenario.all-azure",
        "scenario.all-gcp",
        "scenario.mixed-provider",
        "scenario.user-processor",
    }:
        _fail(
            "PROVIDER_PROFILE_INCOMPLETE",
            "definitions.fixtures",
            "Required provider scenario fixture set differs",
        )

    return {
        "status": "complete",
        "profile": {
            "id": profile["profile_id"],
            "version": profile["profile_version"],
            "digest": profile["content_digest"],
            "logical_components": len(profile["components"]),
            "logical_edges": len(profile["edges"]),
            "extension_slots": len(profile["extension_slots"]),
        },
        "catalog": {
            "id": catalog["catalog_id"],
            "version": catalog["catalog_version"],
            "digest": catalog["content_digest"],
            "deployment_components": len(catalog["components"]),
            "edge_implementations": len(catalog["edge_implementations"]),
            "package_artifacts": len(catalog["package_artifacts"]),
            "terraform_resources": len(claimed_resources),
        },
        "providers": provider_report,
        "fixtures": fixture_report,
    }
