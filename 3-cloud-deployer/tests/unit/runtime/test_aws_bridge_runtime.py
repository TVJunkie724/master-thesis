"""AWS source bridge wrapper tests without AWS calls."""

from __future__ import annotations

import base64
import json

import pytest

from src.runtime.eventing.aws import runtime
from src.runtime.eventing.bridge_core import BridgeContractError, load_routes


IDENTITY = {
    ("aws", "azure"): "aws_oidc_to_entra_federated_credential",
    ("aws", "gcp"): "aws_subject_token_to_gcp_workload_identity_federation",
}


def _route(destination, channel):
    telemetry = channel == "telemetry"
    return {
        "route_id": f"route.aws.{destination}.{channel}",
        "logical_edge_id": (
            "edge.ingestion-to-processing"
            if telemetry
            else "edge.ingestion-to-hot-storage"
        ),
        "source_provider": "aws",
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
        "identity_exchange": IDENTITY[("aws", destination)],
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


class _S3:
    def __init__(self):
        self.requests = []

    def put_object(self, **request):
        self.requests.append(request)
        return {"ETag": '"etag"'}


class _Sqs:
    def __init__(self):
        self.requests = []

    def send_message(self, **request):
        self.requests.append(request)
        return {"MessageId": "message-1"}


def test_failure_writer_uses_s3_for_telemetry_and_fifo_for_control():
    routes = load_routes(
        [_route("azure", "telemetry"), _route("gcp", "control")],
        source_provider="aws",
    )
    s3 = _S3()
    sqs = _Sqs()
    writer = runtime.AwsFailureWriter(
        routes,
        telemetry_bucket="twin-bridge-failures",
        control_queue_url=(
            "https://sqs.eu-central-1.amazonaws.com/123456789012/bridge-failure.fifo"
        ),
        s3_client=s3,
        sqs_client=sqs,
    )
    common = {
        "schema_version": "cross-cloud-bridge-failure.v1",
        "canonical_envelope": _event("telemetry.received.v1"),
        "attempt_count": 1,
    }

    assert writer({**common, "route_id": routes[0].route_id})
    assert s3.requests[0]["Bucket"] == "twin-bridge-failures"
    assert s3.requests[0]["Key"].startswith("bridge-failures/")
    assert s3.requests[0]["ContentType"] == "application/json"

    assert writer({**common, "route_id": routes[1].route_id})
    request = sqs.requests[0]
    assert request["QueueUrl"].endswith("bridge-failure.fifo")
    assert request["MessageGroupId"] != "device-sensitive-id"
    assert len(request["MessageGroupId"]) == 64
    assert len(request["MessageDeduplicationId"]) == 64


def test_failure_writer_rejects_missing_or_nonregional_destinations():
    routes = load_routes([_route("gcp", "control")], source_provider="aws")

    with pytest.raises(
        BridgeContractError,
        match="INVALID_FAILURE_DESTINATION_CONFIGURATION",
    ):
        runtime.AwsFailureWriter(
            routes,
            telemetry_bucket="",
            control_queue_url=(
                "https://sqs.us-east-1.amazonaws.com/123456789012/failure.fifo"
            ),
            s3_client=object(),
            sqs_client=object(),
        )


class _Application:
    def __init__(self, routes):
        self.routes = routes
        self.events = []

    def publish(self, route, event):
        self.events.append((route, event))
        return "accepted"


def test_lambda_handler_returns_partial_batch_protocol_after_acceptance(
    monkeypatch,
):
    raw_route = _route("azure", "telemetry")
    routes = load_routes([raw_route], source_provider="aws")
    app = _Application(routes)
    monkeypatch.setattr(runtime, "_APPLICATION", app)
    monkeypatch.setattr(runtime, "_FAILURE_WRITER", lambda _failure: True)
    monkeypatch.setattr(runtime, "_CIRCUITS", {})
    monkeypatch.setenv("BRIDGE_ROUTES_JSON", json.dumps([raw_route]))
    event = _event("telemetry.received.v1")
    invocation = {
        "Records": [
            {
                "eventSource": "aws:kinesis",
                "eventID": "shard:1",
                "kinesis": {
                    "data": base64.b64encode(json.dumps(event).encode()).decode()
                },
            }
        ]
    }

    assert runtime.lambda_handler(invocation, object()) == {"batchItemFailures": []}
    assert app.events[0][1] == event
