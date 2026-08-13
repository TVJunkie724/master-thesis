"""Azure Functions entry points for ``five-layer-baseline@2``.

Cross-cloud ingress terminates on Event Hubs or Service Bus.  No public
function-to-function bridge endpoint is exposed by this package.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid

import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import (
    CosmosBatchOperationError,
    CosmosResourceExistsError,
    CosmosResourceNotFoundError,
)
from azure.digitaltwins.core import DigitalTwinsClient
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage

from core import (
    ContractError,
    build_ingress_event,
    build_processed_event,
    build_rule_matches,
    build_twin_projection,
    canonical_json,
    cosmos_raw_history_statement,
    decode_cursor,
    decode_json_object,
    decode_message_body,
    derive_event,
    encode_cursor,
    event_body,
    event_id,
    finite_number,
    iso_time,
    next_rollup_document,
    normalize_history_points,
    outcome_document,
    parse_time,
    parse_raw_history_query,
    partition_key,
    raw_document,
    raw_history_query_digest,
    rollup_id,
    validate_canonical_event,
)


app = func.FunctionApp()
REMOTE_TELEMETRY_ENABLED = (
    os.getenv("V2_REMOTE_TELEMETRY_ENABLED", "false").strip().lower() == "true"
)
DOMAIN_CONSUMER_ENABLED = (
    os.getenv("V2_DOMAIN_CONSUMER_ENABLED", "false").strip().lower() == "true"
)
IOT_PROCESSOR_ENABLED = (
    os.getenv("V2_IOT_PROCESSOR_ENABLED", "false").strip().lower() == "true"
)
BRIDGE_TELEMETRY_ENABLED = (
    os.getenv("V2_BRIDGE_TELEMETRY_ENABLED", "false").strip().lower() == "true"
)
BRIDGE_CONTROL_ENABLED = (
    os.getenv("V2_BRIDGE_CONTROL_ENABLED", "false").strip().lower() == "true"
)
BRIDGE_EVENT_TELEMETRY_ENABLED = (
    os.getenv("V2_BRIDGE_EVENT_TELEMETRY_ENABLED", "false").strip().lower() == "true"
)
BRIDGE_EVENT_CONTROL_ENABLED = (
    os.getenv("V2_BRIDGE_EVENT_CONTROL_ENABLED", "false").strip().lower() == "true"
)
RAW_HISTORY_ENABLED = (
    os.getenv("V2_RAW_HISTORY_ENABLED", "false").strip().lower() == "true"
)
ACTION_ENDPOINT_ENABLED = (
    os.getenv("V2_ACTION_ENDPOINT_ENABLED", "false").strip().lower() == "true"
)
EVENTING_DELIVERY_ENDPOINT_ENABLED = (
    os.getenv("V2_EVENTING_DELIVERY_ENDPOINT_ENABLED", "false").strip().lower()
    == "true"
)
_COSMOS_CONTAINER: Any | None = None
_ADT_CLIENT: Any | None = None
_AZURE_CREDENTIAL: Any | None = None
_SERVICE_BUS_CLIENT: Any | None = None
MAX_EXTENSION_RESPONSE_BYTES = 1024 * 1024


def _credential():
    global _AZURE_CREDENTIAL
    if _AZURE_CREDENTIAL is not None:
        return _AZURE_CREDENTIAL
    client_id = os.getenv("V2_MANAGED_IDENTITY_CLIENT_ID", "")
    _AZURE_CREDENTIAL = DefaultAzureCredential(
        managed_identity_client_id=client_id or None
    )
    return _AZURE_CREDENTIAL


def _event_hub_events(messages: Iterable[func.EventHubEvent]):
    for message in messages:
        yield decode_message_body(message.get_body())


def _service_bus_event(message: func.ServiceBusMessage):
    return decode_message_body(message.get_body())


def _service_bus_client():
    global _SERVICE_BUS_CLIENT
    if _SERVICE_BUS_CLIENT is not None:
        return _SERVICE_BUS_CLIENT
    namespace = os.getenv("V2_SERVICE_BUS__fullyQualifiedNamespace", "")
    if not namespace or namespace.startswith("disabled."):
        raise ContractError("DOMAIN_ROUTE_NOT_CONFIGURED", 503)
    _SERVICE_BUS_CLIENT = ServiceBusClient(
        fully_qualified_namespace=namespace,
        credential=_credential(),
    )
    return _SERVICE_BUS_CLIENT


def _six_layer_eventing() -> bool:
    return os.getenv("ARCHITECTURE_PROFILE") == "six-layer-eventing@1"


def _enqueue(event: Mapping[str, Any]) -> None:
    validated = validate_canonical_event(event)
    if _six_layer_eventing():
        _publish_eventing_control(validated)
        return
    queue_name = os.getenv("V2_DOMAIN_QUEUE_NAME", "")
    if not queue_name:
        raise ContractError("DOMAIN_ROUTE_NOT_CONFIGURED", 503)
    message = ServiceBusMessage(
        canonical_json(validated),
        content_type="application/json",
        message_id=event_id(validated),
        session_id=str(validated["source_id"]),
        correlation_id=str(validated["correlation_id"]),
    )
    with _service_bus_client().get_queue_sender(queue_name=queue_name) as sender:
        sender.send_messages(message)


def _publish_eventing_stream(event: Mapping[str, Any]) -> None:
    from azure.eventhub import EventData, EventHubProducerClient

    validated = validate_canonical_event(event)
    hub_setting = {
        "telemetry.received.v1": "V2_EVENTING_RECEIVED_HUB_NAME",
        "telemetry.processed.v1": "V2_EVENTING_PROCESSED_HUB_NAME",
    }.get(str(validated["event_type"]))
    if hub_setting is None:
        raise ContractError("UNSUPPORTED_EVENTING_STREAM_EVENT")
    namespace = os.getenv("V2_EVENTING__fullyQualifiedNamespace", "")
    event_hub_name = os.getenv(hub_setting, "")
    if not namespace or namespace.startswith("disabled.") or not event_hub_name:
        raise ContractError("EVENTING_ROUTE_NOT_CONFIGURED", 503)
    producer = EventHubProducerClient(
        fully_qualified_namespace=namespace,
        eventhub_name=event_hub_name,
        credential=_credential(),
        buffered_mode=False,
    )
    with producer:
        producer.send_batch(
            [EventData(canonical_json(validated).encode("utf-8"))],
            partition_key=partition_key(validated),
            timeout=30,
        )


def _publish_eventing_control(event: Mapping[str, Any]) -> None:
    validated = validate_canonical_event(event)
    namespace = os.getenv("V2_EVENTING_SERVICE_BUS__fullyQualifiedNamespace", "")
    topic_name = os.getenv("V2_EVENTING_CONTROL_TOPIC_NAME", "")
    if not namespace or namespace.startswith("disabled.") or not topic_name:
        raise ContractError("EVENTING_ROUTE_NOT_CONFIGURED", 503)
    client = ServiceBusClient(
        fully_qualified_namespace=namespace,
        credential=_credential(),
    )
    message = ServiceBusMessage(
        canonical_json(validated),
        content_type="application/json",
        message_id=event_id(validated),
        session_id=partition_key(validated),
        partition_key=partition_key(validated),
        correlation_id=str(validated["correlation_id"]),
        application_properties={"event_type": str(validated["event_type"])},
    )
    with client:
        with client.get_topic_sender(topic_name=topic_name) as sender:
            sender.send_messages(message)


def _publish_telemetry(event: Mapping[str, Any]) -> None:
    from azure.eventhub import EventData, EventHubProducerClient

    validated = validate_canonical_event(event)
    namespace = os.getenv("V2_BRIDGE_TELEMETRY__fullyQualifiedNamespace", "")
    event_hub_name = os.getenv("V2_BRIDGE_TELEMETRY_HUB_NAME", "")
    if not namespace or namespace.startswith("disabled.") or not event_hub_name:
        raise ContractError("REMOTE_HOT_ROUTE_NOT_CONFIGURED", 503)
    producer = EventHubProducerClient(
        fully_qualified_namespace=namespace,
        eventhub_name=event_hub_name,
        credential=_credential(),
        buffered_mode=False,
    )
    with producer:
        producer.send_batch(
            [EventData(canonical_json(validated).encode("utf-8"))],
            partition_key=partition_key(validated),
            timeout=30,
        )


def _publish_control(event: Mapping[str, Any]) -> None:
    validated = validate_canonical_event(event)
    topic_name = os.getenv("V2_BRIDGE_CONTROL_TOPIC_NAME", "")
    if not topic_name:
        raise ContractError("REMOTE_CONTROL_ROUTE_NOT_CONFIGURED", 503)
    message = ServiceBusMessage(
        canonical_json(validated),
        content_type="application/json",
        message_id=event_id(validated),
        session_id=partition_key(validated),
        correlation_id=str(validated["correlation_id"]),
    )
    with _service_bus_client().get_topic_sender(topic_name=topic_name) as sender:
        sender.send_messages(message)


def _event_hub_delivery_attempt(context: func.Context) -> int:
    retry_context = getattr(context, "retry_context", None)
    retry_count = getattr(retry_context, "retry_count", 0)
    try:
        return min(6, max(1, int(retry_count or 0) + 1))
    except (TypeError, ValueError):
        return 1


def _extension_envelope(event: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_canonical_event(event)
    body = event_body(validated)
    invocation_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"{event_id(validated)}:processor.telemetry")
    )
    payload = {"value": finite_number(body.get("value"))}
    unit = body.get("unit")
    if isinstance(unit, str) and unit:
        payload["unit"] = unit
    twin_id = body.get("twin_id")
    device_id = body.get("device_id")
    if not isinstance(twin_id, str) or not isinstance(device_id, str):
        raise ContractError("INVALID_PROCESSOR_CONTEXT")
    return {
        "schema_version": "user-function-runtime-envelope.v1",
        "invocation_id": invocation_id,
        "correlation_id": str(validated["correlation_id"]),
        "occurred_at": str(validated["occurred_at"]),
        "slot_id": "processor.telemetry",
        "payload": payload,
        "context": {"twin_id": twin_id, "device_id": device_id},
    }


def _post_extension(envelope: Mapping[str, Any]) -> dict[str, Any]:
    url = os.getenv("V2_PROCESSOR_EXTENSION_URL", "")
    key = os.getenv("V2_PROCESSOR_EXTENSION_KEY", "")
    if not url or not key:
        raise ContractError("PROCESSOR_EXTENSION_NOT_CONFIGURED", 503)
    request = Request(
        url,
        data=canonical_json(envelope).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-functions-key": key,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=35) as response:  # nosec B310
            raw = response.read(MAX_EXTENSION_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raw = exc.read(MAX_EXTENSION_RESPONSE_BYTES + 1)
    except (TimeoutError, URLError, OSError) as exc:
        raise ContractError("PROCESSOR_EXTENSION_UNAVAILABLE", 503) from exc
    if len(raw) > MAX_EXTENSION_RESPONSE_BYTES:
        raise ContractError("PROCESSOR_EXTENSION_RESPONSE_TOO_LARGE", 503)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("INVALID_PROCESSOR_EXTENSION_RESPONSE", 503) from exc
    if not isinstance(value, dict):
        raise ContractError("INVALID_PROCESSOR_EXTENSION_RESPONSE", 503)
    return value


def _invoke_processor_extension(event: Mapping[str, Any]) -> Mapping[str, Any]:
    envelope = _extension_envelope(event)
    response = _post_extension(envelope)
    common = {
        "schema_version",
        "invocation_id",
        "correlation_id",
        "slot_id",
        "status",
    }
    if (
        response.get("schema_version") != "user-function-runtime-envelope.v1"
        or response.get("invocation_id") != envelope["invocation_id"]
        or response.get("correlation_id") != envelope["correlation_id"]
        or response.get("slot_id") != "processor.telemetry"
    ):
        raise ContractError("INVALID_PROCESSOR_EXTENSION_RESPONSE", 503)
    if response.get("status") == "success" and set(response) == common | {"payload"}:
        payload = response.get("payload")
        if isinstance(payload, Mapping):
            return payload
    if response.get("status") in {"rejected", "failed"}:
        raise ContractError("PROCESSOR_EXTENSION_REJECTED", 422)
    raise ContractError("INVALID_PROCESSOR_EXTENSION_RESPONSE", 503)


def _post_bound_json(
    url: str, payload: Mapping[str, Any], *, function_key: str = "", timeout: int = 10
) -> dict[str, Any] | None:
    if not url:
        return None
    headers = {"content-type": "application/json"}
    if function_key:
        headers["x-functions-key"] = function_key
    request = Request(
        url,
        data=canonical_json(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            raw = response.read(MAX_EXTENSION_RESPONSE_BYTES + 1)
    except (HTTPError, TimeoutError, URLError, OSError):
        return None
    if not raw or len(raw) > MAX_EXTENSION_RESPONSE_BYTES:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _configured_rules() -> list[Mapping[str, Any]]:
    try:
        rules = json.loads(os.getenv("V2_RULES_JSON", "[]"))
    except json.JSONDecodeError as exc:
        raise ContractError("INVALID_RULE_CONFIGURATION", 503) from exc
    if not isinstance(rules, list):
        raise ContractError("INVALID_RULE_CONFIGURATION", 503)
    return rules


def _evaluate_rules(event: Mapping[str, Any]) -> None:
    for matched in build_rule_matches(event, _configured_rules()):
        _enqueue(matched)


def _persist_processed(processed: Mapping[str, Any]) -> None:
    if os.getenv("V2_HOT_PROVIDER") != "azure":
        raise ContractError("REMOTE_HOT_ROUTE_NOT_CONFIGURED", 503)
    _write_raw_and_rollup(processed)
    _project_twin(processed)


def _project_twin(processed: Mapping[str, Any]) -> None:
    projection = build_twin_projection(processed)
    if projection is None:
        return
    if os.getenv("V2_TWIN_PROVIDER") == "azure":
        _materialize_twin_projection(projection)
    else:
        _publish_control(projection)


def _process_received(event: Mapping[str, Any]) -> None:
    processed = build_processed_event(event, _invoke_processor_extension(event))
    if _six_layer_eventing():
        _publish_eventing_stream(processed)
    elif os.getenv("V2_HOT_PROVIDER") == "azure":
        _enqueue(processed)
    else:
        _publish_telemetry(processed)
        _evaluate_rules(processed)


def _action_name(action: Mapping[str, Any]) -> str:
    value = action.get("functionName")
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 128:
        raise ContractError("EXTENSION_ACTION_NOT_CONFIGURED", 503)
    return value


def _invoke_poc_action(event: Mapping[str, Any], action: Mapping[str, Any]) -> bool:
    url = os.getenv("V2_ACTION_FUNCTION_URL", "")
    key = os.getenv("V2_ACTION_FUNCTION_KEY", "")
    invocation = {
        "schema_version": "extension-action-invocation.v1",
        "invocation_id": event_id(event),
        "action_id": _action_name(action),
        "event": dict(event),
    }
    for _ in range(3):
        response = _post_bound_json(url, invocation, function_key=key)
        if response == {
            "schema_version": "extension-action-result.v1",
            "invocation_id": event_id(event),
            "action_id": invocation["action_id"],
            "status": "ACCEPTED",
        }:
            return True
    return False


def _dispatch_match(event: Mapping[str, Any]) -> None:
    body = event_body(event)
    action = body.get("action")
    if not isinstance(action, Mapping):
        raise ContractError("INVALID_MATCH_EVENT")
    action_succeeded = _invoke_poc_action(event, action)
    _enqueue(
        derive_event(
            event,
            event_type="extension.action.outcome.v1",
            producer="component.action-dispatcher",
            payload={
                "device_id": partition_key(event),
                "rule_id": body.get("rule_id"),
                "invocation_id": event_id(event),
                "action_id": _action_name(action),
                "status": "SUCCEEDED" if action_succeeded else "FAILED",
            },
        )
    )
    if action.get("type") in {"step_function", "logic_app", "workflow"}:
        _enqueue(
            derive_event(
                event,
                event_type="notification.requested.v1",
                producer="component.action-dispatcher",
                payload={
                    "device_id": partition_key(event),
                    "rule_id": body.get("rule_id"),
                    "message": str(
                        action.get("message") or body.get("condition") or "Rule matched"
                    ),
                },
            )
        )
    feedback = action.get("feedback")
    if isinstance(feedback, Mapping):
        device_id = feedback.get("device_id") or feedback.get("iotDeviceId")
        if not isinstance(device_id, str) or not device_id:
            device_id = partition_key(event)
        command = derive_event(
            event,
            event_type="device.command.requested.v1",
            producer="component.action-dispatcher",
            payload={
                "device_id": device_id,
                "rule_id": body.get("rule_id"),
                "message": str(feedback.get("payload") or "Rule matched"),
            },
        )
        if os.getenv("V2_L1_PROVIDER") == "azure":
            _enqueue(command)
        else:
            _publish_control(command)


def _start_notification_workflow(event: Mapping[str, Any]) -> None:
    url = os.getenv("V2_LOGIC_APP_CALLBACK_URL", "")
    accepted = False
    for _ in range(3):
        response = _post_bound_json(url, event)
        if (
            isinstance(response, Mapping)
            and response.get("status") == "ACCEPTED"
            and response.get("event_id") == event_id(event)
        ):
            accepted = True
            break
    _emit_outcome(
        derive_event(
            event,
            event_type="notification.workflow.outcome.v1",
            producer="component.notification-workflow",
            payload={
                "device_id": partition_key(event),
                "invocation_id": event_id(event),
                "status": "SUCCEEDED" if accepted else "FAILED",
            },
        )
    )


def _send_device_command(event: Mapping[str, Any]) -> bool:
    hostname = os.getenv("V2_IOT_HUB_HOSTNAME", "")
    body = event_body(event)
    device_id = partition_key(event)
    if not hostname:
        return False
    url = (
        f"https://{hostname}/devices/{quote(device_id, safe='')}/messages/deviceBound"
        "?api-version=2021-04-12"
    )
    payload = str(body.get("message") or "Rule matched").encode("utf-8")
    for _ in range(3):
        try:
            token = _credential().get_token("https://iothubs.azure.net/.default")
            request = Request(
                url,
                data=payload,
                headers={
                    "authorization": f"Bearer {token.token}",
                    "content-type": "text/plain; charset=utf-8",
                    "iothub-messageid": event_id(event),
                },
                method="POST",
            )
            with urlopen(request, timeout=10) as response:  # nosec B310
                if response.status == 204:
                    return True
        except (HTTPError, TimeoutError, URLError, OSError):
            continue
    return False


def _deliver_device_command(event: Mapping[str, Any]) -> None:
    accepted = _send_device_command(event)
    _emit_outcome(
        derive_event(
            event,
            event_type="device.command.outcome.v1",
            producer="component.device-command-adapter",
            payload={
                "device_id": partition_key(event),
                "invocation_id": event_id(event),
                "status": "ACCEPTED" if accepted else "FAILED",
            },
        )
    )


def _consume(event: dict) -> None:
    """Route one canonical event to its Azure-owned local responsibility."""

    validated = validate_canonical_event(event)
    if (
        _six_layer_eventing()
        and os.getenv("V2_EVENT_LAYER_PROVIDER") == "azure"
        and validated["event_type"]
        in {
            "telemetry.received.v1",
            "telemetry.processed.v1",
            "event.matched.v1",
            "notification.requested.v1",
            "device.command.requested.v1",
            "extension.action.outcome.v1",
            "notification.workflow.outcome.v1",
            "device.command.outcome.v1",
        }
    ):
        if validated["event_type"] in {
            "telemetry.received.v1",
            "telemetry.processed.v1",
        }:
            _publish_eventing_stream(validated)
        else:
            _publish_eventing_control(validated)
    elif validated["event_type"] == "telemetry.received.v1":
        if os.getenv("V2_L2_PROVIDER") != "azure":
            raise ContractError("REMOTE_PROCESSING_ROUTE_NOT_CONFIGURED", 503)
        _process_received(validated)
    elif validated["event_type"] == "telemetry.processed.v1":
        handled = False
        if os.getenv("V2_HOT_PROVIDER") == "azure":
            _persist_processed(validated)
            handled = True
        if _six_layer_eventing() and os.getenv("V2_L2_PROVIDER") == "azure":
            _evaluate_rules(validated)
            handled = True
        if not handled:
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
    elif validated["event_type"] == "twin.state.upserted":
        if os.getenv("V2_TWIN_PROVIDER") != "azure":
            raise ContractError("REMOTE_TWIN_ROUTE_NOT_CONFIGURED", 503)
        _materialize_twin_projection(validated)
    elif validated["event_type"] == "event.matched.v1":
        if _six_layer_eventing() and os.getenv("V2_L2_PROVIDER") != "azure":
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _dispatch_match(validated)
    elif validated["event_type"] == "notification.requested.v1":
        if _six_layer_eventing() and os.getenv("V2_L2_PROVIDER") != "azure":
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _start_notification_workflow(validated)
    elif validated["event_type"] == "device.command.requested.v1":
        if _six_layer_eventing() and os.getenv("V2_L1_PROVIDER") != "azure":
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _deliver_device_command(validated)
    elif validated["event_type"] in {
        "extension.action.outcome.v1",
        "notification.workflow.outcome.v1",
        "device.command.outcome.v1",
    }:
        if _six_layer_eventing() and os.getenv("V2_HOT_PROVIDER") != "azure":
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _store_outcome(validated)
    else:
        raise ContractError("UNSUPPORTED_LOCAL_DOMAIN_EVENT")
    logging.info(
        "Azure v2 event accepted type=%s event_id=%s",
        validated["event_type"],
        validated["event_id"],
    )


def _consume_eventing_delivery(role: str, event: Mapping[str, Any]) -> None:
    validated = validate_canonical_event(event)
    kind = validated["event_type"]
    if role == "telemetry-processor":
        if kind != "telemetry.received.v1" or os.getenv("V2_L2_PROVIDER") != "azure":
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _process_received(validated)
    elif role == "control-router":
        if kind == "event.matched.v1" and os.getenv("V2_L2_PROVIDER") == "azure":
            _dispatch_match(validated)
        elif (
            kind == "notification.requested.v1"
            and os.getenv("V2_L2_PROVIDER") == "azure"
        ):
            _start_notification_workflow(validated)
        elif (
            kind == "device.command.requested.v1"
            and os.getenv("V2_L1_PROVIDER") == "azure"
        ):
            _deliver_device_command(validated)
        elif (
            kind
            in {
                "extension.action.outcome.v1",
                "notification.workflow.outcome.v1",
                "device.command.outcome.v1",
            }
            and os.getenv("V2_HOT_PROVIDER") == "azure"
        ):
            _store_outcome(validated)
        else:
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
    elif kind != "telemetry.processed.v1":
        raise ContractError("EVENTING_CONSUMER_EVENT_MISMATCH")
    elif role == "historical-persistence":
        if os.getenv("V2_HOT_PROVIDER") != "azure":
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _write_raw_and_rollup(validated)
    elif role == "twin-state-update":
        if os.getenv("V2_HOT_PROVIDER") != "azure":
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _project_twin(validated)
    elif role == "rule-evaluator":
        if os.getenv("V2_L2_PROVIDER") != "azure":
            raise ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _evaluate_rules(validated)
    elif role not in {"audit", "realtime-visualization"}:
        raise ContractError("UNKNOWN_EVENTING_CONSUMER")


def _reader_response(status: int, payload: Mapping[str, Any]) -> func.HttpResponse:
    return func.HttpResponse(
        body=canonical_json(payload),
        status_code=status,
        mimetype="application/json",
        headers={"cache-control": "no-store"},
    )


def _poc_action_result(invocation: Mapping[str, Any]) -> dict[str, Any]:
    if (
        set(invocation)
        != {
            "schema_version",
            "invocation_id",
            "action_id",
            "event",
        }
        or invocation.get("schema_version") != "extension-action-invocation.v1"
    ):
        raise ContractError("INVALID_ACTION_INVOCATION")
    event = invocation.get("event")
    if not isinstance(event, Mapping):
        raise ContractError("INVALID_ACTION_INVOCATION")
    validated = validate_canonical_event(event)
    action = event_body(validated).get("action")
    if (
        validated["event_type"] != "event.matched.v1"
        or invocation.get("invocation_id") != event_id(validated)
        or not isinstance(action, Mapping)
        or invocation.get("action_id") != _action_name(action)
    ):
        raise ContractError("INVALID_ACTION_INVOCATION")
    return {
        "schema_version": "extension-action-result.v1",
        "invocation_id": event_id(validated),
        "action_id": invocation["action_id"],
        "status": "ACCEPTED",
    }


def _poc_notification_result(event: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_canonical_event(event)
    if validated["event_type"] != "notification.requested.v1":
        raise ContractError("INVALID_NOTIFICATION_INVOCATION")
    body = event_body(validated)
    if not isinstance(body.get("message"), str) or not body["message"]:
        raise ContractError("INVALID_NOTIFICATION_INVOCATION")
    return {
        "schema_version": "notification-delivery-result.v1",
        "event_id": event_id(validated),
        "status": "ACCEPTED",
    }


if ACTION_ENDPOINT_ENABLED:

    @app.function_name(name="v2-poc-extension-action")
    @app.route(
        route="extension-action/v1",
        methods=["POST"],
        auth_level=func.AuthLevel.FUNCTION,
    )
    def poc_extension_action(req: func.HttpRequest) -> func.HttpResponse:
        """Execute the fixed, side-effect-free PoC extension-action boundary."""

        try:
            invocation = decode_json_object(req.get_body())
            return _reader_response(
                200,
                _poc_action_result(invocation),
            )
        except ContractError as exc:
            return _reader_response(
                exc.status,
                {
                    "schema_version": "architecture-runtime-error.v1",
                    "code": exc.code,
                },
            )

    @app.function_name(name="v2-poc-notification-delivery")
    @app.route(
        route="notification-delivery/v1",
        methods=["POST"],
        auth_level=func.AuthLevel.FUNCTION,
    )
    def poc_notification_delivery(req: func.HttpRequest) -> func.HttpResponse:
        """Accept the workflow's one external PoC notification action."""

        try:
            event = decode_json_object(req.get_body())
            return _reader_response(200, _poc_notification_result(event))
        except ContractError as exc:
            return _reader_response(
                exc.status,
                {
                    "schema_version": "architecture-runtime-error.v1",
                    "code": exc.code,
                },
            )


def _cosmos_container():
    global _COSMOS_CONTAINER
    if _COSMOS_CONTAINER is not None:
        return _COSMOS_CONTAINER
    endpoint = os.getenv("V2_COSMOS_ENDPOINT", "")
    database = os.getenv("V2_COSMOS_DATABASE", "")
    container = os.getenv("V2_COSMOS_CONTAINER", "")
    if not endpoint or not database or not container:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
    client = CosmosClient(endpoint, credential=_credential())
    _COSMOS_CONTAINER = client.get_database_client(database).get_container_client(
        container
    )
    return _COSMOS_CONTAINER


def _read_item_or_none(container, item_id: str, partition_key: str):
    try:
        return container.read_item(item=item_id, partition_key=partition_key)
    except CosmosResourceNotFoundError:
        return None


def _batch_statuses(exc: CosmosBatchOperationError) -> set[int]:
    responses = getattr(exc, "operation_responses", None) or []
    statuses = {
        int(response.get("statusCode"))
        for response in responses
        if isinstance(response, Mapping) and isinstance(response.get("statusCode"), int)
    }
    if isinstance(getattr(exc, "status_code", None), int):
        statuses.add(exc.status_code)
    return statuses


def _storage_task_count() -> int:
    try:
        value = int(os.getenv("V2_STORAGE_TASK_COUNT", "1"))
    except ValueError as exc:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503) from exc
    if value < 1:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
    return value


def _write_raw_and_rollup(
    event: Mapping[str, Any], *, stored_at=None, attempts: int = 3
) -> bool:
    """Atomically create raw telemetry and CAS-update its hourly rollup."""

    if attempts < 1:
        raise ValueError("attempts must be positive")
    container = _cosmos_container()
    current_time = stored_at or datetime.now(timezone.utc)
    try:
        hot_days = int(os.getenv("V2_HOT_BOUNDARY_DAYS", "0"))
    except ValueError as exc:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503) from exc
    raw = raw_document(
        event,
        stored_at=current_time,
        hot_boundary_days=hot_days,
        storage_task_count=_storage_task_count(),
    )
    device_id = str(raw["device_id"])
    for attempt in range(attempts):
        existing_raw = _read_item_or_none(container, str(raw["id"]), device_id)
        if existing_raw is not None:
            if existing_raw.get("payload_digest") == raw["payload_digest"]:
                return False
            raise ContractError("IDEMPOTENCY_CONFLICT", 409)

        current_rollup = _read_item_or_none(container, rollup_id(raw), device_id)
        rollup = next_rollup_document(raw, current_rollup)
        if current_rollup is not None and not current_rollup.get("_etag"):
            raise ContractError("INVALID_ROLLUP_STATE", 503)
        rollup_operation = (
            ("create", (rollup,), {})
            if current_rollup is None
            else (
                "replace",
                (str(rollup["id"]), rollup),
                {"if_match_etag": current_rollup.get("_etag")},
            )
        )
        try:
            container.execute_item_batch(
                batch_operations=[("create", (raw,), {}), rollup_operation],
                partition_key=device_id,
            )
            return True
        except CosmosBatchOperationError as exc:
            statuses = _batch_statuses(exc)
            if not statuses.intersection({409, 412, 424}):
                raise
            if attempt + 1 < attempts:
                time.sleep(0.01 * (attempt + 1))
    raise ContractError("ROLLUP_CONFLICT_EXHAUSTED", 503)


def _store_outcome(event: Mapping[str, Any], *, stored_at=None) -> None:
    if os.getenv("V2_HOT_PROVIDER") != "azure":
        _publish_control(event)
        return
    try:
        hot_days = int(os.getenv("V2_HOT_BOUNDARY_DAYS", "0"))
    except ValueError as exc:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503) from exc
    document = outcome_document(
        event,
        stored_at=stored_at or datetime.now(timezone.utc),
        hot_boundary_days=hot_days,
        storage_task_count=_storage_task_count(),
    )
    container = _cosmos_container()
    try:
        container.create_item(body=document)
    except CosmosResourceExistsError:
        existing = container.read_item(
            item=document["id"], partition_key=document["device_id"]
        )
        if existing.get("payload_digest") != document["payload_digest"]:
            raise ContractError("IDEMPOTENCY_CONFLICT", 409) from None


def _emit_outcome(event: Mapping[str, Any]) -> None:
    if _six_layer_eventing():
        _enqueue(event)
    else:
        _store_outcome(event)


def _adt_client():
    global _ADT_CLIENT
    if _ADT_CLIENT is not None:
        return _ADT_CLIENT
    endpoint = os.getenv("V2_ADT_ENDPOINT", "")
    if not endpoint:
        raise ContractError("TWIN_PROJECTION_TARGET_NOT_CONFIGURED", 503)
    _ADT_CLIENT = DigitalTwinsClient(endpoint, _credential())
    return _ADT_CLIENT


def _materialize_twin_projection(event: Mapping[str, Any]) -> None:
    """Idempotently project the selected numeric state into Azure Digital Twins."""

    validated = validate_canonical_event(event)
    if validated["event_type"] != "twin.state.upserted":
        raise ContractError("UNEXPECTED_TWIN_PROJECTION")
    body = event_body(validated)
    twin_id = body.get("twin_id")
    state_patch = body.get("state_patch")
    if (
        not isinstance(twin_id, str)
        or not twin_id
        or not isinstance(state_patch, Mapping)
    ):
        raise ContractError("INVALID_TWIN_STATE_PATCH")
    if len(state_patch) != 1:
        raise ContractError("INVALID_TWIN_STATE_PATCH")
    metric, value = next(iter(state_patch.items()))
    if not isinstance(metric, str) or not metric:
        raise ContractError("INVALID_TWIN_STATE_PATCH")
    value = finite_number(value)
    observed_at = iso_time(parse_time(body.get("observed_at")))
    source_sequence = body.get("source_sequence")
    if not isinstance(source_sequence, str) or not source_sequence:
        raise ContractError("INVALID_TWIN_STATE_PATCH")
    client = _adt_client()
    try:
        current = client.get_digital_twin(twin_id)
    except ResourceNotFoundError:
        model_id = os.getenv("V2_ADT_MODEL_ID", "dtmi:twin2multicloud:poc:TwinNode;1")
        client.upsert_digital_twin(
            twin_id,
            {
                "$metadata": {"$model": model_id},
                "nodeId": str(body.get("source_id") or twin_id),
                "provider": os.getenv("V2_HOT_PROVIDER", "azure"),
                "status": "active",
                "lastUpdate": observed_at,
                "sourceSequence": source_sequence,
                "lastEventId": event_id(validated),
                "metric": metric,
                "value": value,
            },
        )
        return
    if current.get("lastEventId") == event_id(validated):
        return
    client.update_digital_twin(
        twin_id,
        [
            {"op": "add", "path": "/status", "value": "active"},
            {
                "op": "add",
                "path": "/lastUpdate",
                "value": observed_at,
            },
            {"op": "add", "path": "/sourceSequence", "value": source_sequence},
            {"op": "add", "path": "/lastEventId", "value": event_id(validated)},
            {"op": "add", "path": "/metric", "value": metric},
            {"op": "add", "path": "/value", "value": value},
        ],
    )


def _read_history(params: Mapping[str, Any]) -> dict[str, Any]:
    query, start, end = parse_raw_history_query(params)
    hmac_key = os.getenv("V2_CURSOR_HMAC_KEY", "")
    digest = raw_history_query_digest(query, start, end)
    continuation = decode_cursor(
        query["cursor"], hmac_key=hmac_key, query_digest=digest
    )
    result = _cosmos_container().query_items(
        query=cosmos_raw_history_statement(query["bucket_seconds"]),
        parameters=[
            {"name": "@device_id", "value": query["device_id"]},
            {"name": "@metric", "value": query["metric"]},
            {"name": "@from", "value": iso_time(start)},
            {"name": "@to", "value": iso_time(end)},
        ],
        partition_key=query["device_id"],
        max_item_count=query["limit"],
    )
    pages = result.by_page(continuation_token=continuation)
    try:
        documents = list(next(pages))
    except StopIteration:
        documents = []
    next_token = pages.continuation_token
    next_cursor = (
        encode_cursor(next_token, hmac_key=hmac_key, query_digest=digest)
        if next_token
        else None
    )
    return {
        "schema_version": "raw-history-query.v1",
        "device_id": query["device_id"],
        "metric": query["metric"],
        "points": normalize_history_points(documents, query["bucket_seconds"]),
        "next_cursor": next_cursor,
        "truncated": bool(next_token),
    }


def _raw_history_payload(params: Mapping[str, Any]) -> dict[str, Any]:
    if not params:
        return {
            "schema_version": "raw-history-health.v1",
            "status": "ready",
        }
    return _read_history(params)


if EVENTING_DELIVERY_ENDPOINT_ENABLED:

    @app.function_name(name="v2-eventing-domain-delivery")
    @app.route(
        route="eventing-delivery/v1",
        methods=["POST"],
        auth_level=func.AuthLevel.FUNCTION,
    )
    def eventing_domain_delivery(req: func.HttpRequest) -> func.HttpResponse:
        """Accept only authenticated same-cloud Event Layer deliveries."""

        try:
            payload = decode_json_object(req.get_body())
            eventing_delivery = payload.get("eventing_delivery")
            if eventing_delivery is None:
                _consume(payload)
            elif (
                set(payload) == {"eventing_delivery"}
                and isinstance(eventing_delivery, Mapping)
                and set(eventing_delivery) == {"consumer_role", "event"}
                and isinstance(eventing_delivery.get("consumer_role"), str)
                and isinstance(eventing_delivery.get("event"), Mapping)
            ):
                _consume_eventing_delivery(
                    str(eventing_delivery["consumer_role"]),
                    eventing_delivery["event"],
                )
            else:
                raise ContractError("INVALID_EVENTING_DELIVERY")
            return _reader_response(
                202,
                {
                    "schema_version": "event-delivery-result.v1",
                    "accepted": 1,
                },
            )
        except ContractError as exc:
            return _reader_response(
                exc.status,
                {
                    "schema_version": "event-delivery-error.v1",
                    "error_code": exc.code,
                },
            )


if REMOTE_TELEMETRY_ENABLED:

    @app.function_name(name="v2-remote-telemetry-consumer")
    @app.event_hub_message_trigger(
        arg_name="messages",
        event_hub_name="%V2_REMOTE_TELEMETRY_HUB_NAME%",
        connection="V2_REMOTE_TELEMETRY",
        cardinality="many",
        consumer_group="$Default",
    )
    def remote_telemetry_consumer(messages: list[func.EventHubEvent]) -> None:
        """Consume provider-managed Event Hubs batches after durable landing."""

        try:
            for event in _event_hub_events(messages):
                _consume(event)
        except ContractError as exc:
            raise RuntimeError(exc.code) from None


if BRIDGE_TELEMETRY_ENABLED:

    @app.function_name(name="v2-cross-cloud-telemetry-bridge")
    @app.retry(
        strategy="exponential_backoff",
        max_retry_count="5",
        minimum_interval="00:00:01",
        maximum_interval="00:00:32",
    )
    @app.event_hub_message_trigger(
        arg_name="messages",
        event_hub_name="%V2_BRIDGE_TELEMETRY_HUB_NAME%",
        connection="V2_BRIDGE_TELEMETRY",
        cardinality="many",
        consumer_group="$Default",
    )
    def cross_cloud_telemetry_bridge(
        messages: list[func.EventHubEvent],
        context: func.Context,
    ) -> None:
        """Checkpoint the source Event Hub only after durable target acceptance."""

        from phase8_eventing.azure.runtime import event_hub_batch

        event_hub_batch(
            messages,
            attempt_count=_event_hub_delivery_attempt(context),
        )


if BRIDGE_EVENT_TELEMETRY_ENABLED:

    @app.function_name(name="v2-cross-cloud-event-received-bridge")
    @app.retry(
        strategy="exponential_backoff",
        max_retry_count="5",
        minimum_interval="00:00:01",
        maximum_interval="00:00:32",
    )
    @app.event_hub_message_trigger(
        arg_name="messages",
        event_hub_name="%V2_EVENTING_RECEIVED_HUB_NAME%",
        connection="V2_EVENTING",
        cardinality="many",
        consumer_group="bridge-received",
    )
    def cross_cloud_event_received_bridge(
        messages: list[func.EventHubEvent],
        context: func.Context,
    ) -> None:
        from phase8_eventing.azure.runtime import event_hub_batch

        event_hub_batch(
            messages,
            attempt_count=_event_hub_delivery_attempt(context),
        )

    @app.function_name(name="v2-cross-cloud-event-processed-bridge")
    @app.retry(
        strategy="exponential_backoff",
        max_retry_count="5",
        minimum_interval="00:00:01",
        maximum_interval="00:00:32",
    )
    @app.event_hub_message_trigger(
        arg_name="messages",
        event_hub_name="%V2_EVENTING_PROCESSED_HUB_NAME%",
        connection="V2_EVENTING",
        cardinality="many",
        consumer_group="bridge-processed",
    )
    def cross_cloud_event_processed_bridge(
        messages: list[func.EventHubEvent],
        context: func.Context,
    ) -> None:
        from phase8_eventing.azure.runtime import event_hub_batch

        event_hub_batch(
            messages,
            attempt_count=_event_hub_delivery_attempt(context),
        )


if BRIDGE_CONTROL_ENABLED:

    @app.function_name(name="v2-cross-cloud-control-bridge")
    @app.service_bus_queue_trigger(
        arg_name="message",
        queue_name="%V2_BRIDGE_CONTROL_QUEUE_NAME%",
        connection="V2_SERVICE_BUS",
        is_sessions_enabled=True,
    )
    def cross_cloud_control_bridge(message: func.ServiceBusMessage) -> None:
        """Complete the source control message only after target acceptance."""

        from phase8_eventing.azure.runtime import service_bus_message

        service_bus_message(message)


if BRIDGE_EVENT_CONTROL_ENABLED:

    @app.function_name(name="v2-cross-cloud-event-control-bridge")
    @app.service_bus_topic_trigger(
        arg_name="message",
        topic_name="%V2_EVENTING_CONTROL_TOPIC_NAME%",
        subscription_name="%V2_EVENTING_BRIDGE_CONTROL_SUBSCRIPTION_NAME%",
        connection="V2_EVENTING_SERVICE_BUS",
        is_sessions_enabled=True,
    )
    def cross_cloud_event_control_bridge(
        message: func.ServiceBusMessage,
    ) -> None:
        from phase8_eventing.azure.runtime import service_bus_message

        service_bus_message(message)


if DOMAIN_CONSUMER_ENABLED:

    @app.function_name(name="v2-domain-event-consumer")
    @app.service_bus_queue_trigger(
        arg_name="message",
        queue_name="%V2_DOMAIN_QUEUE_NAME%",
        connection="V2_SERVICE_BUS",
        is_sessions_enabled=True,
    )
    def domain_event_consumer(message: func.ServiceBusMessage) -> None:
        """Consume ordered domain/control events from a session-enabled queue."""

        try:
            _consume(_service_bus_event(message))
        except ContractError as exc:
            raise RuntimeError(exc.code) from None


if IOT_PROCESSOR_ENABLED:

    @app.function_name(name="v2-iot-telemetry-adapter")
    @app.event_hub_message_trigger(
        arg_name="messages",
        event_hub_name="%V2_IOT_HUB_NAME%",
        connection="V2_IOT_HUB",
        cardinality="many",
        consumer_group="$Default",
    )
    def iot_telemetry_adapter(messages: list[func.EventHubEvent]) -> None:
        """Adapt the existing simulator payload from IoT Hub and enqueue it."""

        try:
            for message in messages:
                payload = decode_json_object(message.get_body())
                event = build_ingress_event(
                    payload,
                    deployment_id=os.getenv("DEPLOYMENT_ID", "local-poc"),
                    default_metric=os.getenv("V2_DEFAULT_METRIC", "temperature"),
                )
                if _six_layer_eventing():
                    _publish_eventing_stream(event)
                elif os.getenv("V2_L2_PROVIDER") == "azure":
                    _enqueue(event)
                else:
                    _publish_telemetry(event)
        except ContractError as exc:
            raise RuntimeError(exc.code) from None


if RAW_HISTORY_ENABLED:

    @app.function_name(name="v2-raw-history-reader")
    @app.route(
        route="raw-history/v1",
        methods=["GET"],
        auth_level=func.AuthLevel.FUNCTION,
    )
    def raw_history_reader(req: func.HttpRequest) -> func.HttpResponse:
        """Serve the bounded L3-hot query used only by the L5 datasource."""

        correlation_id = str(uuid.uuid4())
        try:
            payload = _raw_history_payload(dict(req.params))
            payload["correlation_id"] = correlation_id
            return _reader_response(200, payload)
        except ContractError as exc:
            return _reader_response(
                exc.status,
                {
                    "schema_version": "architecture-runtime-error.v1",
                    "code": exc.code,
                    "correlation_id": correlation_id,
                },
            )
        except Exception:
            logging.exception(
                "Azure v2 raw-history query failed correlation_id=%s",
                correlation_id,
            )
            return _reader_response(
                503,
                {
                    "schema_version": "architecture-runtime-error.v1",
                    "code": "READER_UNAVAILABLE",
                    "correlation_id": correlation_id,
                },
            )
