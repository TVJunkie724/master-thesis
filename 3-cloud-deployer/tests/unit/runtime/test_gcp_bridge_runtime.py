"""GCP source bridge wrapper tests without GCP calls."""

from __future__ import annotations

import base64
import json

import pytest

from src.runtime.eventing.bridge_core import BridgeContractError, load_routes
from src.runtime.eventing.gcp import runtime


def _route():
    return {
        "route_id": "route.gcp.aws.telemetry",
        "logical_edge_id": "edge.ingestion-to-processing",
        "source_provider": "gcp",
        "destination_provider": "aws",
        "execution_kind": "source_event_forwarder",
        "channel_class": "telemetry",
        "event_types": ["telemetry.received.v1"],
        "source_broker_kind": "telemetry_stream",
        "destination_broker_kind": "telemetry_stream",
        "identity_exchange": (
            "google_service_account_oidc_to_assume_role_with_web_identity"
        ),
        "payload_contract_id": "canonical-domain-event.v1",
        "trust_contract_id": "trust.workload-identity-federation",
    }


def _event():
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": "event-1",
        "event_type": "telemetry.received.v1",
        "deployment_id": "deployment-1",
        "source_id": "device-sensitive-id",
        "source_sequence": "1",
        "occurred_at": "2026-08-08T00:00:00Z",
        "correlation_id": "correlation-1",
        "causation_id": "causation-1",
        "producer": "component.device-ingress",
        "payload": {"device_id": "device-sensitive-id"},
    }


class _Future:
    def result(self, **configuration):
        assert configuration == {"timeout": 30}
        return "message-1"


class _Publisher:
    def __init__(self):
        self.requests = []

    def publish(self, *args, **configuration):
        self.requests.append((args, configuration))
        return _Future()


def test_failure_writer_uses_ordered_regional_pubsub_contract():
    publisher = _Publisher()
    writer = runtime.GcpFailureWriter(
        "projects/project-1/topics/bridge-failure",
        publisher,
    )
    failure = {
        "schema_version": "cross-cloud-bridge-failure.v1",
        "route_id": "route.gcp.aws.telemetry",
        "canonical_envelope": _event(),
    }

    assert writer(failure)
    args, configuration = publisher.requests[0]
    assert args[0] == "projects/project-1/topics/bridge-failure"
    assert json.loads(args[1]) == failure
    assert configuration["ordering_key"] != "device-sensitive-id"
    assert len(configuration["ordering_key"]) == 64


def test_failure_writer_rejects_custom_or_cross_project_topic_shapes():
    with pytest.raises(
        BridgeContractError,
        match="INVALID_FAILURE_DESTINATION_CONFIGURATION",
    ):
        runtime.GcpFailureWriter("https://proxy.example.test/topic", object())


class _Application:
    def __init__(self, routes, accepted=True):
        self.routes = routes
        self.accepted = accepted
        self.events = []

    def publish(self, route, event):
        self.events.append((route, event))
        return "message-1" if self.accepted else None


class _Request:
    def __init__(self, body):
        self.body = body

    def get_json(self, *, silent):
        assert silent is True
        return self.body


def _push_body():
    return {
        "message": {
            "messageId": "message-1",
            "data": base64.b64encode(json.dumps(_event()).encode()).decode(),
        },
        "deliveryAttempt": 1,
    }


def _configure(monkeypatch, *, accepted=True):
    raw_route = _route()
    app = _Application(load_routes([raw_route], source_provider="gcp"), accepted)
    monkeypatch.setattr(runtime, "_APPLICATION", app)
    monkeypatch.setattr(runtime, "_FAILURE_WRITER", lambda _failure: True)
    monkeypatch.setattr(runtime, "_CIRCUITS", {})
    monkeypatch.setenv("BRIDGE_ROUTES_JSON", json.dumps([raw_route]))
    return app


def test_push_returns_204_only_after_destination_acceptance(monkeypatch):
    app = _configure(monkeypatch)

    assert runtime.push_request(_Request(_push_body())) == ("", 204)
    assert app.events[0][1] == _event()


def test_push_returns_retryable_status_when_destination_does_not_accept(monkeypatch):
    _configure(monkeypatch, accepted=False)

    assert runtime.push_request(_Request(_push_body())) == ("", 503)


class _PullMessage:
    message_id = "message-1"
    data = json.dumps(_event()).encode()
    delivery_attempt = 1

    def __init__(self):
        self.acked = 0
        self.nacked = 0

    def ack(self):
        self.acked += 1

    def nack(self):
        self.nacked += 1


@pytest.mark.parametrize("accepted", [True, False])
def test_streaming_pull_settlement_follows_bridge_result(monkeypatch, accepted):
    _configure(monkeypatch, accepted=accepted)
    message = _PullMessage()

    runtime.streaming_pull_callback(message)

    assert (message.acked, message.nacked) == ((1, 0) if accepted else (0, 1))
