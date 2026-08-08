"""Azure source bridge wrapper tests without Azure calls."""

from __future__ import annotations

import json

import pytest

from src.runtime.eventing.azure import runtime
from src.runtime.eventing.bridge_core import RetryableBridgeError, load_routes
from src.runtime.eventing.destination_publishers import AzureDestination


IDENTITY = {
    "aws": "entra_managed_identity_oidc_to_assume_role_with_web_identity",
    "gcp": "entra_managed_identity_oidc_to_gcp_workload_identity_federation",
}


def _route(destination, channel):
    telemetry = channel == "telemetry"
    return {
        "route_id": f"route.azure.{destination}.{channel}",
        "logical_edge_id": (
            "edge.ingestion-to-processing"
            if telemetry
            else "edge.ingestion-to-hot-storage"
        ),
        "source_provider": "azure",
        "destination_provider": destination,
        "execution_kind": "source_event_forwarder",
        "channel_class": channel,
        "event_types": [
            "telemetry.received.v1" if telemetry else "device.command.outcome.v1"
        ],
        "source_broker_kind": "telemetry_stream" if telemetry else "control_topic",
        "destination_broker_kind": (
            "telemetry_stream" if telemetry else "control_topic"
        ),
        "identity_exchange": IDENTITY[destination],
        "payload_contract_id": "canonical-domain-event.v1",
        "trust_contract_id": "trust.workload-identity-federation",
    }


def _event(event_type):
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": "event-1",
        "event_type": event_type,
        "deployment_id": "deployment-1",
        "source_id": "device-sensitive-id",
        "source_sequence": "1",
        "occurred_at": "2026-08-08T00:00:00Z",
        "correlation_id": "correlation-1",
        "causation_id": "causation-1",
        "producer": "component.device-ingress",
        "payload": {"device_id": "device-sensitive-id"},
    }


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _EventHub(_Context):
    def __init__(self, **configuration):
        self.configuration = configuration
        self.sent = []

    def send_batch(self, messages, **configuration):
        self.sent.append((messages, configuration))


class _Sender(_Context):
    def __init__(self):
        self.sent = []

    def send_messages(self, message):
        self.sent.append(message)


class _ServiceBus(_Context):
    def __init__(self, **configuration):
        self.configuration = configuration
        self.sender = _Sender()

    def get_queue_sender(self, **configuration):
        self.queue_configuration = configuration
        return self.sender


def test_failure_writer_routes_safe_records_by_channel():
    routes = load_routes(
        [_route("aws", "telemetry"), _route("gcp", "control")],
        source_provider="azure",
    )
    event_hubs = []
    service_buses = []

    def event_hub_factory(**configuration):
        client = _EventHub(**configuration)
        event_hubs.append(client)
        return client

    def service_bus_factory(**configuration):
        client = _ServiceBus(**configuration)
        service_buses.append(client)
        return client

    writer = runtime.AzureFailureWriter(
        routes,
        AzureDestination(
            telemetry_namespace="failure.servicebus.windows.net",
            telemetry_entity="telemetry-failure",
            control_namespace="failure.servicebus.windows.net",
            control_entity="control-failure",
        ),
        object(),
        event_hub_factory=event_hub_factory,
        event_data_factory=lambda data: ("event", data),
        service_bus_factory=service_bus_factory,
        service_bus_message_factory=lambda data, **metadata: (data, metadata),
    )
    common = {
        "schema_version": "cross-cloud-bridge-failure.v1",
        "canonical_envelope": _event("telemetry.received.v1"),
    }

    assert writer({**common, "route_id": routes[0].route_id})
    assert event_hubs[0].configuration["buffered_mode"] is False
    assert event_hubs[0].sent[0][1]["partition_key"] != "device-sensitive-id"

    assert writer({**common, "route_id": routes[1].route_id})
    assert service_buses[0].queue_configuration == {
        "queue_name": "control-failure"
    }
    metadata = service_buses[0].sender.sent[0][1]
    assert len(metadata["message_id"]) == 64
    assert metadata["session_id"] != "device-sensitive-id"


class _Application:
    def __init__(self, routes, accepted=True):
        self.routes = routes
        self.accepted = accepted

    def publish(self, _route, _event):
        return "accepted" if self.accepted else None


class _EventHubMessage:
    sequence_number = 1

    def get_body(self):
        return json.dumps(_event("telemetry.received.v1")).encode()


class _ServiceBusMessage:
    message_id = "message-1"
    delivery_count = 1

    def get_body(self):
        return json.dumps(_event("device.command.outcome.v1")).encode()


def _configure(monkeypatch, raw_route, *, accepted=True):
    routes = load_routes([raw_route], source_provider="azure")
    monkeypatch.setattr(runtime, "_APPLICATION", _Application(routes, accepted))
    monkeypatch.setattr(runtime, "_FAILURE_WRITER", lambda _failure: True)
    monkeypatch.setattr(runtime, "_CIRCUITS", {})
    monkeypatch.setenv("BRIDGE_ROUTES_JSON", json.dumps([raw_route]))


def test_event_hub_batch_returns_only_after_acceptance(monkeypatch):
    _configure(monkeypatch, _route("aws", "telemetry"))

    assert runtime.event_hub_batch([_EventHubMessage()]) is None


def test_event_hub_final_retry_is_acknowledged_after_failure_store(monkeypatch):
    _configure(monkeypatch, _route("aws", "telemetry"), accepted=False)

    assert runtime.event_hub_batch([_EventHubMessage()], attempt_count=6) is None


def test_service_bus_trigger_retries_when_target_did_not_accept(monkeypatch):
    _configure(monkeypatch, _route("gcp", "control"), accepted=False)

    with pytest.raises(RetryableBridgeError, match="SOURCE_NOT_ACKNOWLEDGED"):
        runtime.service_bus_message(_ServiceBusMessage())
