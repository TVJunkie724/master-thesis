"""Typed, non-secret Terraform projection of resolved cross-cloud edges."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.architecture_profiles import ResolvedDeploymentGraph


IDENTITY_EXCHANGE_BY_PAIR = {
    ("aws", "azure"): "aws_oidc_to_entra_federated_credential",
    ("aws", "gcp"): "aws_subject_token_to_gcp_workload_identity_federation",
    ("azure", "aws"): "entra_managed_identity_oidc_to_assume_role_with_web_identity",
    ("azure", "gcp"): "entra_managed_identity_oidc_to_gcp_workload_identity_federation",
    ("gcp", "aws"): "google_service_account_oidc_to_assume_role_with_web_identity",
    ("gcp", "azure"): "google_service_account_oidc_to_entra_federated_credential",
}

_STORAGE_EDGE_IDS = frozenset(
    {
        "edge.hot-to-cool-storage",
        "edge.cool-to-archive-storage",
    }
)

_PAYLOAD_CONTRACT_BY_EDGE = {
    "edge.cool-to-archive-storage": "storage_transition.v1",
    "edge.hot-storage-to-twin-state": "twin_projection.v1",
    "edge.hot-to-cool-storage": "storage_transition.v1",
    "edge.ingestion-to-hot-storage": "canonical-domain-event.v1",
    "edge.ingestion-to-processing": "canonical-domain-event.v1",
    "edge.processing-to-hot-storage": "canonical-domain-event.v1",
    "edge.processing-to-ingestion": "canonical-domain-event.v1",
    "edge.ingestion-to-eventing": "canonical-domain-event.v1",
    "edge.eventing-to-processing": "canonical-domain-event.v1",
    "edge.processing-to-eventing": "canonical-domain-event.v1",
    "edge.eventing-to-ingestion": "canonical-domain-event.v1",
}

_EVENT_CHANNELS_BY_EDGE: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "edge.ingestion-to-processing": (
        ("telemetry", ("telemetry.received.v1",)),
    ),
    "edge.ingestion-to-hot-storage": (
        ("control", ("device.command.outcome.v1",)),
    ),
    "edge.processing-to-ingestion": (
        ("control", ("device.command.requested.v1",)),
    ),
    "edge.processing-to-hot-storage": (
        ("telemetry", ("telemetry.processed.v1",)),
        (
            "control",
            (
                "extension.action.outcome.v1",
                "notification.workflow.outcome.v1",
            ),
        ),
    ),
    "edge.hot-storage-to-twin-state": (
        (
            "control",
            (
                "twin.state.upserted",
                "twin.model.upserted",
                "twin.relationship.upserted",
                "twin.relationship.deleted",
            ),
        ),
    ),
    "edge.ingestion-to-eventing": (
        ("telemetry", ("telemetry.received.v1",)),
        ("control", ("device.command.outcome.v1",)),
    ),
    "edge.eventing-to-processing": (
        (
            "telemetry",
            ("telemetry.received.v1", "telemetry.processed.v1"),
        ),
        (
            "control",
            (
                "event.matched.v1",
                "notification.requested.v1",
                "extension.action.outcome.v1",
                "notification.workflow.outcome.v1",
                "device.command.outcome.v1",
            ),
        ),
    ),
    "edge.processing-to-eventing": (
        ("telemetry", ("telemetry.processed.v1",)),
        (
            "control",
            (
                "event.matched.v1",
                "notification.requested.v1",
                "device.command.requested.v1",
                "extension.action.outcome.v1",
                "notification.workflow.outcome.v1",
            ),
        ),
    ),
    "edge.eventing-to-ingestion": (
        ("control", ("device.command.requested.v1",)),
    ),
}

_BROKER_KIND_BY_CHANNEL = {
    "telemetry": "telemetry_stream",
    "control": "control_topic",
    "storage": "object_storage",
}


@dataclass(frozen=True, slots=True)
class CrossCloudRoute:
    """One graph-owned route without credentials or generated endpoints."""

    route_id: str
    logical_edge_id: str
    source_provider: str
    destination_provider: str
    execution_kind: str
    channel_class: str
    event_types: tuple[str, ...]
    source_broker_kind: str
    destination_broker_kind: str
    identity_exchange: str
    payload_contract_id: str
    trust_contract_id: str

    def to_tfvar(self) -> dict[str, Any]:
        return asdict(self)


def resolve_cross_cloud_routes(
    graph: "ResolvedDeploymentGraph | None",
) -> tuple[CrossCloudRoute, ...]:
    """Compile all and only resolved cross-provider edges for Terraform."""

    if graph is None:
        return ()

    providers_by_node = {node.node_id: node.provider for node in graph.nodes}
    routes: list[CrossCloudRoute] = []
    for edge in graph.edges:
        if edge.transfer_route_class != "cross_provider":
            continue
        source = providers_by_node.get(edge.source_node_id, "")
        destination = providers_by_node.get(edge.destination_node_id, "")
        exchange = IDENTITY_EXCHANGE_BY_PAIR.get((source, destination))
        if exchange is None:
            raise ValueError(
                "Resolved cross-cloud edge has no approved directed identity "
                f"exchange: {source or '<missing>'}->{destination or '<missing>'}"
            )
        if edge.logical_edge_id in _STORAGE_EDGE_IDS:
            channels = (("storage", ()),)
        else:
            channels = _EVENT_CHANNELS_BY_EDGE.get(edge.logical_edge_id, ())
            if not channels:
                raise ValueError(
                    "Resolved cross-cloud edge has no approved channel route: "
                    f"{edge.logical_edge_id}"
                )
        expected_payload = _PAYLOAD_CONTRACT_BY_EDGE[edge.logical_edge_id]
        if (
            edge.payload_ref.get("id") != expected_payload
            or edge.trust_ref.get("id") != "trust.workload-identity-federation"
        ):
            raise ValueError(
                "Resolved cross-cloud edge violates its approved payload or trust "
                f"contract: {edge.logical_edge_id}"
            )
        for channel_class, event_types in channels:
            broker_kind = _BROKER_KIND_BY_CHANNEL[channel_class]
            routes.append(
                CrossCloudRoute(
                    route_id=f"{edge.graph_edge_id}.{channel_class}",
                    logical_edge_id=edge.logical_edge_id,
                    source_provider=source,
                    destination_provider=destination,
                    execution_kind=(
                        "finite_storage_job"
                        if channel_class == "storage"
                        else "source_event_forwarder"
                    ),
                    channel_class=channel_class,
                    event_types=event_types,
                    source_broker_kind=broker_kind,
                    destination_broker_kind=broker_kind,
                    identity_exchange=exchange,
                    payload_contract_id=str(edge.payload_ref.get("id", "")),
                    trust_contract_id=str(edge.trust_ref.get("id", "")),
                )
            )
    return tuple(sorted(routes, key=lambda route: route.route_id))


def cross_cloud_route_tfvars(
    graph: "ResolvedDeploymentGraph | None",
) -> dict[str, Any]:
    return {
        "resolved_cross_cloud_routes": [
            route.to_tfvar() for route in resolve_cross_cloud_routes(graph)
        ]
    }


__all__ = [
    "CrossCloudRoute",
    "IDENTITY_EXCHANGE_BY_PAIR",
    "cross_cloud_route_tfvars",
    "resolve_cross_cloud_routes",
]
