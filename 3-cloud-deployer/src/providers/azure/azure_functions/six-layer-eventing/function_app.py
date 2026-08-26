"""Azure delivery adapter for the independent Six-layer Event Layer.

Event Hubs owns replayable telemetry and one consumer group per independent
consumer. Service Bus owns ordered low-rate control delivery and its native
dead-letter queue. The only HTTP hop is an authenticated same-cloud handoff to
the Azure Six-layer domain runtime; cross-cloud traffic still lands on a
provider broker first.
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import azure.functions as func


SCHEMA_VERSION = "canonical-domain-event.v1"
TELEMETRY_RECEIVED = "telemetry.received.v1"
TELEMETRY_PROCESSED = "telemetry.processed.v1"
REQUIRED_FIELDS = {
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
SUPPORTED_EVENT_TYPES = {
    TELEMETRY_RECEIVED,
    TELEMETRY_PROCESSED,
    "twin.state.upserted",
    "event.matched.v1",
    "notification.requested.v1",
    "extension.action.outcome.v1",
    "notification.workflow.outcome.v1",
    "device.command.requested.v1",
    "device.command.outcome.v1",
}
PROCESSED_ROLES = {
    "historical-persistence",
    "twin-state-update",
    "rule-evaluator",
    "audit",
    "realtime-visualization",
}
MAX_EVENT_BYTES = 96 * 1024
MAX_RESPONSE_BYTES = 4096


class DeliveryError(ValueError):
    """Stable payload-free delivery failure."""


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _decode(value: bytes | bytearray | Iterable[bytes]) -> dict[str, Any]:
    raw = bytes(value) if isinstance(value, (bytes, bytearray)) else b"".join(value)
    if not raw or len(raw) > MAX_EVENT_BYTES:
        raise DeliveryError("INVALID_SOURCE_RECORD")
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeliveryError("INVALID_SOURCE_RECORD") from exc
    if not isinstance(decoded, dict):
        raise DeliveryError("INVALID_SOURCE_RECORD")
    return decoded


def _validate(event: Mapping[str, Any]) -> dict[str, Any]:
    if set(event) != REQUIRED_FIELDS or event.get("schema_version") != SCHEMA_VERSION:
        raise DeliveryError("INVALID_CANONICAL_EVENT")
    if event.get("event_type") not in SUPPORTED_EVENT_TYPES:
        raise DeliveryError("UNSUPPORTED_EVENT_TYPE")
    for field in REQUIRED_FIELDS - {"payload"}:
        if not isinstance(event.get(field), str) or not event[field]:
            raise DeliveryError("INVALID_CANONICAL_EVENT")
    if not isinstance(event.get("payload"), Mapping):
        raise DeliveryError("INVALID_CANONICAL_EVENT")
    if len(_canonical_bytes(event)) > MAX_EVENT_BYTES:
        raise DeliveryError("INVALID_CANONICAL_EVENT")
    return dict(event)


def _required_environment(name: str) -> str:
    value = os.getenv(name, "")
    if not value or len(value.encode("utf-8")) > 2048:
        raise DeliveryError("EVENT_RUNTIME_NOT_CONFIGURED")
    return value


def _post_delivery(event: Mapping[str, Any], role: str | None = None) -> None:
    payload: Mapping[str, Any] = event
    if role is not None:
        payload = {"eventing_delivery": {"consumer_role": role, "event": event}}
    request = Request(
        _required_environment("EVENT_DOMAIN_DELIVERY_URL"),
        data=_canonical_bytes(payload),
        headers={
            "content-type": "application/json",
            "x-functions-key": _required_environment("EVENT_DOMAIN_DELIVERY_KEY"),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
    except (HTTPError, TimeoutError, URLError, OSError) as exc:
        raise DeliveryError("DESTINATION_RETRYABLE_FAILURE") from exc
    if not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise DeliveryError("DESTINATION_NOT_ACCEPTED")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeliveryError("DESTINATION_NOT_ACCEPTED") from exc
    if status != 202 or result != {
        "schema_version": "event-delivery-result.v1",
        "accepted": 1,
    }:
        raise DeliveryError("DESTINATION_NOT_ACCEPTED")


def _failure_record(event: Mapping[str, Any], error_code: str) -> dict[str, Any]:
    validated = None
    try:
        validated = _validate(event)
    except DeliveryError:
        pass
    failure: dict[str, Any] = {
        "schema_version": "event-delivery-failure.v1",
        "event_id": str(event.get("event_id") or "invalid"),
        "correlation_id": str(event.get("correlation_id") or "invalid"),
        "error_code": error_code,
    }
    if validated is not None:
        failure["canonical_event"] = validated
    return failure


def _publish_terminal_failures(
    failures: Iterable[tuple[Mapping[str, Any], str]],
) -> None:
    from azure.eventhub import EventData, EventHubProducerClient
    from azure.identity import DefaultAzureCredential

    namespace = _required_environment("EVENT_HUBS__fullyQualifiedNamespace")
    hub_name = _required_environment("EVENT_FAILURE_HUB_NAME")
    client_id = os.getenv("EVENT_MANAGED_IDENTITY_CLIENT_ID", "") or None
    producer = EventHubProducerClient(
        fully_qualified_namespace=namespace,
        eventhub_name=hub_name,
        credential=DefaultAzureCredential(managed_identity_client_id=client_id),
        buffered_mode=False,
    )
    with producer:
        for event, error_code in failures:
            producer.send_batch(
                [EventData(_canonical_bytes(_failure_record(event, error_code)))],
                partition_key=str(event.get("source_id") or "invalid"),
                timeout=30,
            )


def _retry_count(context: func.Context) -> int:
    retry_context = getattr(context, "retry_context", None)
    try:
        return max(0, int(getattr(retry_context, "retry_count", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _telemetry_batch(
    messages: Iterable[func.EventHubEvent],
    *,
    role: str,
    expected_type: str,
    context: func.Context,
) -> None:
    failures: list[tuple[Mapping[str, Any], str]] = []
    for message in messages:
        event: Mapping[str, Any] = {}
        try:
            event = _validate(_decode(message.get_body()))
            if event["event_type"] != expected_type:
                raise DeliveryError("EVENT_CHANNEL_MISMATCH")
            if role in {"audit", "realtime-visualization"}:
                continue
            _post_delivery(event, role)
        except Exception as exc:
            error_code = (
                str(exc)
                if isinstance(exc, DeliveryError)
                else "DESTINATION_RETRYABLE_FAILURE"
            )
            failures.append((event, error_code))
    if not failures:
        return
    if _retry_count(context) >= 5:
        _publish_terminal_failures(failures)
        return
    raise RuntimeError("EVENT_DELIVERY_RETRYABLE_FAILURE")


def _configured_processed_roles() -> tuple[str, ...]:
    try:
        value = json.loads(os.getenv("EVENT_LOCAL_PROCESSED_ROLES_JSON", "[]"))
    except json.JSONDecodeError as exc:
        raise DeliveryError("EVENT_RUNTIME_NOT_CONFIGURED") from exc
    if (
        not isinstance(value, list)
        or len(value) > len(PROCESSED_ROLES)
        or not all(isinstance(item, str) and item in PROCESSED_ROLES for item in value)
        or len(set(value)) != len(value)
    ):
        raise DeliveryError("EVENT_RUNTIME_NOT_CONFIGURED")
    return tuple(sorted(value))


app = func.FunctionApp()


if os.getenv("EVENT_LOCAL_PROCESSING_ENABLED", "false").lower() == "true":

    @app.function_name(name="event-telemetry-processor")
    @app.retry(
        strategy="exponential_backoff",
        max_retry_count="5",
        minimum_interval="00:00:01",
        maximum_interval="00:00:32",
    )
    @app.event_hub_message_trigger(
        arg_name="messages",
        event_hub_name="%EVENT_RECEIVED_HUB_NAME%",
        connection="EVENT_HUBS",
        cardinality="many",
        consumer_group="telemetry-processor",
    )
    def telemetry_processor(
        messages: list[func.EventHubEvent], context: func.Context
    ) -> None:
        _telemetry_batch(
            messages,
            role="telemetry-processor",
            expected_type=TELEMETRY_RECEIVED,
            context=context,
        )


def _register_processed_consumer(role: str) -> None:
    function_name = f"event-{role}"

    @app.function_name(name=function_name)
    @app.retry(
        strategy="exponential_backoff",
        max_retry_count="5",
        minimum_interval="00:00:01",
        maximum_interval="00:00:32",
    )
    @app.event_hub_message_trigger(
        arg_name="messages",
        event_hub_name="%EVENT_PROCESSED_HUB_NAME%",
        connection="EVENT_HUBS",
        cardinality="many",
        consumer_group=role,
    )
    def processed_consumer(
        messages: list[func.EventHubEvent], context: func.Context
    ) -> None:
        _telemetry_batch(
            messages,
            role=role,
            expected_type=TELEMETRY_PROCESSED,
            context=context,
        )


for _processed_role in _configured_processed_roles():
    _register_processed_consumer(_processed_role)


if os.getenv("EVENT_LOCAL_CONTROL_ENABLED", "false").lower() == "true":

    @app.function_name(name="event-control-router")
    @app.service_bus_topic_trigger(
        arg_name="message",
        topic_name="%EVENT_CONTROL_TOPIC_NAME%",
        subscription_name="%EVENT_CONTROL_SUBSCRIPTION_NAME%",
        connection="EVENT_SERVICE_BUS",
        is_sessions_enabled=True,
    )
    def control_router(message: func.ServiceBusMessage) -> None:
        try:
            _post_delivery(
                _validate(_decode(message.get_body())),
                "control-router",
            )
        except DeliveryError as exc:
            raise RuntimeError(str(exc)) from None


__all__ = ["DeliveryError", "app"]
