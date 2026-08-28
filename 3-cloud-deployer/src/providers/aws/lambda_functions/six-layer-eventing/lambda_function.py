"""AWS Lambda delivery adapter for the independent Six-layer Event Layer.

The adapter consumes only the Event Layer's Kinesis stream and SQS FIFO
subscription.  It acknowledges telemetry after Lambda's durable asynchronous
invocation queue accepts it and acknowledges control after AWS IoT Commands
accepts it. Exhausted control deliveries are written to the bounded SQS dead-
letter queue before acknowledgement; exhausted telemetry uses the configured
S3 event-source destination.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any, Mapping
import uuid

import boto3


SCHEMA_VERSION = "canonical-domain-event.v1"
MAX_EVENT_BYTES = 96 * 1024
TELEMETRY_EVENT = "telemetry.received.v1"
PROCESSED_EVENT = "telemetry.processed.v1"
CONTROL_EVENT = "device.command.requested.v1"
COMMAND_OUTCOME_EVENT = "device.command.outcome.v1"
PROCESSING_EVENT_TYPES = {
    TELEMETRY_EVENT,
    PROCESSED_EVENT,
    "event.matched.v1",
    "notification.requested.v1",
    "extension.action.outcome.v1",
    "notification.workflow.outcome.v1",
    COMMAND_OUTCOME_EVENT,
}
CONTROL_PROCESSING_EVENT_TYPES = PROCESSING_EVENT_TYPES - {
    TELEMETRY_EVENT,
    PROCESSED_EVENT,
}
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
DIAGNOSTIC_TRACE_PATTERN = re.compile(r"^(?:TRACE|VERIFY)-[A-Z0-9]{8,48}$")


class DeliveryError(ValueError):
    """Stable payload-free delivery failure."""


def _client(service: str):
    if service == "iot-jobs-data":
        endpoint = _required_environment("IOT_COMMANDS_ENDPOINT")
        return boto3.client(service, endpoint_url=f"https://{endpoint}")
    return boto3.client(service)


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _diagnostic_checkpoint(event: Mapping[str, Any]) -> None:
    payload = event.get("payload")
    candidates = (
        event.get("trace_id"),
        event.get("source_sequence"),
        payload.get("trace_id") if isinstance(payload, Mapping) else None,
        payload.get("source_sequence") if isinstance(payload, Mapping) else None,
    )
    trace_id = next(
        (
            value
            for value in candidates
            if isinstance(value, str) and DIAGNOSTIC_TRACE_PATTERN.fullmatch(value)
        ),
        None,
    )
    if trace_id is None:
        return
    event_type = str(event.get("event_type") or "unknown")
    stage = {
        CONTROL_EVENT: "event_layer_command_durable",
        COMMAND_OUTCOME_EVENT: "outcome_event_durable",
    }.get(event_type, "event_layer_durable")
    checkpoint = {
        "schema_version": "diagnostic-checkpoint.v1",
        "trace_id": trace_id,
        "stage": stage,
        "provider": "aws",
        "component": "eventing",
        "status": "passed",
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_id": str(event.get("event_id") or trace_id),
        "event_type": event_type,
    }
    print(
        "T2MC_CHECKPOINT "
        + json.dumps(
            checkpoint, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
    )


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or len(value.encode("utf-8")) > 2048:
        raise DeliveryError("EVENT_RUNTIME_NOT_CONFIGURED")
    return value


def _decode_record(record: Mapping[str, Any]) -> tuple[str, str, int, dict[str, Any]]:
    source = str(record.get("eventSource") or record.get("EventSource") or "")
    if source == "aws:kinesis":
        record_id = record.get("eventID")
        encoded = (record.get("kinesis") or {}).get("data")
        if not isinstance(record_id, str) or not isinstance(encoded, str):
            raise DeliveryError("INVALID_SOURCE_RECORD")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (TypeError, ValueError) as exc:
            raise DeliveryError("INVALID_SOURCE_RECORD") from exc
        attempt = 1
    elif source == "aws:sqs":
        record_id = record.get("messageId")
        raw = record.get("body")
        attributes = record.get("attributes") or {}
        if not isinstance(record_id, str) or not isinstance(raw, str):
            raise DeliveryError("INVALID_SOURCE_RECORD")
        try:
            attempt = int(str(attributes.get("ApproximateReceiveCount", "1")))
        except ValueError as exc:
            raise DeliveryError("INVALID_SOURCE_RECORD") from exc
    else:
        raise DeliveryError("INVALID_SOURCE_RECORD")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise DeliveryError("INVALID_SOURCE_RECORD") from exc
    if not isinstance(payload, dict):
        raise DeliveryError("INVALID_SOURCE_RECORD")
    return record_id, source, max(1, attempt), payload


def _validate_event(event: Mapping[str, Any]) -> None:
    if set(event) != REQUIRED_FIELDS or event.get("schema_version") != SCHEMA_VERSION:
        raise DeliveryError("INVALID_CANONICAL_EVENT")
    if event.get("event_type") not in {*PROCESSING_EVENT_TYPES, CONTROL_EVENT}:
        raise DeliveryError("UNSUPPORTED_EVENT_TYPE")
    for field in REQUIRED_FIELDS - {"payload"}:
        if not isinstance(event.get(field), str) or not event[field]:
            raise DeliveryError("INVALID_CANONICAL_EVENT")
    if not isinstance(event.get("payload"), Mapping):
        raise DeliveryError("INVALID_CANONICAL_EVENT")
    try:
        encoded = _canonical_bytes(event)
    except (TypeError, ValueError) as exc:
        raise DeliveryError("INVALID_CANONICAL_EVENT") from exc
    if len(encoded) > MAX_EVENT_BYTES:
        raise DeliveryError("INVALID_CANONICAL_EVENT")


def _deliver_processing(event: Mapping[str, Any], role: str) -> bool:
    if role in {"audit", "realtime-visualization"}:
        return True
    hot_delivery = role in {"historical-persistence", "twin-state-update"} or (
        role == "control-router"
        and event.get("event_type")
        in {
            "extension.action.outcome.v1",
            "notification.workflow.outcome.v1",
            COMMAND_OUTCOME_EVENT,
        }
    )
    payload: Mapping[str, Any] = {
        "eventing_delivery": {
            "consumer_role": role,
            "event": event,
        }
    }
    response = _client("lambda").invoke(
        FunctionName=_required_environment(
            "HOT_FUNCTION_NAME" if hot_delivery else "PROCESSING_FUNCTION_NAME"
        ),
        InvocationType="Event",
        Payload=_canonical_bytes(payload),
    )
    return response.get("StatusCode") == 202


def _command_outcome(event: Mapping[str, Any], execution_id: str) -> dict[str, Any]:
    source_event_id = str(event["event_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{source_event_id}:{COMMAND_OUTCOME_EVENT}",
            )
        ),
        "event_type": COMMAND_OUTCOME_EVENT,
        "deployment_id": str(event["deployment_id"]),
        "source_id": str(event["source_id"]),
        "source_sequence": str(event["source_sequence"]),
        "occurred_at": str(event["occurred_at"]),
        "correlation_id": str(event["correlation_id"]),
        "causation_id": source_event_id,
        "producer": "component.device-command-adapter",
        "payload": {
            "device_id": str(event["payload"].get("device_id") or event["source_id"]),
            "invocation_id": source_event_id,
            "execution_id": execution_id,
            "status": "ACCEPTED",
        },
    }


def _publish_control_outcome(event: Mapping[str, Any], execution_id: str) -> bool:
    outcome = _command_outcome(event, execution_id)
    response = _client("sns").publish(
        TopicArn=_required_environment("CONTROL_TOPIC_ARN"),
        Message=_canonical_bytes(outcome).decode("utf-8"),
        MessageAttributes={
            "event_type": {
                "DataType": "String",
                "StringValue": COMMAND_OUTCOME_EVENT,
            }
        },
        MessageGroupId=str(outcome["source_id"]),
        MessageDeduplicationId=str(outcome["event_id"]),
    )
    return isinstance(response.get("MessageId"), str)


def _deliver_control(event: Mapping[str, Any]) -> bool:
    payload = event["payload"]
    device_id = payload.get("device_id") or event.get("source_id")
    if not isinstance(device_id, str) or not device_id:
        raise DeliveryError("INVALID_COMMAND_DEVICE")
    response = _client("iot-jobs-data").start_command_execution(
        targetArn=(
            f"arn:aws:iot:{_required_environment('AWS_REGION')}:"
            f"{_required_environment('AWS_ACCOUNT_ID')}:thing/{device_id}"
        ),
        commandArn=_required_environment("DEVICE_COMMAND_ARN"),
        parameters={"message": {"S": str(payload.get("message") or "Rule matched")}},
        executionTimeoutSeconds=300,
        clientToken=str(event["event_id"])[:64],
    )
    execution_id = response.get("executionId")
    return (
        isinstance(execution_id, str)
        and bool(execution_id)
        and (_publish_control_outcome(event, execution_id))
    )


def _write_control_terminal_failure(
    event: Mapping[str, Any],
    *,
    record_id: str,
    error_code: str,
    include_event: bool,
) -> bool:
    failure = {
        "schema_version": "event-delivery-failure.v1",
        "record_id": record_id,
        "event_id": str(event.get("event_id") or "invalid"),
        "correlation_id": str(event.get("correlation_id") or "invalid"),
        "error_code": error_code,
    }
    if include_event:
        failure["canonical_event"] = event
    data = _canonical_bytes(failure)
    digest = hashlib.sha256(data).hexdigest()
    response = _client("sqs").send_message(
        QueueUrl=_required_environment("CONTROL_FAILURE_QUEUE_URL"),
        MessageBody=data.decode("utf-8"),
        MessageGroupId=hashlib.sha256(
            str(event.get("source_id") or "invalid").encode("utf-8")
        ).hexdigest(),
        MessageDeduplicationId=digest,
    )
    return isinstance(response.get("MessageId"), str)


def lambda_handler(event: Mapping[str, Any], _context: object) -> dict[str, Any]:
    """Return Lambda partial-batch failures without exposing event payloads."""

    records = event.get("Records")
    if not isinstance(records, list) or not records:
        raise RuntimeError("INVALID_SOURCE_RECORD")
    failures: list[dict[str, str]] = []
    accepted = 0
    for raw_record in records:
        record_id = "invalid"
        source = ""
        attempt = 1
        payload: Mapping[str, Any] = {}
        validated = False
        try:
            if not isinstance(raw_record, Mapping):
                raise DeliveryError("INVALID_SOURCE_RECORD")
            record_id, source, attempt, payload = _decode_record(raw_record)
            _validate_event(payload)
            validated = True
            _diagnostic_checkpoint(payload)
            role = _required_environment("CONSUMER_ROLE")
            event_type = str(payload["event_type"])
            if source == "aws:kinesis" and (
                (role == "telemetry-processor" and event_type != TELEMETRY_EVENT)
                or (role != "telemetry-processor" and event_type != PROCESSED_EVENT)
            ):
                raise DeliveryError("EVENT_CHANNEL_MISMATCH")
            if source == "aws:sqs" and event_type == CONTROL_EVENT:
                delivered = _deliver_control(payload)
            elif source == "aws:sqs" and event_type in CONTROL_PROCESSING_EVENT_TYPES:
                delivered = _deliver_processing(payload, "control-router")
            elif source == "aws:kinesis":
                delivered = _deliver_processing(payload, role)
            else:
                raise DeliveryError("EVENT_CHANNEL_MISMATCH")
            if not delivered:
                raise DeliveryError("DESTINATION_NOT_ACCEPTED")
            accepted += 1
        except Exception as exc:
            error_code = (
                str(exc)
                if isinstance(exc, DeliveryError)
                else "DESTINATION_RETRYABLE_FAILURE"
            )
            terminal = source == "aws:sqs" and attempt >= int(
                os.environ.get("MAX_RECEIVE_COUNT", "6")
            )
            if terminal and _write_control_terminal_failure(
                payload,
                record_id=record_id,
                error_code=error_code,
                include_event=validated,
            ):
                accepted += 1
            else:
                failures.append({"itemIdentifier": record_id})
    return {
        "schema_version": "event-delivery-result.v1",
        "accepted": accepted,
        "batchItemFailures": failures,
    }


__all__ = ["DeliveryError", "lambda_handler"]
