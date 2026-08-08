"""Source-broker adapter tests for the three shared bridge runtimes."""

from __future__ import annotations

import base64
import json

import pytest

from src.runtime.eventing.aws import bridge as aws_bridge
from src.runtime.eventing.azure import bridge as azure_bridge
from src.runtime.eventing.bridge_core import (
    BridgeContractError,
    RetryableBridgeError,
    RouteBlockingBridgeError,
)
from src.runtime.eventing.gcp import bridge as gcp_bridge


IDENTITY_EXCHANGE = {
    ("aws", "azure"): "aws_oidc_to_entra_federated_credential",
    ("azure", "gcp"): "entra_managed_identity_oidc_to_gcp_workload_identity_federation",
    ("gcp", "aws"): "google_service_account_oidc_to_assume_role_with_web_identity",
}


def _event(event_id: str = "event-1") -> dict:
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": event_id,
        "event_type": "device.command.outcome.v1",
        "deployment_id": "deployment-1",
        "source_id": "device-1",
        "source_sequence": event_id,
        "occurred_at": "2026-08-08T00:00:00Z",
        "correlation_id": event_id,
        "causation_id": event_id,
        "producer": "component.device-ingress",
        "payload": {"device_id": "device-1", "status": "ACCEPTED"},
    }


def _routes(source: str, destination: str) -> str:
    return json.dumps(
        [
            {
                "route_id": f"route.{source}.{destination}.control",
                "logical_edge_id": "edge.ingestion-to-hot-storage",
                "source_provider": source,
                "destination_provider": destination,
                "execution_kind": "source_event_forwarder",
                "channel_class": "control",
                "event_types": ["device.command.outcome.v1"],
                "source_broker_kind": "control_topic",
                "destination_broker_kind": "control_topic",
                "identity_exchange": IDENTITY_EXCHANGE[(source, destination)],
                "payload_contract_id": "canonical-domain-event.v1",
                "trust_contract_id": "trust.workload-identity-federation",
            }
        ]
    )


def _encoded_event() -> str:
    return base64.b64encode(json.dumps(_event()).encode()).decode()


def test_aws_kinesis_batch_acks_only_accepted_destination_record():
    event = {
        "Records": [
            {
                "eventSource": "aws:kinesis",
                "eventID": "shard:1",
                "kinesis": {"data": _encoded_event()},
            }
        ]
    }

    response = aws_bridge.handle_batch(
        event,
        routes_json=_routes("aws", "azure"),
        publish=lambda route, value: route.destination_provider == "azure"
        and value["event_id"],
        write_dlq=lambda _failure: False,
    )

    assert response == {"batchItemFailures": []}


def test_aws_sqs_unwraps_sns_and_returns_retry_as_partial_failure():
    body = json.dumps({"Type": "Notification", "Message": json.dumps(_event())})
    event = {
        "Records": [
            {
                "eventSource": "aws:sqs",
                "messageId": "message-1",
                "attributes": {"ApproximateReceiveCount": "3"},
                "body": body,
            }
        ]
    }

    response = aws_bridge.handle_batch(
        event,
        routes_json=_routes("aws", "azure"),
        publish=lambda _route, _value: (_ for _ in ()).throw(
            RetryableBridgeError("throttled")
        ),
        write_dlq=lambda _failure: False,
    )

    assert response == {"batchItemFailures": [{"itemIdentifier": "message-1"}]}


class _EventHubMessage:
    sequence_number = 42

    def get_body(self):
        return json.dumps(_event()).encode()


class _ServiceBusMessage:
    message_id = "service-bus-1"
    delivery_count = 8

    def __iter__(self):
        yield json.dumps(_event()).encode()


def test_azure_event_hub_result_requires_wrapper_retry_when_route_is_blocked():
    result = azure_bridge.handle_event_hub_batch(
        [_EventHubMessage()],
        routes_json=_routes("azure", "gcp"),
        publish=lambda _route, _value: (_ for _ in ()).throw(
            RouteBlockingBridgeError("DESTINATION_PERMISSION_REJECTED")
        ),
        write_dlq=lambda _failure: False,
    )

    assert result.acknowledged_record_ids == ()
    assert result.blocked_record_ids == ("42",)


def test_azure_event_hub_passes_final_function_retry_to_delivery_core():
    failures = []
    result = azure_bridge.handle_event_hub_batch(
        [_EventHubMessage()],
        attempt_count=6,
        routes_json=_routes("azure", "gcp"),
        publish=lambda _route, _value: (_ for _ in ()).throw(
            RetryableBridgeError("unavailable")
        ),
        write_dlq=lambda failure: not failures.append(failure),
    )

    assert result.acknowledged_record_ids == ("42",)
    assert result.retry_record_ids == ()
    assert failures[0]["failure_code"] == "DELIVERY_ATTEMPTS_EXHAUSTED"


def test_azure_service_bus_caps_provider_delivery_attempt_at_contract_limit():
    decoded = azure_bridge.decode_service_bus_record(_ServiceBusMessage())

    assert decoded.record_id == "service-bus-1"
    assert decoded.attempt_count == 6
    assert decoded.event == _event()


def test_gcp_push_acks_only_after_destination_acceptance():
    body = {
        "message": {"messageId": "pubsub-1", "data": _encoded_event()},
        "deliveryAttempt": 2,
    }

    result = gcp_bridge.handle_push(
        body,
        routes_json=_routes("gcp", "aws"),
        publish=lambda route, _value: route.destination_provider == "aws",
        write_dlq=lambda _failure: False,
    )

    assert result.acknowledged_record_ids == ("pubsub-1",)
    assert result.retry_record_ids == ()


class _StreamingPullMessage:
    message_id = "pull-1"
    data = json.dumps(_event()).encode()
    delivery_attempt = 3


def test_gcp_streaming_pull_returns_retry_without_acknowledging():
    result = gcp_bridge.handle_streaming_pull(
        _StreamingPullMessage(),
        routes_json=_routes("gcp", "aws"),
        publish=lambda _route, _value: (_ for _ in ()).throw(
            RetryableBridgeError("unavailable")
        ),
        write_dlq=lambda _failure: False,
    )

    assert result.acknowledged_record_ids == ()
    assert result.retry_record_ids == ("pull-1",)


@pytest.mark.parametrize(
    "decode",
    [
        lambda: aws_bridge.decode_records({"Records": []}),
        lambda: azure_bridge.decode_event_hub_records([]),
        lambda: gcp_bridge.decode_push({"message": {"messageId": "x"}}),
    ],
)
def test_source_adapters_reject_invalid_provider_envelopes_without_payload_echo(decode):
    with pytest.raises(BridgeContractError, match="INVALID_SOURCE_RECORD"):
        decode()
