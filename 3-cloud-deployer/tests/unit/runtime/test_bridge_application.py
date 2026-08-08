"""Bridge application composition tests without cloud calls."""

from __future__ import annotations

import json

import pytest

from src.runtime.eventing import bridge_application as application
from src.runtime.eventing.bridge_core import (
    BridgeContractError,
    RouteBlockingBridgeError,
)


TENANT_ID = "11111111-1111-4111-8111-111111111111"
CLIENT_ID = "22222222-2222-4222-8222-222222222222"
BRIDGE_AUDIENCE = "api://33333333-3333-4333-8333-333333333333"
PROVIDER_AUDIENCE = (
    "//iam.googleapis.com/projects/123456789012/locations/global/"
    "workloadIdentityPools/twin-pool/providers/source-bridge"
)
IMPERSONATION_URL = (
    "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
    "bridge@project-1.iam.gserviceaccount.com:generateAccessToken"
)
IDENTITY_EXCHANGE = {
    ("aws", "azure"): "aws_oidc_to_entra_federated_credential",
    ("aws", "gcp"): "aws_subject_token_to_gcp_workload_identity_federation",
    ("azure", "aws"): "entra_managed_identity_oidc_to_assume_role_with_web_identity",
    ("azure", "gcp"): "entra_managed_identity_oidc_to_gcp_workload_identity_federation",
    ("gcp", "aws"): "google_service_account_oidc_to_assume_role_with_web_identity",
    ("gcp", "azure"): "google_service_account_oidc_to_entra_federated_credential",
}


def _route(source, destination):
    return {
        "route_id": f"graph.{source}.{destination}.telemetry",
        "logical_edge_id": "edge.ingestion-to-processing",
        "source_provider": source,
        "destination_provider": destination,
        "execution_kind": "source_event_forwarder",
        "channel_class": "telemetry",
        "event_types": ["telemetry.received.v1"],
        "source_broker_kind": "telemetry_stream",
        "destination_broker_kind": "telemetry_stream",
        "identity_exchange": IDENTITY_EXCHANGE[(source, destination)],
        "payload_contract_id": "canonical-domain-event.v1",
        "trust_contract_id": "trust.workload-identity-federation",
    }


def _destination(provider):
    if provider == "aws":
        return {
            "telemetry_stream_arn": (
                "arn:aws:kinesis:eu-central-1:123456789012:stream/events"
            )
        }
    if provider == "azure":
        return {
            "telemetry_namespace": "twin01.servicebus.windows.net",
            "telemetry_entity": "telemetry",
        }
    return {"telemetry_topic": "projects/project-1/topics/telemetry"}


def _identity(source, destination):
    if destination == "aws":
        return {
            "role_arn": "arn:aws:iam::123456789012:role/twin-bridge",
            "assertion_audience": BRIDGE_AUDIENCE,
        }
    if destination == "azure":
        return {"tenant_id": TENANT_ID, "client_id": CLIENT_ID}
    value = {
        "provider_audience": PROVIDER_AUDIENCE,
        "service_account_impersonation_url": IMPERSONATION_URL,
    }
    if source == "azure":
        value["source_assertion_audience"] = BRIDGE_AUDIENCE
    return value


class _Publisher:
    def __init__(self, provider, *configuration):
        self.provider = provider
        self.configuration = configuration
        self.calls = []

    def publish(self, route, event):
        self.calls.append((route, event))
        return f"accepted-{self.provider}"


@pytest.fixture
def composition_fakes(monkeypatch):
    calls = []

    def supplier(kind):
        def create(*args):
            value = (kind, args)
            calls.append(value)
            return value

        return create

    monkeypatch.setattr(
        application,
        "AwsOutboundAssertionSupplier",
        supplier("aws-outbound-assertion"),
    )
    monkeypatch.setattr(
        application,
        "AzureManagedIdentityAssertionSupplier",
        supplier("azure-managed-identity-assertion"),
    )
    monkeypatch.setattr(
        application,
        "GoogleIdTokenAssertionSupplier",
        supplier("google-id-token-assertion"),
    )
    monkeypatch.setattr(
        application,
        "AwsAssumeRoleClientFactory",
        supplier("aws-assume-role-factory"),
    )
    monkeypatch.setattr(
        application,
        "build_azure_credential",
        supplier("azure-client-assertion-credential"),
    )

    def gcp_credentials(target, **configuration):
        value = ("gcp-wif-credential", target, configuration)
        calls.append(value)
        return value

    monkeypatch.setattr(application, "build_gcp_credentials", gcp_credentials)
    monkeypatch.setattr(
        application,
        "_gcp_publisher",
        supplier("gcp-ordered-publisher-client"),
    )
    monkeypatch.setattr(
        application,
        "AwsDestinationPublisher",
        lambda *args: _Publisher("aws", *args),
    )
    monkeypatch.setattr(
        application,
        "AzureDestinationPublisher",
        lambda *args: _Publisher("azure", *args),
    )
    monkeypatch.setattr(
        application,
        "GcpDestinationPublisher",
        lambda *args: _Publisher("gcp", *args),
    )
    return calls


@pytest.mark.parametrize("source,destination", sorted(IDENTITY_EXCHANGE))
def test_every_directed_pair_composes_only_its_official_identity_and_sdk_path(
    source,
    destination,
    composition_fakes,
):
    source_identity = (
        {"managed_identity_client_id": CLIENT_ID} if source == "azure" else {}
    )
    bridge = application.build_bridge_application(
        source_provider=source,
        routes_json=json.dumps([_route(source, destination)]),
        destinations_json=json.dumps({destination: _destination(destination)}),
        identities_json=json.dumps({destination: _identity(source, destination)}),
        source_identity_json=json.dumps(source_identity),
    )

    route = bridge.routes[0]
    assert bridge.publish(route, {"event_id": "event-1"}) == (
        f"accepted-{destination}"
    )
    assert bridge.source_provider == source
    assert {route.destination_provider for route in bridge.routes} == {destination}

    call_kinds = {value[0] for value in composition_fakes}
    if destination == "aws":
        assert "aws-assume-role-factory" in call_kinds
    elif destination == "azure":
        assert "azure-client-assertion-credential" in call_kinds
    else:
        assert "gcp-wif-credential" in call_kinds
        assert "gcp-ordered-publisher-client" in call_kinds


def test_one_source_application_supports_two_remote_destination_providers(
    composition_fakes,
):
    routes = [_route("azure", "aws"), _route("azure", "gcp")]
    # Distinct event ownership is mandatory inside one source runtime.
    routes[1].update(
        {
            "route_id": "graph.azure.gcp.control",
            "logical_edge_id": "edge.ingestion-to-hot-storage",
            "channel_class": "control",
            "event_types": ["device.command.outcome.v1"],
            "source_broker_kind": "control_topic",
            "destination_broker_kind": "control_topic",
        }
    )
    destinations = {
        provider: _destination(provider) for provider in ("aws", "gcp")
    }
    destinations["gcp"] = {
        "control_topic": "projects/project-1/topics/control"
    }

    bridge = application.build_bridge_application(
        source_provider="azure",
        routes_json=json.dumps(routes),
        destinations_json=json.dumps(destinations),
        identities_json=json.dumps(
            {
                provider: _identity("azure", provider)
                for provider in ("aws", "gcp")
            }
        ),
        source_identity_json=json.dumps(
            {"managed_identity_client_id": CLIENT_ID}
        ),
    )

    assert {route.destination_provider for route in bridge.routes} == {"aws", "gcp"}
    assert len(composition_fakes) >= 4


def test_configuration_rejects_missing_extra_or_same_cloud_targets(
    composition_fakes,
):
    route = _route("aws", "azure")
    with pytest.raises(
        BridgeContractError,
        match="INVALID_BRIDGE_ROUTE_CONFIGURATION",
    ):
        application.build_bridge_application(
            source_provider="aws",
            routes_json=json.dumps([route]),
            destinations_json=json.dumps({}),
            identities_json=json.dumps({"azure": _identity("aws", "azure")}),
        )
    with pytest.raises(BridgeContractError, match="INVALID_IDENTITY_CONFIGURATION"):
        application.build_bridge_application(
            source_provider="aws",
            routes_json=json.dumps([route]),
            destinations_json=json.dumps({"azure": _destination("azure")}),
            identities_json=json.dumps({"azure": _identity("aws", "azure")}),
            source_identity_json=json.dumps(
                {"managed_identity_client_id": CLIENT_ID}
            ),
        )


def test_application_blocks_a_route_from_another_source(composition_fakes):
    bridge = application.build_bridge_application(
        source_provider="aws",
        routes_json=json.dumps([_route("aws", "azure")]),
        destinations_json=json.dumps({"azure": _destination("azure")}),
        identities_json=json.dumps({"azure": _identity("aws", "azure")}),
    )
    foreign = application.load_routes_json(
        json.dumps([_route("gcp", "azure")]),
        source_provider="gcp",
    )[0]

    with pytest.raises(RouteBlockingBridgeError, match="ROUTE_MISMATCH"):
        bridge.publish(foreign, {})
