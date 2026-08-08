"""Provider-neutral contract tests for all Phase 8 bridge adapters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import itertools

import pytest

from src.runtime.eventing.bridge_core import (
    BridgeContractError,
    RetryableBridgeError,
    RouteBlockingBridgeError,
    RouteCircuitBreaker,
    SourceRecord,
    deliver_batch,
    load_routes,
    validate_event,
)


PROVIDERS = ("aws", "azure", "gcp")
IDENTITY_EXCHANGES = {
    ("aws", "azure"): "aws_oidc_to_entra_federated_credential",
    ("aws", "gcp"): "aws_subject_token_to_gcp_workload_identity_federation",
    ("azure", "aws"): "entra_managed_identity_oidc_to_assume_role_with_web_identity",
    ("azure", "gcp"): "entra_managed_identity_oidc_to_gcp_workload_identity_federation",
    ("gcp", "aws"): "google_service_account_oidc_to_assume_role_with_web_identity",
    ("gcp", "azure"): "google_service_account_oidc_to_entra_federated_credential",
}


def _route(source: str, destination: str, *events: str, channel="control"):
    broker = "telemetry_stream" if channel == "telemetry" else "control_topic"
    edge = "edge.processing-to-hot-storage"
    if events == ("device.command.outcome.v1",):
        edge = "edge.ingestion-to-hot-storage"
    elif events == ("telemetry.received.v1",):
        edge = "edge.ingestion-to-processing"
    return {
        "route_id": f"route.{source}.{destination}.{channel}",
        "logical_edge_id": edge,
        "source_provider": source,
        "destination_provider": destination,
        "execution_kind": "source_event_forwarder",
        "channel_class": channel,
        "event_types": list(events),
        "source_broker_kind": broker,
        "destination_broker_kind": broker,
        "identity_exchange": IDENTITY_EXCHANGES[(source, destination)],
        "payload_contract_id": "canonical-domain-event.v1",
        "trust_contract_id": "trust.workload-identity-federation",
    }


def _event(event_id: str, event_type="device.command.outcome.v1", source_id="d1"):
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": event_id,
        "event_type": event_type,
        "deployment_id": "deployment-1",
        "source_id": source_id,
        "source_sequence": event_id,
        "occurred_at": "2026-08-08T00:00:00Z",
        "correlation_id": event_id,
        "causation_id": event_id,
        "producer": "component.device-ingress",
        "payload": {"device_id": source_id, "status": "ACCEPTED"},
    }


@pytest.mark.parametrize(
    ("source", "destination"),
    [(a, b) for a, b in itertools.permutations(PROVIDERS, 2)],
)
def test_all_six_pairs_ack_only_after_destination_acceptance(source, destination):
    routes = load_routes(
        [_route(source, destination, "device.command.outcome.v1")],
        source_provider=source,
    )
    calls = []

    result = deliver_batch(
        [SourceRecord("record-1", _event("event-1"), 1)],
        routes,
        publish=lambda route, event: calls.append((route, event)) or "accepted-id",
        write_dlq=lambda _failure: False,
    )

    assert result.acknowledged_record_ids == ("record-1",)
    assert result.retry_record_ids == ()
    assert result.blocked_record_ids == ()
    assert result.blocked_route_ids == ()
    assert calls[0][0].destination_provider == destination


def test_retryable_failure_blocks_only_later_records_for_the_same_device():
    routes = load_routes(
        [_route("aws", "azure", "device.command.outcome.v1")],
        source_provider="aws",
    )
    published = []

    def publish(_route, event):
        published.append(event["event_id"])
        if event["event_id"] == "event-1":
            raise RetryableBridgeError("throttled")
        return "accepted"

    result = deliver_batch(
        [
            SourceRecord("record-1", _event("event-1", source_id="d1"), 1),
            SourceRecord("record-2", _event("event-2", source_id="d1"), 1),
            SourceRecord("record-3", _event("event-3", source_id="d2"), 1),
        ],
        routes,
        publish=publish,
        write_dlq=lambda _failure: False,
    )

    assert published == ["event-1", "event-3"]
    assert result.acknowledged_record_ids == ("record-3",)
    assert result.retry_record_ids == ("record-1", "record-2")


def test_terminal_schema_failure_acks_only_after_safe_dlq_acceptance():
    routes = load_routes(
        [_route("gcp", "aws", "device.command.outcome.v1")],
        source_provider="gcp",
    )
    invalid = _event("event-1")
    invalid["credential"] = "must-not-enter-the-dlq"
    failures = []
    fixed_time = datetime(2026, 8, 8, tzinfo=timezone.utc)

    result = deliver_batch(
        [SourceRecord("record-1", invalid, 1)],
        routes,
        publish=lambda _route, _event: pytest.fail("invalid event was published"),
        write_dlq=lambda failure: failures.append(failure) or True,
        now=lambda: fixed_time,
    )

    assert result.acknowledged_record_ids == ("record-1",)
    assert result.retry_record_ids == ()
    assert failures[0]["failure_code"] == "INVALID_CANONICAL_EVENT"
    assert failures[0]["canonical_envelope"] == {}
    assert failures[0]["source_provider"] == "gcp"
    assert failures[0]["destination_provider"] == "aws"
    assert set(failures[0]) == {
        "schema_version",
        "canonical_envelope",
        "source_provider",
        "destination_provider",
        "route_id",
        "attempt_count",
        "first_failure_at",
        "terminal_failure_at",
        "failure_code",
    }


def test_canonical_source_id_obeys_portable_128_byte_ordering_limit():
    assert validate_event(_event("event-1", source_id="d" * 128))["source_id"] == (
        "d" * 128
    )

    with pytest.raises(BridgeContractError, match="INVALID_CANONICAL_EVENT"):
        validate_event(_event("event-2", source_id="d" * 129))


def test_unknown_closed_event_is_terminal_but_known_unconfigured_route_blocks():
    routes = load_routes(
        [_route("aws", "gcp", "device.command.outcome.v1")],
        source_provider="aws",
    )
    failures = []

    unknown = deliver_batch(
        [SourceRecord("record-1", _event("event-1", "unknown.v1"), 1)],
        routes,
        publish=lambda _route, _event: pytest.fail("unknown event was published"),
        write_dlq=lambda failure: failures.append(failure) or True,
    )
    unconfigured = deliver_batch(
        [SourceRecord("record-2", _event("event-2", "telemetry.received.v1"), 1)],
        routes,
        publish=lambda _route, _event: pytest.fail("unconfigured event was published"),
        write_dlq=lambda _failure: pytest.fail("route fault entered the DLQ"),
    )

    assert unknown.acknowledged_record_ids == ("record-1",)
    assert failures[0]["failure_code"] == "UNKNOWN_EVENT_TYPE"
    assert failures[0]["canonical_envelope"]["event_id"] == "event-1"
    assert failures[0]["source_provider"] == "aws"
    assert unconfigured.blocked_record_ids == ("record-2",)
    assert unconfigured.blocked_route_ids == ("unresolved",)
    assert unconfigured.acknowledged_record_ids == ()
    assert unconfigured.retry_record_ids == ()


def test_route_blocking_publish_error_uses_safe_dlq_on_final_provider_attempt():
    routes = load_routes(
        [_route("azure", "aws", "device.command.outcome.v1")],
        source_provider="azure",
    )
    breakers = {}
    failures = []

    result = deliver_batch(
        [SourceRecord("record-1", _event("event-1"), 6)],
        routes,
        publish=lambda _route, _event: (_ for _ in ()).throw(
            RouteBlockingBridgeError("DESTINATION_PERMISSION_REJECTED")
        ),
        write_dlq=lambda failure: failures.append(failure) or True,
        circuit_breakers=breakers,
    )

    assert result.acknowledged_record_ids == ("record-1",)
    assert result.blocked_record_ids == ()
    assert result.blocked_route_ids == (routes[0].route_id,)
    assert breakers[routes[0].route_id].operator_blocked is True
    assert failures[0]["failure_code"] == "ROUTE_BLOCKED_ATTEMPTS_EXHAUSTED"


def test_route_blocking_publish_error_retries_before_final_provider_attempt():
    routes = load_routes(
        [_route("azure", "aws", "device.command.outcome.v1")],
        source_provider="azure",
    )

    result = deliver_batch(
        [SourceRecord("record-1", _event("event-1"), 5)],
        routes,
        publish=lambda _route, _event: (_ for _ in ()).throw(
            RouteBlockingBridgeError("DESTINATION_PERMISSION_REJECTED")
        ),
        write_dlq=lambda _failure: pytest.fail("route fault exhausted too early"),
    )

    assert result.acknowledged_record_ids == ()
    assert result.blocked_record_ids == ("record-1",)


def test_operator_blocked_route_is_probed_again_after_circuit_interval():
    breaker = RouteCircuitBreaker()
    blocked_at = datetime(2026, 8, 8, tzinfo=timezone.utc)

    breaker.block_for_operator(blocked_at)

    assert breaker.permits(blocked_at + timedelta(seconds=29)) is False
    assert breaker.permits(blocked_at + timedelta(seconds=30)) is True
    assert breaker.operator_blocked is False


def test_sixth_transient_attempt_moves_to_dlq_and_preserves_event_identity():
    routes = load_routes(
        [_route("azure", "gcp", "device.command.outcome.v1")],
        source_provider="azure",
    )
    failures = []

    result = deliver_batch(
        [SourceRecord("record-1", _event("event-1"), 6)],
        routes,
        publish=lambda _route, _event: (_ for _ in ()).throw(
            RetryableBridgeError("unavailable")
        ),
        write_dlq=lambda failure: failures.append(failure) or True,
    )

    assert result.acknowledged_record_ids == ("record-1",)
    assert failures[0]["failure_code"] == "DELIVERY_ATTEMPTS_EXHAUSTED"
    assert failures[0]["canonical_envelope"]["event_id"] == "event-1"


def test_circuit_opens_after_five_failures_and_recovers_after_30_seconds():
    routes = load_routes(
        [_route("gcp", "azure", "device.command.outcome.v1")],
        source_provider="gcp",
    )
    route_id = routes[0].route_id
    breakers = {route_id: RouteCircuitBreaker(consecutive_failures=4)}
    current = datetime(2026, 8, 8, tzinfo=timezone.utc)

    failed = deliver_batch(
        [SourceRecord("record-1", _event("event-1"), 1)],
        routes,
        publish=lambda _route, _event: (_ for _ in ()).throw(
            RetryableBridgeError("unavailable")
        ),
        write_dlq=lambda _failure: False,
        circuit_breakers=breakers,
        now=lambda: current,
    )
    blocked = deliver_batch(
        [SourceRecord("record-2", _event("event-2"), 1)],
        routes,
        publish=lambda _route, _event: pytest.fail("open circuit published"),
        write_dlq=lambda _failure: False,
        circuit_breakers=breakers,
        now=lambda: current + timedelta(seconds=29),
    )
    recovered = deliver_batch(
        [SourceRecord("record-3", _event("event-3"), 1)],
        routes,
        publish=lambda _route, _event: "accepted",
        write_dlq=lambda _failure: False,
        circuit_breakers=breakers,
        now=lambda: current + timedelta(seconds=30),
    )

    assert failed.retry_record_ids == ("record-1",)
    assert failed.blocked_route_ids == (route_id,)
    assert blocked.blocked_record_ids == ("record-2",)
    assert recovered.acknowledged_record_ids == ("record-3",)
    assert breakers[route_id].consecutive_failures == 0


def test_exact_96_kib_event_limit_is_enforced():
    event = _event("event-1")
    event["payload"] = {"value": "x" * (96 * 1024)}

    with pytest.raises(BridgeContractError, match="EVENT_TOO_LARGE"):
        validate_event(event)


@pytest.mark.parametrize(
    "forbidden_payload",
    [
        {"access_token": "nope"},
        {"nested": {"cloud_credentials": "nope"}},
        {"provider_resource_id": "nope"},
        {"arbitrary_http_headers": {"X-Api-Key": "nope"}},
    ],
)
def test_secret_or_provider_transport_metadata_never_reaches_publish(
    forbidden_payload,
):
    event = _event("event-1")
    event["payload"] = forbidden_payload

    with pytest.raises(BridgeContractError, match="INVALID_CANONICAL_EVENT"):
        validate_event(event)


def test_duplicate_event_owner_and_storage_or_tampered_route_are_rejected():
    duplicate = [
        _route("aws", "azure", "device.command.outcome.v1"),
        _route("aws", "gcp", "device.command.outcome.v1"),
    ]
    with pytest.raises(BridgeContractError, match="AMBIGUOUS"):
        load_routes(duplicate, source_provider="aws")

    storage = _route("aws", "azure", "device.command.outcome.v1")
    storage.update(
        execution_kind="finite_storage_job",
        channel_class="storage",
        event_types=[],
        source_broker_kind="object_storage",
        destination_broker_kind="object_storage",
    )
    with pytest.raises(BridgeContractError, match="INVALID_BRIDGE_ROUTE"):
        load_routes([storage], source_provider="aws")

    tampered = _route("aws", "azure", "device.command.outcome.v1")
    tampered["identity_exchange"] = "static_key"
    with pytest.raises(BridgeContractError, match="INVALID_BRIDGE_ROUTE"):
        load_routes([tampered], source_provider="aws")
