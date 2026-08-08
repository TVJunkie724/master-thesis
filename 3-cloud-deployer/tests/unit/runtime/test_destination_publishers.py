"""Destination data-plane publisher contract tests without cloud calls."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.runtime.eventing.bridge_core import (
    RetryableBridgeError,
    RouteBlockingBridgeError,
    TerminalBridgeError,
    load_routes,
)
from src.runtime.eventing.destination_publishers import (
    AwsDestinationPublisher,
    AzureDestinationPublisher,
    GcpDestinationPublisher,
    load_destination,
    raise_safe_publish_error,
)


IDENTITY = {
    ("gcp", "aws"): "google_service_account_oidc_to_assume_role_with_web_identity",
    ("aws", "azure"): "aws_oidc_to_entra_federated_credential",
    ("azure", "gcp"): "entra_managed_identity_oidc_to_gcp_workload_identity_federation",
}


def _route(source: str, destination: str, *, channel: str):
    telemetry = channel == "telemetry"
    event_type = "telemetry.received.v1" if telemetry else "device.command.outcome.v1"
    edge = "edge.ingestion-to-processing" if telemetry else "edge.ingestion-to-hot-storage"
    return load_routes(
        [
            {
                "route_id": f"route.{source}.{destination}.{channel}",
                "logical_edge_id": edge,
                "source_provider": source,
                "destination_provider": destination,
                "execution_kind": "source_event_forwarder",
                "channel_class": channel,
                "event_types": [event_type],
                "source_broker_kind": "telemetry_stream" if telemetry else "control_topic",
                "destination_broker_kind": "telemetry_stream" if telemetry else "control_topic",
                "identity_exchange": IDENTITY[(source, destination)],
                "payload_contract_id": "canonical-domain-event.v1",
                "trust_contract_id": "trust.workload-identity-federation",
            }
        ],
        source_provider=source,
    )[0]


def _event(event_id: str, *, telemetry: bool) -> dict:
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": event_id,
        "event_type": "telemetry.received.v1" if telemetry else "device.command.outcome.v1",
        "deployment_id": "deployment-1",
        "source_id": "device-1",
        "source_sequence": event_id,
        "occurred_at": "2026-08-08T00:00:00Z",
        "correlation_id": event_id,
        "causation_id": event_id,
        "producer": "component.device-ingress",
        "payload": {"device_id": "device-1", "status": "ACCEPTED"},
    }


def test_destination_configuration_rejects_custom_or_cross_region_endpoints():
    with pytest.raises(RouteBlockingBridgeError, match="TLS_ENDPOINT_REJECTED"):
        load_destination(
            {
                "telemetry_topic": "projects/project-1/topics/telemetry",
                "control_topic": "projects/project-1/topics/control",
                "api_endpoint": "proxy.example.test",
            },
            provider="gcp",
        )
    with pytest.raises(RouteBlockingBridgeError, match="TLS_ENDPOINT_REJECTED"):
        load_destination(
            {
                "telemetry_stream_arn": "arn:aws:kinesis:us-east-1:123456789012:stream/events",
                "control_topic_arn": "arn:aws:sns:eu-central-1:123456789012:control.fifo",
            },
            provider="aws",
        )


def test_destination_configuration_does_not_require_an_unused_channel_service():
    destination = load_destination(
        {
            "telemetry_stream_arn": "arn:aws:kinesis:eu-central-1:123456789012:stream/events"
        },
        provider="aws",
    )

    assert destination.telemetry_stream_arn.endswith("stream/events")
    assert destination.control_topic_arn == ""


class _Kinesis:
    def __init__(self):
        self.requests = []

    def put_record(self, **request):
        self.requests.append(request)
        return {"ShardId": "shard-1", "SequenceNumber": str(len(self.requests))}


class _Sns:
    def __init__(self):
        self.requests = []

    def publish(self, **request):
        self.requests.append(request)
        return {"MessageId": "message-1", "SequenceNumber": "1"}


def test_aws_publisher_uses_kinesis_sequence_chain_and_sns_fifo_identity():
    destination = load_destination(
        {
            "telemetry_stream_arn": "arn:aws:kinesis:eu-central-1:123456789012:stream/events",
            "control_topic_arn": "arn:aws:sns:eu-central-1:123456789012:control.fifo",
        },
        provider="aws",
    )
    kinesis = _Kinesis()
    sns = _Sns()
    clients = {"kinesis": kinesis, "sns": sns}
    publisher = AwsDestinationPublisher(destination, clients.__getitem__)
    telemetry_route = _route("gcp", "aws", channel="telemetry")

    assert publisher.publish(telemetry_route, _event("event-1", telemetry=True)) == "1"
    assert publisher.publish(telemetry_route, _event("event-2", telemetry=True)) == "2"
    assert kinesis.requests[1]["SequenceNumberForOrdering"] == "1"
    assert kinesis.requests[1]["PartitionKey"] == "device-1"

    assert (
        publisher.publish(
            _route("gcp", "aws", channel="control"),
            _event("event-3", telemetry=False),
        )
        == "message-1"
    )
    assert sns.requests[0]["MessageGroupId"] == "device-1"
    assert len(sns.requests[0]["MessageDeduplicationId"]) == 64


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

    def get_topic_sender(self, **_configuration):
        return self.sender


def test_azure_publisher_uses_non_buffered_sdk_acceptance_and_sessions():
    destination = load_destination(
        {
            "telemetry_namespace": "twin01.servicebus.windows.net",
            "telemetry_entity": "telemetry",
            "control_namespace": "twin01.servicebus.windows.net",
            "control_entity": "control",
        },
        provider="azure",
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

    publisher = AzureDestinationPublisher(
        destination,
        object(),
        event_hub_factory=event_hub_factory,
        event_data_factory=lambda data: ("event", data),
        service_bus_factory=service_bus_factory,
        service_bus_message_factory=lambda data, **metadata: (data, metadata),
    )

    assert publisher.publish(
        _route("aws", "azure", channel="telemetry"),
        _event("event-1", telemetry=True),
    )
    assert event_hubs[0].configuration["buffered_mode"] is False
    assert event_hubs[0].sent[0][1]["partition_key"] == "device-1"

    assert publisher.publish(
        _route("aws", "azure", channel="control"),
        _event("event-2", telemetry=False),
    )
    assert service_buses[0].sender.sent[0][1]["session_id"] == "device-1"


class _Future:
    def __init__(self, result="message-1", error=None):
        self._result = result
        self._error = error

    def result(self, **_configuration):
        if self._error:
            raise self._error
        return self._result


class _Publisher:
    def __init__(self, error=None):
        self.error = error
        self.requests = []
        self.resumed = []

    def publish(self, *args, **configuration):
        self.requests.append((args, configuration))
        return _Future(error=self.error)

    def resume_publish(self, *args):
        self.resumed.append(args)


def test_gcp_publisher_waits_for_message_id_and_resumes_failed_ordering_key():
    destination = load_destination(
        {
            "telemetry_topic": "projects/project-1/topics/telemetry",
            "control_topic": "projects/project-1/topics/control",
            "api_endpoint": "europe-west1-pubsub.googleapis.com",
        },
        provider="gcp",
    )
    publisher_client = _Publisher()
    publisher = GcpDestinationPublisher(destination, publisher_client)

    assert (
        publisher.publish(
            _route("azure", "gcp", channel="telemetry"),
            _event("event-1", telemetry=True),
        )
        == "message-1"
    )
    assert publisher_client.requests[0][1]["ordering_key"] == "device-1"

    publisher_client.error = TimeoutError()
    with pytest.raises(RetryableBridgeError):
        publisher.publish(
            _route("azure", "gcp", channel="control"),
            _event("event-2", telemetry=False),
        )
    assert publisher_client.resumed == [
        ("projects/project-1/topics/control", "device-1")
    ]


@dataclass
class _ProviderError(Exception):
    status_code: int


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (403, RouteBlockingBridgeError),
        (413, TerminalBridgeError),
        (429, RetryableBridgeError),
        (503, RetryableBridgeError),
    ],
)
def test_provider_errors_map_to_bounded_failure_classes(status, expected):
    with pytest.raises(expected):
        raise_safe_publish_error(_ProviderError(status))
