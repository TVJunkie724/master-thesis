"""Deterministic catalog-backed ResolvedDeploymentGraph compiler."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from src.deployment_specification.errors import DeploymentSpecificationError
from src.deployment_specification.models import ValidatedDeploymentManifest

from .binding_resolver import resolve_node_bindings
from .catalog import DeploymentComponentCatalog
from . import contracts
from .graph_evidence import content_digest
from .graph_models import (
    GraphBinding,
    GraphEdge,
    GraphNode,
    ResolvedDeploymentGraph,
    frozen_mapping,
)
from .registry import ArchitectureProfileRegistry
from .stage_planner import STAGES, plan_stages


GRAPH_SCHEMA_VERSION = "resolved-deployment-graph.v1"


def _fail(code: str, field: str, message: str) -> None:
    raise DeploymentSpecificationError(code, field, message)


def resolve_deployment_graph(
    manifest: ValidatedDeploymentManifest,
    *,
    registry: ArchitectureProfileRegistry | None = None,
) -> ResolvedDeploymentGraph:
    """Resolve every architecture assignment and edge before side effects."""

    if manifest.manifest_version != "4.0" or manifest.architecture is None:
        _fail(
            "DEPLOYMENT_MANIFEST_VERSION_UNSUPPORTED",
            "deployment_manifest.manifest_version",
            "Graph resolution requires DeploymentManifest v4",
        )
    architecture = manifest.architecture
    profile_ref = architecture["architecture_profile_ref"]
    registry = registry or ArchitectureProfileRegistry(
        profile_id=str(profile_ref["id"]), profile_version=str(profile_ref["version"])
    )
    catalog = DeploymentComponentCatalog(registry)
    specification = manifest.specification.specification
    specification_components = (
        specification["component_selections"]
        if manifest.specification.schema_version
        == "resolved-deployment-specification.v2"
        else specification["components"]
    )
    specification_by_id = {
        (
            item["implementation_component_id"]
            if "implementation_component_id" in item
            else item["component_id"]
        ): item
        for item in specification_components
    }
    assignments = sorted(
        architecture["component_assignments"],
        key=lambda item: item["assignment_id"],
    )
    provider_regions: dict[str, str] = {}
    for assignment in assignments:
        provider = str(assignment["provider"])
        region = str(assignment["region"])
        previous = provider_regions.setdefault(provider, region)
        if previous != region:
            _fail(
                "DEPLOYMENT_GRAPH_NODE_UNRESOLVED",
                "resolved_twin_architecture.component_assignments",
                "One provider resolves to multiple unsupported baseline regions",
            )
    assignment_ids = [item["assignment_id"] for item in assignments]
    if len(assignment_ids) != len(set(assignment_ids)):
        _fail(
            "DEPLOYMENT_GRAPH_NODE_UNRESOLVED",
            "resolved_twin_architecture.component_assignments",
            "Architecture assignment identifiers are duplicated",
        )

    extension_bindings = architecture.get("extension_bindings", ())
    nodes: list[GraphNode] = []
    used_specification_ids: set[str] = set()
    component_by_assignment: dict[str, Mapping[str, Any]] = {}
    assignment_by_id = {item["assignment_id"]: item for item in assignments}
    for assignment in assignments:
        component_id = assignment["deployment_component_id"]
        try:
            component = catalog.component(component_id)
            artifact_ref = component["package_artifact_ref"]
            artifact = catalog.artifacts[artifact_ref["id"]]
        except (KeyError, TypeError, DeploymentSpecificationError) as exc:
            _fail(
                "DEPLOYMENT_GRAPH_NODE_UNRESOLVED",
                f"component_assignments.{assignment['assignment_id']}",
                "Architecture component is absent from the pinned catalog",
            )
            raise AssertionError from exc
        if (
            component["component_version"] != assignment["deployment_component_version"]
            or component["provider"] != assignment["provider"]
            or assignment["logical_component_id"]
            not in component["logical_component_ids"]
            or artifact["artifact_version"] != artifact_ref["version"]
        ):
            _fail(
                "DEPLOYMENT_GRAPH_NODE_UNRESOLVED",
                f"component_assignments.{assignment['assignment_id']}",
                "Architecture component does not match its catalog declaration",
            )
        specification_ids = tuple(assignment["deployment_specification_component_ids"])
        selected_specification_components = []
        declared_specification_ids = {
            item["component_id"]
            for item in component["deployment_specification_bindings"]
        }
        for specification_id in specification_ids:
            specification_component = specification_by_id.get(specification_id)
            if (
                specification_component is None
                or specification_id not in declared_specification_ids
                or specification_component["provider"] != assignment["provider"]
            ):
                _fail(
                    "DEPLOYMENT_GRAPH_NODE_UNRESOLVED",
                    f"component_assignments.{assignment['assignment_id']}",
                    "Deployment specification component is not owned by the catalog node",
                )
            selected_specification_components.append(specification_component)
        node = GraphNode(
            node_id=f"node.{assignment['assignment_id']}",
            node_role="architecture_component",
            assignment_id=assignment["assignment_id"],
            logical_component_id=assignment["logical_component_id"],
            deployment_component_id=component_id,
            deployment_component_version=component["component_version"],
            provider=component["provider"],
            service_id=component["service_id"],
            region=assignment["region"],
            package_artifact=frozen_mapping(_artifact_projection(artifact)),
            package_artifacts=tuple(
                frozen_mapping(item)
                for item in _artifact_closure(catalog, artifact_ref)
            ),
            terraform=frozen_mapping(component["terraform_binding"]),
            deployment_specification_component_ids=specification_ids,
            deployment_dimensions=tuple(
                frozen_mapping(dimension)
                for selected in selected_specification_components
                for dimension in selected["dimensions"]
            ),
            input_ports=tuple(
                frozen_mapping(item) for item in component["input_ports"]
            ),
            output_ports=tuple(
                frozen_mapping(item) for item in component["output_ports"]
            ),
            extension_artifact_refs=tuple(
                frozen_mapping(item)
                for item in extension_bindings
                if item.get("logical_component_id")
                == assignment["logical_component_id"]
            ),
            permission_refs=tuple(component["required_permission_capabilities"]),
            configuration_ref=frozen_mapping(component["configuration_schema_ref"]),
            runtime_contract=frozen_mapping(component["runtime_contract"]),
            error_ref=frozen_mapping(component["error_contract_ref"]),
            observability_ref=frozen_mapping(component["observability_contract_ref"]),
            cleanup_ref=frozen_mapping(component["cleanup_contract_ref"]),
            lifecycle_stage_ids=STAGES,
        )
        resolve_node_bindings(
            node,
            component,
            selected_specification_components,
            extension_bindings,
        )
        nodes.append(node)
        used_specification_ids.update(specification_ids)
        component_by_assignment[assignment["assignment_id"]] = component

    node_by_deployment_component = {
        node.deployment_component_id: node for node in nodes
    }

    edges: list[GraphEdge] = []
    support_node_by_component: dict[str, GraphNode] = {}
    destination_bindings: set[tuple[str, str]] = set()
    source_bindings: set[tuple[str, str]] = set()
    for resolved in sorted(
        architecture["resolved_edges"],
        key=lambda item: item["resolved_edge_id"],
    ):
        source_assignment = assignment_by_id.get(resolved["source_assignment_id"])
        destination_assignment = assignment_by_id.get(
            resolved["destination_assignment_id"]
        )
        try:
            edge = catalog.edge(resolved["edge_implementation_id"])
        except contracts.ContractError as exc:
            _fail(
                "DEPLOYMENT_GRAPH_EDGE_UNRESOLVED",
                f"resolved_edges.{resolved['resolved_edge_id']}",
                "Architecture edge is absent from the pinned catalog",
            )
            raise AssertionError from exc
        if (
            source_assignment is None
            or destination_assignment is None
            or source_assignment["deployment_component_id"]
            not in edge["source_component_ids"]
            or destination_assignment["deployment_component_id"]
            not in edge["destination_component_ids"]
            or resolved["edge_id"] not in edge["logical_edge_ids"]
            or resolved["source_port_id"] != edge["source_output_port_id"]
            or resolved["destination_port_id"] != edge["destination_input_port_id"]
            or resolved["mechanism"] != edge["mechanism"]
            or resolved["transfer_route_class"] != edge["transfer_route_class"]
        ):
            _fail(
                "DEPLOYMENT_GRAPH_EDGE_UNRESOLVED",
                f"resolved_edges.{resolved['resolved_edge_id']}",
                "Architecture edge differs from its catalog declaration",
            )
        support_node_ids: list[str] = []
        for support_component_id in edge["glue_component_ids"]:
            support_node = node_by_deployment_component.get(
                support_component_id
            ) or support_node_by_component.get(support_component_id)
            if support_node is None:
                try:
                    support_component = catalog.component(support_component_id)
                except contracts.ContractError as exc:
                    _fail(
                        "DEPLOYMENT_GRAPH_NODE_UNRESOLVED",
                        f"resolved_edges.{resolved['resolved_edge_id']}",
                        "Graph edge support component is absent from the catalog",
                    )
                    raise AssertionError from exc
                support_specification_ids = tuple(
                    item["component_id"]
                    for item in support_component["deployment_specification_bindings"]
                    if item["component_id"] in specification_by_id
                )
                declared_support_ids = {
                    item["component_id"]
                    for item in support_component["deployment_specification_bindings"]
                }
                if (
                    not support_specification_ids
                    or set(support_specification_ids) != declared_support_ids
                    or any(
                        specification_by_id[item]["provider"]
                        != support_component["provider"]
                        for item in support_specification_ids
                    )
                ):
                    _fail(
                        "DEPLOYMENT_GRAPH_NODE_UNRESOLVED",
                        f"resolved_edges.{resolved['resolved_edge_id']}",
                        "Graph edge support component has no exact deployment specification",
                    )
                support_artifact_ref = support_component["package_artifact_ref"]
                support_artifact = catalog.artifacts[support_artifact_ref["id"]]
                support_assignment_id = "support." + support_component_id.removeprefix(
                    "deployment."
                )
                support_node = GraphNode(
                    node_id=f"node.{support_assignment_id}",
                    node_role="edge_support",
                    assignment_id=support_assignment_id,
                    logical_component_id=resolved["edge_id"],
                    deployment_component_id=support_component_id,
                    deployment_component_version=support_component["component_version"],
                    provider=support_component["provider"],
                    service_id=support_component["service_id"],
                    region=provider_regions[support_component["provider"]],
                    package_artifact=frozen_mapping(
                        _artifact_projection(support_artifact)
                    ),
                    package_artifacts=tuple(
                        frozen_mapping(item)
                        for item in _artifact_closure(
                            catalog,
                            support_artifact_ref,
                        )
                    ),
                    terraform=frozen_mapping(support_component["terraform_binding"]),
                    deployment_specification_component_ids=(support_specification_ids),
                    deployment_dimensions=tuple(
                        frozen_mapping(dimension)
                        for specification_id in support_specification_ids
                        for dimension in specification_by_id[specification_id][
                            "dimensions"
                        ]
                    ),
                    input_ports=tuple(
                        frozen_mapping(item)
                        for item in support_component["input_ports"]
                    ),
                    output_ports=tuple(
                        frozen_mapping(item)
                        for item in support_component["output_ports"]
                    ),
                    extension_artifact_refs=(),
                    permission_refs=tuple(
                        support_component["required_permission_capabilities"]
                    ),
                    configuration_ref=frozen_mapping(
                        support_component["configuration_schema_ref"]
                    ),
                    runtime_contract=frozen_mapping(
                        support_component["runtime_contract"]
                    ),
                    error_ref=frozen_mapping(support_component["error_contract_ref"]),
                    observability_ref=frozen_mapping(
                        support_component["observability_contract_ref"]
                    ),
                    cleanup_ref=frozen_mapping(
                        support_component["cleanup_contract_ref"]
                    ),
                    lifecycle_stage_ids=STAGES,
                )
                resolve_node_bindings(
                    support_node,
                    support_component,
                    tuple(
                        specification_by_id[item] for item in support_specification_ids
                    ),
                    (),
                )
                support_node_by_component[support_component_id] = support_node
                node_by_deployment_component[support_component_id] = support_node
                nodes.append(support_node)
                component_by_assignment[support_assignment_id] = support_component
                used_specification_ids.update(support_specification_ids)
            support_node_ids.append(support_node.node_id)
        source_key = (
            resolved["source_assignment_id"],
            resolved["source_port_id"],
        )
        destination_key = (
            resolved["destination_assignment_id"],
            resolved["destination_port_id"],
        )
        if source_key in source_bindings or destination_key in destination_bindings:
            _fail(
                "DEPLOYMENT_GRAPH_BINDING_DUPLICATE",
                f"resolved_edges.{resolved['resolved_edge_id']}",
                "Graph port is bound more than once",
            )
        source_bindings.add(source_key)
        destination_bindings.add(destination_key)
        edges.append(
            GraphEdge(
                graph_edge_id=f"graph.{resolved['resolved_edge_id']}",
                resolved_edge_id=resolved["resolved_edge_id"],
                logical_edge_id=resolved["edge_id"],
                source_node_id=(f"node.{resolved['source_assignment_id']}"),
                source_port_id=resolved["source_port_id"],
                destination_node_id=(f"node.{resolved['destination_assignment_id']}"),
                destination_port_id=resolved["destination_port_id"],
                support_node_ids=tuple(support_node_ids),
                edge_implementation_id=edge["edge_implementation_id"],
                edge_implementation_version=edge["edge_implementation_version"],
                mechanism=edge["mechanism"],
                payload_ref=frozen_mapping(edge["payload_contract_ref"]),
                delivery_ref=frozen_mapping(edge["delivery_requirements"]),
                trust_ref=frozen_mapping(edge["trust_contract_ref"]),
                transfer_route_class=edge["transfer_route_class"],
                pricing_refs=tuple(edge["pricing_model_refs"]),
                observability_ref=frozen_mapping(edge["observability_contract_ref"]),
                resolution_stage="terraform",
                terraform=frozen_mapping(edge["terraform_binding"]),
                sensitivity=_port_sensitivity(
                    component_by_assignment[resolved["source_assignment_id"]],
                    resolved["source_port_id"],
                ),
            )
        )

    for node in nodes:
        if node.node_role != "architecture_component":
            continue
        for port in node.input_ports:
            if (node.assignment_id, port["port_id"]) not in destination_bindings:
                _fail(
                    "DEPLOYMENT_GRAPH_BINDING_MISSING",
                    f"nodes.{node.node_id}.input_ports.{port['port_id']}",
                    "Catalog input port has no resolved edge",
                )
        for port in node.output_ports:
            if (node.assignment_id, port["port_id"]) not in source_bindings:
                _fail(
                    "DEPLOYMENT_GRAPH_BINDING_MISSING",
                    f"nodes.{node.node_id}.output_ports.{port['port_id']}",
                    "Catalog output port has no resolved edge",
                )

    if used_specification_ids != set(specification_by_id):
        _fail(
            "DEPLOYMENT_GRAPH_NODE_UNRESOLVED",
            "resolved_deployment_specification.components",
            "Deployment specification contains unowned or missing graph components",
        )

    node_tuple = tuple(nodes)
    edge_tuple = tuple(edges)
    node_bindings = [
        binding
        for node in node_tuple
        for binding in resolve_node_bindings(
            node,
            component_by_assignment[node.assignment_id],
            tuple(
                specification_by_id[component_id]
                for component_id in node.deployment_specification_component_ids
            ),
            extension_bindings,
        )
    ]
    edge_bindings = [
        GraphBinding(
            binding_id=f"binding.edge.{edge.resolved_edge_id}",
            binding_kind="component_output",
            source_id=str(edge.terraform["source_output_id"]),
            destination_node_id=edge.destination_node_id,
            destination_input_id=str(edge.terraform["destination_input_id"]),
            value_type="terraform_symbol",
            sensitivity=edge.sensitivity,
            resolution_stage="terraform",
            validator_id="validator.catalog-edge-symbol.v1",
            transformer_id="transformer.direct-reference.v1",
            compatibility_version="1",
        )
        for edge in edge_tuple
    ]
    bindings = tuple(
        sorted((*node_bindings, *edge_bindings), key=lambda item: item.binding_id)
    )
    binding_ids = [item.binding_id for item in bindings]
    if len(binding_ids) != len(set(binding_ids)):
        _fail(
            "DEPLOYMENT_GRAPH_BINDING_DUPLICATE",
            "bindings",
            "Graph binding identifier is duplicated",
        )
    topological_node_ids = _topological_order(
        node_tuple,
        edge_tuple,
        allowed_cycle_ids=frozenset(
            registry.profile["graph_policy"]["allowed_cycle_ids"]
        ),
    )
    stages = plan_stages(
        node_tuple,
        edge_tuple,
        bindings,
        topological_node_ids,
    )
    catalog_ref = {
        "id": registry.catalog["catalog_id"],
        "version": registry.catalog["catalog_version"],
        "digest": registry.catalog["content_digest"],
    }
    architecture_ref = {
        "schema_version": architecture["schema_version"],
        "digest": architecture["content_digest"],
    }
    specification_ref = {
        "schema_version": manifest.specification.schema_version,
        "digest": manifest.specification.digest,
    }
    profile_ref = dict(architecture["architecture_profile_ref"])
    graph_id = (
        "graph."
        + content_digest(
            {
                "architecture": architecture_ref,
                "catalog": catalog_ref,
                "specification": specification_ref,
            }
        ).removeprefix("sha256:")[:32]
    )
    without_digest = {
        "graph_schema_version": GRAPH_SCHEMA_VERSION,
        "graph_id": graph_id,
        "calculation_run_id": architecture["calculation_run_id"],
        "architecture_ref": architecture_ref,
        "profile_ref": profile_ref,
        "catalog_ref": catalog_ref,
        "specification_ref": specification_ref,
        "nodes": [node.to_contract() for node in node_tuple],
        "edges": [edge.to_contract() for edge in edge_tuple],
        "bindings": [binding.to_contract() for binding in bindings],
        "stages": [stage.to_contract() for stage in stages],
        "compatibility": dict(manifest.manifest["compatibility"]),
    }
    return ResolvedDeploymentGraph(
        graph_schema_version=GRAPH_SCHEMA_VERSION,
        graph_id=graph_id,
        calculation_run_id=architecture["calculation_run_id"],
        architecture_ref=frozen_mapping(architecture_ref),
        profile_ref=frozen_mapping(profile_ref),
        catalog_ref=frozen_mapping(catalog_ref),
        specification_ref=frozen_mapping(specification_ref),
        nodes=node_tuple,
        edges=edge_tuple,
        bindings=bindings,
        stages=stages,
        compatibility=frozen_mapping(manifest.manifest["compatibility"]),
        content_digest=content_digest(without_digest),
    )


def _port_sensitivity(
    component: Mapping[str, Any],
    port_id: str,
) -> str:
    return next(
        str(port["sensitivity"])
        for port in component["output_ports"]
        if port["port_id"] == port_id
    )


def _artifact_projection(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": artifact["artifact_id"],
        "version": artifact["artifact_version"],
        "source_digest": artifact["source_digest"],
        "digest_policy": artifact["digest_policy"],
        "builder_adapter_id": artifact["builder_adapter_id"],
        "repository_source_path": artifact["repository_source_path"],
        "platform_handler": artifact["platform_handler"],
        "user_source_policy": artifact["user_source_policy"],
    }


def _artifact_closure(
    catalog: DeploymentComponentCatalog,
    root_ref: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Return the deterministic transitive package dependency closure."""

    selected: dict[str, dict[str, Any]] = {}
    visiting: set[str] = set()

    def visit(reference: Mapping[str, Any]) -> None:
        artifact_id = str(reference["id"])
        if artifact_id in selected:
            if selected[artifact_id]["version"] != reference["version"]:
                _fail(
                    "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                    artifact_id,
                    "Package dependency version is contradictory",
                )
            return
        if artifact_id in visiting:
            _fail(
                "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                artifact_id,
                "Package dependency graph contains a cycle",
            )
        try:
            artifact = catalog.artifacts[artifact_id]
        except KeyError as exc:
            _fail(
                "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                artifact_id,
                "Package dependency is absent from the catalog",
            )
            raise AssertionError from exc
        if artifact["artifact_version"] != reference["version"]:
            _fail(
                "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                artifact_id,
                "Package dependency version differs from the catalog",
            )
        visiting.add(artifact_id)
        for dependency in artifact["dependency_artifact_refs"]:
            visit(dependency)
        visiting.remove(artifact_id)
        selected[artifact_id] = _artifact_projection(artifact)

    visit(root_ref)
    return tuple(selected[key] for key in sorted(selected))


def _topological_order(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    allowed_cycle_ids: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Order the condensation graph and expand only profile-allowlisted cycles."""

    nodes_by_id = {node.node_id: node for node in nodes}
    outgoing: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        outgoing[edge.source_node_id].add(edge.destination_node_id)

    next_index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(node_id: str) -> None:
        nonlocal next_index
        indexes[node_id] = next_index
        lowlinks[node_id] = next_index
        next_index += 1
        stack.append(node_id)
        on_stack.add(node_id)
        for destination in sorted(outgoing[node_id]):
            if destination not in indexes:
                visit(destination)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[destination])
            elif destination in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indexes[destination])
        if lowlinks[node_id] != indexes[node_id]:
            return
        connected: list[str] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            connected.append(member)
            if member == node_id:
                break
        components.append(tuple(sorted(connected)))

    for node_id in sorted(nodes_by_id):
        if node_id not in indexes:
            visit(node_id)

    cyclic_components = [
        component
        for component in components
        if len(component) > 1
        or any(node_id in outgoing[node_id] for node_id in component)
    ]
    actual_cycle_ids = {
        "cycle."
        + ".".join(
            sorted(
                nodes_by_id[node_id].logical_component_id.removeprefix("component.")
                for node_id in component
            )
        )
        for component in cyclic_components
    }
    if actual_cycle_ids != set(allowed_cycle_ids):
        _fail(
            "DEPLOYMENT_GRAPH_CYCLE_FORBIDDEN",
            "resolved_twin_architecture.resolved_edges",
            "Resolved deployment graph cycles differ from the profile allowlist",
        )

    component_by_node = {
        node_id: index
        for index, component in enumerate(components)
        for node_id in component
    }
    component_outgoing: dict[int, set[int]] = defaultdict(set)
    indegree = {index: 0 for index in range(len(components))}
    for source, destinations in outgoing.items():
        source_component = component_by_node[source]
        for destination in destinations:
            destination_component = component_by_node[destination]
            if source_component == destination_component:
                continue
            if destination_component not in component_outgoing[source_component]:
                component_outgoing[source_component].add(destination_component)
                indegree[destination_component] += 1

    ready = sorted(
        (index for index, count in indegree.items() if count == 0),
        key=lambda index: components[index],
    )
    ordered_components: list[int] = []
    while ready:
        component_index = ready.pop(0)
        ordered_components.append(component_index)
        for destination in sorted(
            component_outgoing[component_index],
            key=lambda index: components[index],
        ):
            indegree[destination] -= 1
            if indegree[destination] == 0:
                ready.append(destination)
                ready.sort(key=lambda index: components[index])
    if len(ordered_components) != len(components):
        _fail(
            "DEPLOYMENT_GRAPH_CYCLE_FORBIDDEN",
            "resolved_twin_architecture.resolved_edges",
            "Resolved deployment condensation graph contains a cycle",
        )
    return tuple(
        node_id
        for component_index in ordered_components
        for node_id in components[component_index]
    )
