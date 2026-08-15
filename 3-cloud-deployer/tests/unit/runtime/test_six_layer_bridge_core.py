"""Six-layer fan-out tests for the Event-Layer-owned bridge runtime."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.runtime.six_layer_eventing.bridge_core import (
    BridgeContractError,
    RetryableBridgeError,
    RouteCircuitBreaker,
    SourceRecord,
    deliver_batch,
    load_routes,
)


IDENTITY_EXCHANGES = {
    ("aws", "azure"): "aws_oidc_to_entra_federated_credential",
    ("aws", "gcp"): "aws_subject_token_to_gcp_workload_identity_federation",
}


def _route(
    destination: str,
    logical_edge_id: str,
    *,
    route_id: str,
) -> dict[str, object]:
    return {
        "route_id": route_id,
        "logical_edge_id": logical_edge_id,
        "source_provider": "aws",
        "destination_provider": destination,
        "execution_kind": "source_event_forwarder",
        "channel_class": "telemetry",
        "event_types": [
            "telemetry.received.v1",
            "telemetry.processed.v1",
        ]
        if logical_edge_id == "edge.eventing-to-processing"
        else ["telemetry.processed.v1"],
        "source_broker_kind": "telemetry_stream",
        "destination_broker_kind": "telemetry_stream",
        "identity_exchange": IDENTITY_EXCHANGES[("aws", destination)],
        "payload_contract_id": "canonical-domain-event.v1",
        "trust_contract_id": "trust.workload-identity-federation",
    }


def _event() -> dict[str, object]:
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": "event-1",
        "event_type": "telemetry.processed.v1",
        "deployment_id": "deployment-1",
        "source_id": "device-1",
        "source_sequence": "1",
        "occurred_at": "2026-08-14T00:00:00Z",
        "correlation_id": "correlation-1",
        "causation_id": "causation-1",
        "producer": "component.processing",
        "payload": {"temperature": 21.5},
    }


def _fanout_routes():
    return load_routes(
        [
            _route(
                "azure",
                "edge.eventing-to-processing",
                route_id="route.event-to-processing.telemetry",
            ),
            _route(
                "gcp",
                "edge.eventing-to-hot-storage",
                route_id="route.event-to-hot.telemetry",
            ),
        ],
        source_provider="aws",
    )


def test_processed_event_fans_out_to_distinct_processing_and_hot_providers():
    calls: list[str] = []

    result = deliver_batch(
        [SourceRecord("record-1", _event(), 1)],
        _fanout_routes(),
        publish=lambda route, _event: (
            calls.append(route.destination_provider) or "accepted"
        ),
        write_dlq=lambda _failure: False,
    )

    assert result.acknowledged_record_ids == ("record-1",)
    assert calls == ["azure", "gcp"]


def test_processed_event_retries_until_every_destination_accepts():
    calls: list[str] = []

    def publish(route, _event):
        calls.append(route.destination_provider)
        if route.destination_provider == "gcp":
            raise RetryableBridgeError("unavailable")
        return "accepted"

    result = deliver_batch(
        [SourceRecord("record-1", _event(), 1)],
        _fanout_routes(),
        publish=publish,
        write_dlq=lambda _failure: False,
        now=lambda: datetime(2026, 8, 14, tzinfo=timezone.utc),
    )

    assert result.acknowledged_record_ids == ()
    assert result.retry_record_ids == ("record-1",)
    assert calls == ["azure", "gcp"]


def test_same_provider_and_channel_share_one_landing_publish():
    routes = load_routes(
        [
            _route(
                "azure",
                "edge.eventing-to-processing",
                route_id="route.event-to-processing.telemetry",
            ),
            _route(
                "azure",
                "edge.eventing-to-hot-storage",
                route_id="route.event-to-hot.telemetry",
            ),
        ],
        source_provider="aws",
    )
    breakers = {
        route.route_id: RouteCircuitBreaker(consecutive_failures=3) for route in routes
    }
    calls: list[str] = []

    result = deliver_batch(
        [SourceRecord("record-1", _event(), 1)],
        routes,
        publish=lambda route, _event: calls.append(route.route_id) or "accepted",
        write_dlq=lambda _failure: False,
        circuit_breakers=breakers,
    )

    assert result.acknowledged_record_ids == ("record-1",)
    assert len(calls) == 1
    assert all(breaker.consecutive_failures == 0 for breaker in breakers.values())


def test_duplicate_route_identity_remains_fail_closed():
    duplicate = [
        _route(
            "azure",
            "edge.eventing-to-processing",
            route_id="route.duplicate.telemetry",
        ),
        _route(
            "gcp",
            "edge.eventing-to-hot-storage",
            route_id="route.duplicate.telemetry",
        ),
    ]

    with pytest.raises(BridgeContractError, match="AMBIGUOUS_BRIDGE_EVENT_ROUTE"):
        load_routes(duplicate, source_provider="aws")
