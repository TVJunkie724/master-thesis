"""Closed-world delivery core for the Phase 8 cross-cloud bridge.

Provider adapters own broker decoding, workload-identity exchange, destination
SDK clients, and source acknowledgement. This module owns the portable rules
that must remain identical for all six directed provider pairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from typing import Any, Callable, Mapping, MutableMapping, Sequence


MAX_EVENT_BYTES = 96 * 1024
MAX_SOURCE_ID_BYTES = 128
MAX_BATCH_EVENTS = 10
MAX_IN_MEMORY_EVENTS = 1000
MAX_DELIVERY_ATTEMPTS = 6
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_OPEN_SECONDS = 30
PROVIDERS = frozenset({"aws", "azure", "gcp"})
CANONICAL_FIELDS = frozenset(
    {
        "schema_version",
        "event_id",
        "event_type",
        "deployment_id",
        "source_id",
        "source_sequence",
        "occurred_at",
        "correlation_id",
        "causation_id",
        "producer",
        "payload",
    }
)
CANONICAL_EVENT_TYPES = frozenset(
    {
        "telemetry.received.v1",
        "telemetry.processed.v1",
        "event.matched.v1",
        "notification.requested.v1",
        "device.command.requested.v1",
        "extension.action.outcome.v1",
        "notification.workflow.outcome.v1",
        "device.command.outcome.v1",
        "twin.state.upserted",
        "twin.model.upserted",
        "twin.relationship.upserted",
        "twin.relationship.deleted",
    }
)
_EVENT_TYPES_BY_EDGE_CHANNEL = {
    ("edge.ingestion-to-processing", "telemetry"): frozenset(
        {"telemetry.received.v1"}
    ),
    ("edge.ingestion-to-hot-storage", "control"): frozenset(
        {"device.command.outcome.v1"}
    ),
    ("edge.processing-to-ingestion", "control"): frozenset(
        {"device.command.requested.v1"}
    ),
    ("edge.processing-to-hot-storage", "telemetry"): frozenset(
        {"telemetry.processed.v1"}
    ),
    ("edge.processing-to-hot-storage", "control"): frozenset(
        {
            "extension.action.outcome.v1",
            "notification.workflow.outcome.v1",
        }
    ),
    ("edge.hot-storage-to-twin-state", "control"): frozenset(
        {
            "twin.state.upserted",
            "twin.model.upserted",
            "twin.relationship.upserted",
            "twin.relationship.deleted",
        }
    ),
}
_IDENTITY_EXCHANGE_BY_PAIR = {
    ("aws", "azure"): "aws_oidc_to_entra_federated_credential",
    ("aws", "gcp"): "aws_subject_token_to_gcp_workload_identity_federation",
    ("azure", "aws"): "entra_managed_identity_oidc_to_assume_role_with_web_identity",
    ("azure", "gcp"): "entra_managed_identity_oidc_to_gcp_workload_identity_federation",
    ("gcp", "aws"): "google_service_account_oidc_to_assume_role_with_web_identity",
    ("gcp", "azure"): "google_service_account_oidc_to_entra_federated_credential",
}
_TERMINAL_CODES = frozenset(
    {
        "INVALID_CANONICAL_EVENT",
        "UNSUPPORTED_EVENT_SCHEMA",
        "UNKNOWN_EVENT_TYPE",
        "EVENT_TOO_LARGE",
        "DESTINATION_PAYLOAD_REJECTED",
        "DELIVERY_ATTEMPTS_EXHAUSTED",
        "ROUTE_BLOCKED_ATTEMPTS_EXHAUSTED",
    }
)
_ROUTE_BLOCKING_CODES = frozenset(
    {
        "ROUTE_NOT_CONFIGURED",
        "ROUTE_MISMATCH",
        "TLS_ENDPOINT_REJECTED",
        "IDENTITY_CLAIM_REJECTED",
        "DESTINATION_PERMISSION_REJECTED",
        "CIRCUIT_OPEN",
    }
)
_FORBIDDEN_METADATA_FRAGMENTS = (
    "authorization",
    "cloud_credential",
    "credential",
    "deployment_url",
    "http_header",
    "provider_resource",
    "raw_exception",
    "secret",
    "terraform_name",
    "token",
)


class BridgeContractError(ValueError):
    """Stable, payload-free bridge contract failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class RetryableBridgeError(RuntimeError):
    """A transient identity, network, throttling, or destination failure."""


class TerminalBridgeError(RuntimeError):
    """A bounded message rejection that must enter the source bridge DLQ."""

    def __init__(self, code: str):
        if code not in _TERMINAL_CODES:
            raise ValueError("Unknown terminal bridge failure code")
        super().__init__(code)
        self.code = code


class RouteBlockingBridgeError(RuntimeError):
    """A route/trust/permission fault requiring operator correction."""

    def __init__(self, code: str):
        if code not in _ROUTE_BLOCKING_CODES:
            raise ValueError("Unknown route-blocking bridge failure code")
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class BridgeRoute:
    """One source-owned event route compiled from the immutable graph."""

    route_id: str
    logical_edge_id: str
    source_provider: str
    destination_provider: str
    channel_class: str
    event_types: tuple[str, ...]
    identity_exchange: str
    payload_contract_id: str
    trust_contract_id: str


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """One durable source-broker record and its provider delivery attempt."""

    record_id: str
    event: Mapping[str, Any]
    attempt_count: int
    first_failure_at: str | None = None


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Provider adapter instructions after one bounded bridge invocation."""

    acknowledged_record_ids: tuple[str, ...]
    retry_record_ids: tuple[str, ...]
    blocked_record_ids: tuple[str, ...]
    blocked_route_ids: tuple[str, ...]


@dataclass(slots=True)
class RouteCircuitBreaker:
    """Warm-runtime route circuit with the frozen five-failure/30-second rule."""

    consecutive_failures: int = 0
    open_until: datetime | None = None
    operator_blocked: bool = False

    def permits(self, at: datetime) -> bool:
        at = _aware_utc(at)
        if self.operator_blocked:
            if self.open_until is None or at < self.open_until:
                return False
            self.operator_blocked = False
            self.open_until = None
            self.consecutive_failures = 0
            return True
        if self.open_until is None:
            return True
        if at < self.open_until:
            return False
        self.open_until = None
        self.consecutive_failures = 0
        return True

    def destination_accepted(self) -> None:
        self.consecutive_failures = 0
        self.open_until = None

    def destination_failed(self, at: datetime) -> bool:
        self.consecutive_failures += 1
        if self.consecutive_failures < CIRCUIT_FAILURE_THRESHOLD:
            return False
        self.open_until = _aware_utc(at) + timedelta(seconds=CIRCUIT_OPEN_SECONDS)
        return True

    def block_for_operator(self, at: datetime) -> None:
        self.operator_blocked = True
        self.open_until = _aware_utc(at) + timedelta(seconds=CIRCUIT_OPEN_SECONDS)

    def reset_after_operator_correction(self) -> None:
        self.consecutive_failures = 0
        self.open_until = None
        self.operator_blocked = False


def load_routes(
    raw_routes: object,
    *,
    source_provider: str,
) -> tuple[BridgeRoute, ...]:
    """Validate event-only Terraform routes for one source runtime."""

    if source_provider not in PROVIDERS or not isinstance(raw_routes, list):
        raise BridgeContractError("INVALID_BRIDGE_ROUTE_CONFIGURATION")
    routes: list[BridgeRoute] = []
    event_owners: dict[str, str] = {}
    for value in raw_routes:
        if not isinstance(value, Mapping):
            raise BridgeContractError("INVALID_BRIDGE_ROUTE_CONFIGURATION")
        required = {
            "route_id",
            "logical_edge_id",
            "source_provider",
            "destination_provider",
            "execution_kind",
            "channel_class",
            "event_types",
            "source_broker_kind",
            "destination_broker_kind",
            "identity_exchange",
            "payload_contract_id",
            "trust_contract_id",
        }
        if set(value) != required:
            raise BridgeContractError("INVALID_BRIDGE_ROUTE_CONFIGURATION")
        events = value.get("event_types")
        route_source = value.get("source_provider")
        destination = value.get("destination_provider")
        channel = value.get("channel_class")
        logical_edge = value.get("logical_edge_id")
        broker = "telemetry_stream" if channel == "telemetry" else "control_topic"
        expected_events = _EVENT_TYPES_BY_EDGE_CHANNEL.get((logical_edge, channel))
        expected_payload = (
            "twin_projection.v1"
            if logical_edge == "edge.hot-storage-to-twin-state"
            else "canonical-domain-event.v1"
        )
        if (
            value.get("execution_kind") != "source_event_forwarder"
            or route_source != source_provider
            or destination not in PROVIDERS
            or destination == route_source
            or channel not in {"telemetry", "control"}
            or value.get("source_broker_kind") != broker
            or value.get("destination_broker_kind") != broker
            or not isinstance(events, list)
            or not events
            or any(not isinstance(item, str) or not item for item in events)
            or frozenset(events) != expected_events
            or len(events) != len(expected_events or ())
            or value.get("identity_exchange")
            != _IDENTITY_EXCHANGE_BY_PAIR.get((route_source, destination))
            or value.get("trust_contract_id")
            != "trust.workload-identity-federation"
            or value.get("payload_contract_id") != expected_payload
        ):
            raise BridgeContractError("INVALID_BRIDGE_ROUTE_CONFIGURATION")
        route_id = _text(value.get("route_id"))
        for event_type in events:
            if event_type in event_owners:
                raise BridgeContractError("AMBIGUOUS_BRIDGE_EVENT_ROUTE")
            event_owners[event_type] = route_id
        routes.append(
            BridgeRoute(
                route_id=route_id,
                logical_edge_id=_text(logical_edge),
                source_provider=source_provider,
                destination_provider=str(destination),
                channel_class=str(channel),
                event_types=tuple(events),
                identity_exchange=_text(value.get("identity_exchange")),
                payload_contract_id=str(value.get("payload_contract_id")),
                trust_contract_id=str(value.get("trust_contract_id")),
            )
        )
    return tuple(sorted(routes, key=lambda item: item.route_id))


def load_routes_json(raw: str, *, source_provider: str) -> tuple[BridgeRoute, ...]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise BridgeContractError("INVALID_BRIDGE_ROUTE_CONFIGURATION") from exc
    return load_routes(value, source_provider=source_provider)


def validate_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return one bounded canonical event or raise a safe terminal code."""

    if not isinstance(event, Mapping) or set(event) != CANONICAL_FIELDS:
        raise BridgeContractError("INVALID_CANONICAL_EVENT")
    if event.get("schema_version") != "canonical-domain-event.v1":
        raise BridgeContractError("UNSUPPORTED_EVENT_SCHEMA")
    if event.get("event_type") not in CANONICAL_EVENT_TYPES:
        raise BridgeContractError("UNKNOWN_EVENT_TYPE")
    for field in CANONICAL_FIELDS - {"payload", "occurred_at", "source_id"}:
        _text(event.get(field), code="INVALID_CANONICAL_EVENT", maximum=256)
    _text(
        event.get("source_id"),
        code="INVALID_CANONICAL_EVENT",
        maximum=MAX_SOURCE_ID_BYTES,
    )
    _parse_utc(event.get("occurred_at"))
    if not isinstance(event.get("payload"), Mapping):
        raise BridgeContractError("INVALID_CANONICAL_EVENT")
    if _contains_forbidden_metadata(event):
        raise BridgeContractError("INVALID_CANONICAL_EVENT")
    try:
        encoded = _canonical_bytes(event)
    except (TypeError, ValueError) as exc:
        raise BridgeContractError("INVALID_CANONICAL_EVENT") from exc
    if len(encoded) > MAX_EVENT_BYTES:
        raise BridgeContractError("EVENT_TOO_LARGE")
    return dict(event)


def deliver_batch(
    records: Sequence[SourceRecord],
    routes: Sequence[BridgeRoute],
    *,
    publish: Callable[[BridgeRoute, Mapping[str, Any]], object],
    write_dlq: Callable[[Mapping[str, Any]], bool],
    circuit_breakers: MutableMapping[str, RouteCircuitBreaker] | None = None,
    now: Callable[[], datetime] | None = None,
) -> BatchResult:
    """Deliver records and acknowledge only destination or source-DLQ acceptance.

    Message failures enter the safe source failure store. Route, trust, and
    permission failures remain separately observable, retry without source
    acknowledgement, and use the same bounded provider attempt budget.
    """

    if len(records) > MAX_IN_MEMORY_EVENTS:
        raise BridgeContractError("BRIDGE_BACKPRESSURE_LIMIT")
    if len(records) > MAX_BATCH_EVENTS:
        raise BridgeContractError("BRIDGE_BATCH_LIMIT")
    route_by_event = {
        event_type: route for route in routes for event_type in route.event_types
    }
    if len(route_by_event) != sum(len(route.event_types) for route in routes):
        raise BridgeContractError("AMBIGUOUS_BRIDGE_EVENT_ROUTE")
    clock = now or (lambda: datetime.now(timezone.utc))
    breakers = circuit_breakers if circuit_breakers is not None else {}
    acknowledged: list[str] = []
    retry: list[str] = []
    blocked: list[str] = []
    blocked_routes: set[str] = set()
    blocked_keys: set[str] = set()
    source_provider = routes[0].source_provider if routes else "unknown"
    for record in records:
        _validate_source_record(record)
        source_key = _safe_source_key(record.event)
        if source_key in blocked_keys:
            retry.append(record.record_id)
            continue
        route = route_by_event.get(
            str(record.event.get("event_type", ""))
            if isinstance(record.event, Mapping)
            else ""
        )
        try:
            event = validate_event(record.event)
            if route is None:
                raise RouteBlockingBridgeError("ROUTE_NOT_CONFIGURED")
            breaker = breakers.setdefault(route.route_id, RouteCircuitBreaker())
            current_time = _aware_utc(clock())
            if not breaker.permits(current_time):
                raise RouteBlockingBridgeError("CIRCUIT_OPEN")
            accepted = publish(route, event)
            if accepted is None or accepted is False:
                raise RetryableBridgeError("DESTINATION_NOT_ACCEPTED")
            breaker.destination_accepted()
            acknowledged.append(record.record_id)
            continue
        except BridgeContractError as exc:
            terminal_code = exc.code
        except TerminalBridgeError as exc:
            terminal_code = exc.code
        except RouteBlockingBridgeError as exc:
            route_id = route.route_id if route is not None else "unresolved"
            if route is not None and exc.code != "CIRCUIT_OPEN":
                breakers.setdefault(route_id, RouteCircuitBreaker()).block_for_operator(
                    clock()
                )
            blocked_routes.add(route_id)
            if record.attempt_count < MAX_DELIVERY_ATTEMPTS:
                blocked.append(record.record_id)
                blocked_keys.add(source_key)
                continue
            terminal_code = "ROUTE_BLOCKED_ATTEMPTS_EXHAUSTED"
        except RetryableBridgeError:
            if _record_retryable_failure(
                record, route, breakers, retry, blocked_routes, clock()
            ):
                blocked_keys.add(source_key)
                continue
            terminal_code = "DELIVERY_ATTEMPTS_EXHAUSTED"
        except Exception:
            if _record_retryable_failure(
                record, route, breakers, retry, blocked_routes, clock()
            ):
                blocked_keys.add(source_key)
                continue
            terminal_code = "DELIVERY_ATTEMPTS_EXHAUSTED"

        failure = _failure_record(
            record,
            route,
            terminal_code,
            clock(),
            source_provider=source_provider,
        )
        try:
            dlq_accepted = write_dlq(failure)
        except Exception:
            dlq_accepted = False
        if dlq_accepted:
            acknowledged.append(record.record_id)
        else:
            retry.append(record.record_id)
            blocked_keys.add(source_key)
    return BatchResult(
        tuple(acknowledged),
        tuple(retry),
        tuple(blocked),
        tuple(sorted(blocked_routes)),
    )


def _record_retryable_failure(
    record: SourceRecord,
    route: BridgeRoute | None,
    breakers: MutableMapping[str, RouteCircuitBreaker],
    retry: list[str],
    blocked_routes: set[str],
    at: datetime,
) -> bool:
    if route is not None:
        breaker = breakers.setdefault(route.route_id, RouteCircuitBreaker())
        if breaker.destination_failed(_aware_utc(at)):
            blocked_routes.add(route.route_id)
    if record.attempt_count < MAX_DELIVERY_ATTEMPTS:
        retry.append(record.record_id)
        return True
    return False


def _failure_record(
    record: SourceRecord,
    route: BridgeRoute | None,
    code: str,
    terminal_at: datetime,
    *,
    source_provider: str,
) -> dict[str, Any]:
    if code not in _TERMINAL_CODES:
        code = "INVALID_CANONICAL_EVENT"
    timestamp = _iso(terminal_at)
    first_failure = record.first_failure_at or timestamp
    envelope = _safe_canonical_envelope(record.event)
    return {
        "schema_version": "cross-cloud-bridge-failure.v1",
        "canonical_envelope": envelope,
        "source_provider": route.source_provider if route else source_provider,
        "destination_provider": route.destination_provider if route else "unknown",
        "route_id": route.route_id if route else "unresolved",
        "attempt_count": record.attempt_count,
        "first_failure_at": first_failure,
        "terminal_failure_at": timestamp,
        "failure_code": code,
    }


def _safe_canonical_envelope(event: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(event, Mapping) or set(event) != CANONICAL_FIELDS:
        return {}
    if _contains_forbidden_metadata(event):
        return {}
    try:
        encoded = _canonical_bytes(event)
    except (TypeError, ValueError):
        return {}
    if len(encoded) > MAX_EVENT_BYTES:
        return {}
    return dict(event)


def _contains_forbidden_metadata(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(fragment in normalized for fragment in _FORBIDDEN_METADATA_FRAGMENTS):
                return True
            if _contains_forbidden_metadata(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_metadata(child) for child in value)
    return False


def _validate_source_record(record: SourceRecord) -> None:
    _text(record.record_id, code="INVALID_SOURCE_RECORD", maximum=512)
    if (
        isinstance(record.attempt_count, bool)
        or not isinstance(record.attempt_count, int)
        or record.attempt_count < 1
        or record.attempt_count > MAX_DELIVERY_ATTEMPTS
    ):
        raise BridgeContractError("INVALID_SOURCE_RECORD")
    if record.first_failure_at is not None:
        _parse_utc(record.first_failure_at, code="INVALID_SOURCE_RECORD")


def _safe_source_key(event: Mapping[str, Any]) -> str:
    value = event.get("source_id") if isinstance(event, Mapping) else None
    return value if isinstance(value, str) and value else "__invalid__"


def _text(
    value: object,
    *,
    code: str = "INVALID_BRIDGE_ROUTE_CONFIGURATION",
    maximum: int = 512,
) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise BridgeContractError(code)
    return value


def _parse_utc(value: object, *, code: str = "INVALID_CANONICAL_EVENT") -> datetime:
    if not isinstance(value, str) or not value or len(value) > 35:
        raise BridgeContractError(code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BridgeContractError(code) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise BridgeContractError(code)
    return parsed.astimezone(timezone.utc)


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if any(
        isinstance(item, float) and not math.isfinite(item)
        for item in _nested_values(value)
    ):
        raise ValueError("Non-finite number")
    return encoded


def _nested_values(value: object):
    if isinstance(value, Mapping):
        for child in value.values():
            yield child
            yield from _nested_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield child
            yield from _nested_values(child)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Bridge timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _aware_utc(value).isoformat().replace("+00:00", "Z")


__all__ = [
    "BatchResult",
    "BridgeContractError",
    "BridgeRoute",
    "RouteBlockingBridgeError",
    "RouteCircuitBreaker",
    "RetryableBridgeError",
    "SourceRecord",
    "TerminalBridgeError",
    "deliver_batch",
    "load_routes",
    "load_routes_json",
    "validate_event",
]
