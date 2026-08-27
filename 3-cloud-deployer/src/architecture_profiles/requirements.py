"""Graph-derived deployment prerequisite projection for the thesis PoC."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from .graph_models import GraphEdge, GraphNode, GraphRequirement, frozen_mapping

IDENTITY_EXCHANGE_BY_PAIR = {
    ("aws", "azure"): "aws_oidc_to_entra_federated_credential",
    ("aws", "gcp"): "aws_subject_token_to_gcp_workload_identity_federation",
    ("azure", "aws"): "entra_managed_identity_oidc_to_assume_role_with_web_identity",
    ("azure", "gcp"): "entra_managed_identity_oidc_to_gcp_workload_identity_federation",
    ("gcp", "aws"): "google_service_account_oidc_to_assume_role_with_web_identity",
    ("gcp", "azure"): "google_service_account_oidc_to_entra_federated_credential",
}

_TARGET_SCOPE = {
    "aws": "account",
    "azure": "subscription",
    "gcp": "project",
}

_AWS_CONTROL_PLANES = {
    "aws_cloudwatch": "logs",
    "aws_codebuild": "codebuild",
    "aws_dynamodb": "dynamodb",
    "aws_ecr": "ecr",
    "aws_ecs": "ecs",
    "aws_grafana": "grafana",
    "aws_iam": "iam",
    "aws_iot": "iot",
    "aws_kinesis": "kinesis",
    "aws_lambda": "lambda",
    "aws_s3": "s3",
    "aws_scheduler": "scheduler",
    "aws_sfn": "states",
    "aws_sns": "sns",
    "aws_sqs": "sqs",
    "aws_ssoadmin": "sso-admin",
    "awscc_iot_command": "iot",
    "awscc_iottwinmaker": "iottwinmaker",
}

_AZURE_RESOURCE_PROVIDERS = {
    "azurerm_container_app": "Microsoft.App",
    "azurerm_container_registry": "Microsoft.ContainerRegistry",
    "azurerm_cosmosdb": "Microsoft.DocumentDB",
    "azurerm_dashboard": "Microsoft.Dashboard",
    "azurerm_digital_twins": "Microsoft.DigitalTwins",
    "azurerm_eventhub": "Microsoft.EventHub",
    "azurerm_function_app": "Microsoft.Web",
    "azurerm_iothub": "Microsoft.Devices",
    "azurerm_log_analytics": "Microsoft.OperationalInsights",
    "azurerm_logic_app": "Microsoft.Logic",
    "azurerm_monitor": "Microsoft.Insights",
    "azurerm_role_assignment": "Microsoft.Authorization",
    "azurerm_servicebus": "Microsoft.ServiceBus",
    "azurerm_storage": "Microsoft.Storage",
    "azurerm_user_assigned_identity": "Microsoft.ManagedIdentity",
}

_GCP_APIS = {
    "google_artifact_registry": "artifactregistry.googleapis.com",
    "google_cloud_run": "run.googleapis.com",
    "google_cloud_scheduler": "cloudscheduler.googleapis.com",
    "google_compute": "compute.googleapis.com",
    "google_container": "container.googleapis.com",
    "google_firestore": "firestore.googleapis.com",
    "google_iap": "iap.googleapis.com",
    "google_logging": "logging.googleapis.com",
    "google_project_iam": "cloudresourcemanager.googleapis.com",
    "google_pubsub": "pubsub.googleapis.com",
    "google_service_account": "iam.googleapis.com",
    "google_storage": "storage.googleapis.com",
    "google_workflows": "workflows.googleapis.com",
    "kubernetes_": "container.googleapis.com",
}

_QUOTA_CONTROL_PLANES = {
    "aws": {"grafana", "iottwinmaker", "kinesis"},
    "azure": {
        "Microsoft.App",
        "Microsoft.Dashboard",
        "Microsoft.DocumentDB",
        "Microsoft.EventHub",
        "Microsoft.Web",
    },
    "gcp": {
        "compute.googleapis.com",
        "container.googleapis.com",
        "firestore.googleapis.com",
        "run.googleapis.com",
    },
}

_IDENTITY_RESOURCE_PREFIXES = {
    "aws": ("aws_iam_", "aws_ssoadmin_"),
    "azure": ("azurerm_role_assignment", "azurerm_user_assigned_identity"),
    "gcp": (
        "google_project_iam_",
        "google_service_account",
        "google_artifact_registry_repository_iam_",
        "google_storage_bucket_iam_",
    ),
}

_ACCESS_PREREQUISITES = {
    ("aws", "component.twin-state"): (
        "aws.iam-identity-center.primary-region",
        "manual_external",
    ),
    ("aws", "component.visualization"): (
        "aws.grafana.authentication",
        "manual_external",
    ),
    ("azure", "component.twin-state"): (
        "azure.microsoft-graph.authority",
        "manual_external",
    ),
    ("azure", "component.visualization"): (
        "azure.entra.runtime-access",
        "manual_external",
    ),
    ("gcp", "component.twin-state"): (
        "gcp.iap.oauth-configuration",
        "manual_external",
    ),
    ("gcp", "component.visualization"): (
        "gcp.iap.oauth-configuration",
        "manual_external",
    ),
}


def resolve_graph_requirements(
    nodes: Iterable[GraphNode],
    edges: Iterable[GraphEdge],
) -> tuple[GraphRequirement, ...]:
    """Compile deterministic prerequisites from exact graph ownership."""

    node_tuple = tuple(nodes)
    edge_tuple = tuple(edges)
    by_provider: dict[str, list[GraphNode]] = defaultdict(list)
    for node in node_tuple:
        by_provider[node.provider].append(node)

    collected: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def add(
        requirement_type: str,
        provider: str,
        capability_id: str,
        *,
        scope: str,
        preparation_mode: str,
        source_nodes: Iterable[str] = (),
        source_edges: Iterable[str] = (),
        region: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> None:
        key = (requirement_type, provider, capability_id, region)
        item = collected.setdefault(
            key,
            {
                "source_node_ids": set(),
                "source_edge_ids": set(),
                "attributes": {},
                "scope": scope,
                "preparation_mode": preparation_mode,
            },
        )
        if item["scope"] != scope or item["preparation_mode"] != preparation_mode:
            raise ValueError(
                f"Contradictory graph requirement declaration: {capability_id}"
            )
        item["source_node_ids"].update(source_nodes)
        item["source_edge_ids"].update(source_edges)
        for name, value in (attributes or {}).items():
            previous = item["attributes"].setdefault(name, value)
            if previous != value:
                raise ValueError(
                    f"Contradictory graph requirement attribute: {capability_id}.{name}"
                )

    for provider, provider_nodes in sorted(by_provider.items()):
        if provider not in _TARGET_SCOPE:
            raise ValueError(f"Unsupported graph provider: {provider}")
        node_ids = tuple(sorted(node.node_id for node in provider_nodes))
        resource_types_by_node = {
            node.node_id: tuple(
                sorted(
                    {
                        str(address).split(".", 1)[0]
                        for address in node.terraform["resource_addresses"]
                    }
                )
            )
            for node in provider_nodes
        }
        add(
            "provider_scope",
            provider,
            f"{provider}.target-scope",
            scope=_TARGET_SCOPE[provider],
            preparation_mode="none",
            source_nodes=node_ids,
            attributes={"target_type": _TARGET_SCOPE[provider]},
        )
        for region in sorted({node.region for node in provider_nodes}):
            add(
                "region",
                provider,
                f"{provider}.region.{region}",
                scope="region",
                preparation_mode="none",
                source_nodes=(
                    node.node_id for node in provider_nodes if node.region == region
                ),
                region=region,
            )
        for capability in sorted(
            {item for node in provider_nodes for item in node.permission_refs}
        ):
            add(
                "permission",
                provider,
                capability,
                scope=_TARGET_SCOPE[provider],
                preparation_mode="none",
                source_nodes=(
                    node.node_id
                    for node in provider_nodes
                    if capability in node.permission_refs
                ),
                attributes={
                    "terraform_resource_types": sorted(
                        {
                            resource_type
                            for node in provider_nodes
                            if capability in node.permission_refs
                            for resource_type in resource_types_by_node[node.node_id]
                        }
                    )
                },
            )

        if provider == "aws":
            _add_control_plane_requirements(
                add,
                provider,
                provider_nodes,
                resource_types_by_node,
                _AWS_CONTROL_PLANES,
                requirement_type="control_plane",
                preparation_mode="none",
            )
        elif provider == "azure":
            add(
                "resource_provider",
                provider,
                "Microsoft.Resources",
                scope="subscription",
                preparation_mode="confirmed_account",
                source_nodes=node_ids,
            )
            _add_control_plane_requirements(
                add,
                provider,
                provider_nodes,
                resource_types_by_node,
                _AZURE_RESOURCE_PROVIDERS,
                requirement_type="resource_provider",
                preparation_mode="confirmed_account",
            )
        else:
            for api in (
                "serviceusage.googleapis.com",
                "cloudresourcemanager.googleapis.com",
            ):
                add(
                    "api",
                    provider,
                    api,
                    scope="project",
                    preparation_mode="confirmed_account",
                    source_nodes=node_ids,
                )
            _add_control_plane_requirements(
                add,
                provider,
                provider_nodes,
                resource_types_by_node,
                _GCP_APIS,
                requirement_type="api",
                preparation_mode="confirmed_account",
            )
            if any(
                api == "artifactregistry.googleapis.com"
                for requirement_type, requirement_provider, api, _ in collected
                if requirement_type == "api" and requirement_provider == "gcp"
            ):
                artifact_registry_nodes = tuple(
                    sorted(
                        node.node_id
                        for node in provider_nodes
                        if any(
                            resource_type.startswith("google_artifact_registry")
                            for resource_type in resource_types_by_node[node.node_id]
                        )
                    )
                )
                add(
                    "api",
                    "gcp",
                    "cloudbuild.googleapis.com",
                    scope="project",
                    preparation_mode="confirmed_account",
                    source_nodes=artifact_registry_nodes,
                )

        selected_control_planes = {
            capability
            for requirement_type, requirement_provider, capability, _ in collected
            if requirement_provider == provider
            and requirement_type in {"api", "control_plane", "resource_provider"}
        }
        for capability in sorted(
            selected_control_planes & _QUOTA_CONTROL_PLANES[provider]
        ):
            add(
                "quota",
                provider,
                f"{provider}.quota.{capability}",
                scope="region",
                preparation_mode="manual_external",
                source_nodes=node_ids,
                region=provider_nodes[0].region,
                attributes={"control_plane": capability},
            )

        identity_nodes = [
            node.node_id
            for node in provider_nodes
            if any(
                resource_type.startswith(prefix)
                for resource_type in resource_types_by_node[node.node_id]
                for prefix in _IDENTITY_RESOURCE_PREFIXES[provider]
            )
        ]
        if identity_nodes:
            add(
                "runtime_identity",
                provider,
                f"{provider}.runtime-identity.terraform-managed",
                scope="twin",
                preparation_mode="terraform",
                source_nodes=identity_nodes,
            )

        for node in provider_nodes:
            prerequisite = _ACCESS_PREREQUISITES.get(
                (provider, node.logical_component_id)
            )
            if prerequisite is not None:
                capability, mode = prerequisite
                add(
                    "access_prerequisite",
                    provider,
                    capability,
                    scope=_TARGET_SCOPE[provider],
                    preparation_mode=mode,
                    source_nodes=(node.node_id,),
                    region=node.region,
                )
            if node.node_role == "architecture_component":
                add(
                    "verification_probe",
                    provider,
                    f"verify.{node.service_id}",
                    scope="twin",
                    preparation_mode="none",
                    source_nodes=(node.node_id,),
                    region=node.region,
                    attributes={
                        "logical_component_id": node.logical_component_id,
                        "observability_contract_id": str(
                            node.observability_ref.get("id", "")
                        ),
                    },
                )

    provider_by_node = {node.node_id: node.provider for node in node_tuple}
    for edge in edge_tuple:
        source_provider = provider_by_node[edge.source_node_id]
        destination_provider = provider_by_node[edge.destination_node_id]
        if edge.transfer_route_class != "cross_provider":
            continue
        exchange = IDENTITY_EXCHANGE_BY_PAIR.get(
            (source_provider, destination_provider)
        )
        if exchange is None:
            raise ValueError(
                "Resolved cross-provider graph edge has no reviewed identity exchange: "
                f"{source_provider}->{destination_provider}"
            )
        add(
            "workload_identity",
            source_provider,
            exchange,
            scope="twin",
            preparation_mode="terraform",
            source_edges=(edge.graph_edge_id,),
            attributes={"destination_provider": destination_provider},
        )
        if (source_provider, destination_provider) == ("aws", "azure"):
            add(
                "account_capability",
                "aws",
                "aws.outbound-identity-federation",
                scope="account",
                preparation_mode="confirmed_account",
                source_edges=(edge.graph_edge_id,),
                attributes={"destination_provider": "azure"},
            )
        add(
            "verification_probe",
            destination_provider,
            (
                f"verify.route.{source_provider}-to-{destination_provider}."
                f"{edge.logical_edge_id}"
            ),
            scope="twin",
            preparation_mode="none",
            source_edges=(edge.graph_edge_id,),
            attributes={
                "logical_edge_id": edge.logical_edge_id,
                "source_provider": source_provider,
                "destination_provider": destination_provider,
                "observability_contract_id": str(edge.observability_ref.get("id", "")),
            },
        )

    requirements = []
    for (requirement_type, provider, capability, region), item in sorted(
        collected.items()
    ):
        requirements.append(
            GraphRequirement(
                requirement_id=(
                    f"requirement.{requirement_type}.{provider}."
                    f"{_identifier(capability)}"
                    + (f".{_identifier(region)}" if region else "")
                ),
                requirement_type=requirement_type,
                provider=provider,
                capability_id=capability,
                scope=item["scope"],
                preparation_mode=item["preparation_mode"],
                mandatory=True,
                source_node_ids=tuple(sorted(item["source_node_ids"])),
                source_edge_ids=tuple(sorted(item["source_edge_ids"])),
                region=region,
                attributes=frozen_mapping(item["attributes"]),
            )
        )
    return tuple(requirements)


def _add_control_plane_requirements(
    add,
    provider: str,
    nodes: list[GraphNode],
    resource_types_by_node: dict[str, tuple[str, ...]],
    mapping: dict[str, str],
    *,
    requirement_type: str,
    preparation_mode: str,
) -> None:
    for prefix, capability in sorted(mapping.items()):
        source_nodes = [
            node.node_id
            for node in nodes
            if any(
                resource_type.startswith(prefix)
                for resource_type in resource_types_by_node[node.node_id]
            )
        ]
        if source_nodes:
            add(
                requirement_type,
                provider,
                capability,
                scope=_TARGET_SCOPE[provider],
                preparation_mode=preparation_mode,
                source_nodes=source_nodes,
            )


def _identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


__all__ = ["IDENTITY_EXCHANGE_BY_PAIR", "resolve_graph_requirements"]
