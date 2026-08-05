"""Bounded AWS runtime handlers for ``five-layer-baseline@2``.

One content-addressed ZIP is reused by the event adapter, processor, and
raw-history reader. Each Lambda selects an explicit handler entry point.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import math
import os
from typing import Any, Iterable, Mapping
import uuid

import boto3
from botocore.exceptions import ClientError


PROFILE = "five-layer-baseline@2"
MAX_POINTS = 1000
MAX_RAW_RANGE = timedelta(hours=24)
MAX_AGGREGATE_RANGE = timedelta(days=30)
EVENT_TELEMETRY_RECEIVED = "telemetry.received.v1"
EVENT_TELEMETRY_PROCESSED = "telemetry.processed.v1"
EVENT_TWIN_STATE_UPSERTED = "twin.state.upserted"
EVENT_DEVICE_COMMAND_REQUESTED = "device.command.requested.v1"


class ContractError(ValueError):
    """A stable, payload-free runtime contract failure."""

    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def _client(service: str):
    return boto3.client(service)


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _required_text(value: Any, *, code: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise ContractError(code)
    return value


def _partition_key(payload: Mapping[str, Any]) -> str:
    body = _event_body(payload)
    return _required_text(
        body.get("device_id")
        or payload.get("source_id")
        or body.get("source_id")
        or body.get("twin_id"),
        code="INVALID_PARTITION_KEY",
    )


def _event_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("event_id")
    if value is None:
        value = str(uuid.uuid5(uuid.NAMESPACE_URL, _canonical_json(payload)))
    return _required_text(value, code="INVALID_EVENT_ID")


def _event_body(event: Mapping[str, Any]) -> Mapping[str, Any]:
    body = event.get("payload")
    return body if isinstance(body, Mapping) else event


def _event_type(event: Mapping[str, Any]) -> str:
    value = event.get("event_type") or event.get("channel")
    return str(value or EVENT_TELEMETRY_RECEIVED)


def _derive_event(
    source: Mapping[str, Any],
    *,
    event_type: str,
    producer: str,
    body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one deterministic child event without provider route metadata."""

    source_id = _event_id(source)
    child_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{event_type}"))
    occurred_at = source.get("occurred_at") or _event_body(source).get("event_time")
    if not isinstance(occurred_at, str):
        occurred_at = _iso(datetime.now(timezone.utc))
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": child_id,
        "event_type": event_type,
        "deployment_id": str(source.get("deployment_id") or os.environ.get("DEPLOYMENT_ID", "local-poc")),
        "source_id": _partition_key(source),
        "source_sequence": str(source.get("source_sequence") or source_id),
        "occurred_at": occurred_at,
        "correlation_id": str(source.get("correlation_id") or source_id),
        "causation_id": source_id,
        "producer": producer,
        "payload": dict(body or _event_body(source)),
    }


def _ingress_event(payload: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _event_id(payload)
    source_body = _event_body(payload)
    occurred_at = source_body.get("event_time")
    if not isinstance(occurred_at, str):
        occurred_at = _iso(datetime.now(timezone.utc))
    body = dict(source_body)
    body.pop("event_type", None)
    body.pop("channel", None)
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": event_id,
        "event_type": EVENT_TELEMETRY_RECEIVED,
        "deployment_id": os.environ.get("DEPLOYMENT_ID", "local-poc"),
        "source_id": _partition_key(payload),
        "source_sequence": str(payload.get("source_sequence") or event_id),
        "occurred_at": occurred_at,
        "correlation_id": str(payload.get("correlation_id") or event_id),
        "causation_id": event_id,
        "producer": "component.device-ingress",
        "payload": body,
    }


def _decoded_records(event: Mapping[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    records = event.get("Records")
    if not isinstance(records, list):
        yield "direct", dict(event)
        return
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ContractError("INVALID_RECORD")
        source = str(record.get("eventSource") or record.get("EventSource") or "")
        if source == "aws:kinesis":
            encoded = record.get("kinesis", {}).get("data")
            if not isinstance(encoded, str):
                raise ContractError("INVALID_KINESIS_RECORD")
            raw = base64.b64decode(encoded, validate=True).decode("utf-8")
        elif source == "aws:sqs":
            raw = record.get("body")
            if not isinstance(raw, str):
                raise ContractError("INVALID_SQS_RECORD")
        else:
            raw = _canonical_json(record)
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ContractError("INVALID_ENVELOPE")
        yield str(record.get("messageId") or record.get("eventID") or index), payload


def _put_stream(payload: Mapping[str, Any]) -> None:
    stream_arn = os.environ.get("TELEMETRY_STREAM_ARN", "")
    if not stream_arn:
        raise ContractError("REMOTE_ROUTE_NOT_CONFIGURED", 503)
    _client("kinesis").put_record(
        StreamARN=stream_arn,
        Data=_canonical_json(payload).encode("utf-8"),
        PartitionKey=_partition_key(payload),
    )


def _enqueue(payload: Mapping[str, Any]) -> None:
    queue_url = os.environ.get("EVENT_QUEUE_URL", "")
    if not queue_url:
        raise ContractError("LOCAL_QUEUE_NOT_CONFIGURED", 503)
    event_id = _event_id(payload)
    _client("sqs").send_message(
        QueueUrl=queue_url,
        MessageBody=_canonical_json(payload),
        MessageGroupId=_partition_key(payload),
        MessageDeduplicationId=event_id,
    )


def _materialize_twin_projection(payload: Mapping[str, Any]) -> None:
    workspace = os.environ.get("TWINMAKER_WORKSPACE", "")
    if not workspace:
        raise ContractError("TWIN_PROJECTION_TARGET_NOT_CONFIGURED", 503)
    body = _event_body(payload)
    value = body.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContractError("INVALID_TWIN_VALUE")
    observed_at = _parse_time(body.get("observed_at") or body.get("stored_at"))
    _client("iottwinmaker").batch_put_property_values(
        workspaceId=workspace,
        entries=[
            {
                "entryId": _event_id(payload)[:64],
                "entityPropertyReference": {
                    "entityId": _required_text(body.get("twin_id"), code="INVALID_TWIN_ID"),
                    "componentName": "telemetry",
                    "propertyName": _required_text(body.get("metric"), code="INVALID_METRIC"),
                },
                "propertyValues": [
                    {
                        "timestamp": observed_at,
                        "value": {"doubleValue": float(value)},
                    }
                ],
            }
        ],
    )


def event_adapter(event: Mapping[str, Any], _context: Any) -> dict[str, Any]:
    """Adapt local IoT and inbound Kinesis records without public bridge URLs."""

    try:
        accepted = 0
        for _, decoded in _decoded_records(event):
            payload = _ingress_event(decoded)
            if os.environ.get("LOCAL_PROCESSING", "false").lower() == "true":
                _enqueue(payload)
            else:
                _put_stream(payload)
            accepted += 1
        return {"schema_version": "event-adapter-result.v1", "accepted": accepted}
    except Exception as exc:
        if isinstance(exc, ContractError):
            raise RuntimeError(exc.code) from None
        raise RuntimeError("EVENT_ADAPTER_RETRYABLE_FAILURE") from None


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ContractError("INVALID_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None:
        raise ContractError("INVALID_TIMESTAMP")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _number(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ContractError("INVALID_NUMERIC_VALUE")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ContractError("INVALID_NUMERIC_VALUE") from exc
    if not result.is_finite():
        raise ContractError("INVALID_NUMERIC_VALUE")
    return result


def _existing_raw(table: str, device_id: str, event_id: str) -> dict[str, Any] | None:
    response = _client("dynamodb").get_item(
        TableName=table,
        Key={"device_id": {"S": device_id}, "event_id": {"S": event_id}},
        ConsistentRead=True,
    )
    return response.get("Item")


def _write_raw_and_rollup(payload: Mapping[str, Any]) -> None:
    raw_table = os.environ.get("RAW_TABLE_NAME", "")
    rollup_table = os.environ.get("ROLLUP_TABLE_NAME", "")
    if not raw_table or not rollup_table:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)

    body = dict(_event_body(payload))
    event_id = _event_id(payload)
    device_id = _partition_key(payload)
    metric = _required_text(body.get("metric"), code="INVALID_METRIC")
    value = _number(body.get("value"))
    event_time = _parse_time(body.get("event_time") or payload.get("occurred_at"))
    stored_at = _parse_time(body.get("stored_at") or _iso(datetime.now(timezone.utc)))
    body["stored_at"] = _iso(stored_at)
    stored_at_text = _iso(stored_at)
    sort_key = f"{stored_at_text}#{event_id}"
    canonical_payload = _canonical_json(dict(payload))
    payload_digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    hot_days = int(os.environ.get("HOT_BOUNDARY_DAYS", "30"))
    grace_hours = int(os.environ.get("SOURCE_EXPIRY_GRACE_HOURS", "48"))
    expires_at = int((stored_at + timedelta(days=hot_days, hours=grace_hours)).timestamp())
    minute = stored_at.minute - stored_at.minute % 5
    storage_window = _iso(stored_at.replace(minute=minute, second=0, microsecond=0))
    bucket_start = _iso(stored_at.replace(minute=0, second=0, microsecond=0))
    rollup_key = f"{device_id}#{metric}"
    dynamodb = _client("dynamodb")

    for _ in range(3):
        existing_raw = _existing_raw(raw_table, device_id, event_id)
        if existing_raw:
            if existing_raw.get("payload_digest", {}).get("S") == payload_digest:
                return
            raise ContractError("IDEMPOTENCY_CONFLICT", 409)

        current = dynamodb.get_item(
            TableName=rollup_table,
            Key={"device_metric": {"S": rollup_key}, "bucket_start": {"S": bucket_start}},
            ConsistentRead=True,
        ).get("Item")
        old_version = int(current.get("version", {}).get("N", "0")) if current else 0
        old_count = int(current.get("count", {}).get("N", "0")) if current else 0
        old_sum = Decimal(current.get("sum", {}).get("N", "0")) if current else Decimal(0)
        old_min = Decimal(current.get("min", {}).get("N", str(value))) if current else value
        old_max = Decimal(current.get("max", {}).get("N", str(value))) if current else value
        rollup = {
            "device_metric": {"S": rollup_key},
            "bucket_start": {"S": bucket_start},
            "device_id": {"S": device_id},
            "metric": {"S": metric},
            "count": {"N": str(old_count + 1)},
            "sum": {"N": str(old_sum + value)},
            "min": {"N": str(min(old_min, value))},
            "max": {"N": str(max(old_max, value))},
            "version": {"N": str(old_version + 1)},
            "expires_at": {"N": str(expires_at)},
        }
        condition = "attribute_not_exists(device_metric)" if current is None else "#version = :version"
        condition_names = None if current is None else {"#version": "version"}
        condition_values = None if current is None else {":version": {"N": str(old_version)}}
        rollup_put: dict[str, Any] = {
            "TableName": rollup_table,
            "Item": rollup,
            "ConditionExpression": condition,
        }
        if condition_names:
            rollup_put["ExpressionAttributeNames"] = condition_names
            rollup_put["ExpressionAttributeValues"] = condition_values
        try:
            dynamodb.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": raw_table,
                            "Item": {
                                "device_id": {"S": device_id},
                                "event_id": {"S": event_id},
                                "stored_at_event_id": {"S": sort_key},
                                "storage_window": {"S": storage_window},
                                "metric": {"S": metric},
                                "value": {"N": str(value)},
                                "event_time": {"S": _iso(event_time)},
                                "stored_at": {"S": stored_at_text},
                                "payload_digest": {"S": payload_digest},
                                "payload_json": {"S": canonical_payload},
                                "expires_at": {"N": str(expires_at)},
                            },
                            "ConditionExpression": "attribute_not_exists(device_id) AND attribute_not_exists(event_id)",
                        }
                    },
                    {"Put": rollup_put},
                ],
                ClientRequestToken=hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:36],
            )
            return
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                raise
    raise ContractError("ROLLUP_CONFLICT_EXHAUSTED", 503)


def processor(event: Mapping[str, Any], _context: Any) -> dict[str, Any]:
    """Persist raw+rollup atomically or publish to the reviewed remote outbox."""

    failures = []
    accepted = 0
    for record_id, payload in _decoded_records(event):
        try:
            if _event_type(payload) != EVENT_TELEMETRY_RECEIVED:
                raise ContractError("UNEXPECTED_PROCESSOR_EVENT")
            processed = _derive_event(
                payload,
                event_type=EVENT_TELEMETRY_PROCESSED,
                producer="component.telemetry-processor",
            )
            if os.environ.get("HOT_PROVIDER") == "aws":
                _persist_and_project(processed)
            else:
                _put_stream(processed)
            accepted += 1
        except Exception:
            if isinstance(event.get("Records"), list):
                failures.append({"itemIdentifier": record_id})
            else:
                raise RuntimeError("PROCESSING_RETRYABLE_FAILURE") from None
    return {
        "schema_version": "processor-result.v1",
        "accepted": accepted,
        "batchItemFailures": failures,
    }


def _persist_and_project(event: Mapping[str, Any]) -> None:
    _write_raw_and_rollup(event)
    body = dict(_event_body(event))
    if body.get("projection_candidate") is not True:
        return
    body["observed_at"] = (
        body.get("observed_at")
        or body.get("event_time")
        or event.get("occurred_at")
    )
    projection = _derive_event(
        event,
        event_type=EVENT_TWIN_STATE_UPSERTED,
        producer="component.historical-persistence",
        body=body,
    )
    if os.environ.get("TWIN_PROVIDER") == "aws":
        _materialize_twin_projection(projection)
    else:
        _put_stream(projection)


def domain_consumer(event: Mapping[str, Any], _context: Any) -> dict[str, Any]:
    """Dispatch target-broker records to the responsibility named by event type."""

    failures = []
    accepted = 0
    for record_id, payload in _decoded_records(event):
        try:
            kind = _event_type(payload)
            if kind == EVENT_TELEMETRY_RECEIVED:
                result = processor(payload, None)
                if result["batchItemFailures"]:
                    raise ContractError("PROCESSING_RETRYABLE_FAILURE", 503)
            elif kind == EVENT_TELEMETRY_PROCESSED:
                _persist_and_project(payload)
            elif kind == EVENT_TWIN_STATE_UPSERTED:
                _materialize_twin_projection(payload)
            elif kind == EVENT_DEVICE_COMMAND_REQUESTED:
                raise ContractError("DEVICE_COMMAND_ADAPTER_NOT_CONFIGURED", 503)
            else:
                raise ContractError("UNKNOWN_DOMAIN_EVENT")
            accepted += 1
        except Exception:
            if isinstance(event.get("Records"), list):
                failures.append({"itemIdentifier": record_id})
            else:
                raise RuntimeError("DOMAIN_CONSUMER_RETRYABLE_FAILURE") from None
    return {
        "schema_version": "domain-consumer-result.v1",
        "accepted": accepted,
        "batchItemFailures": failures,
    }


def _reader_response(status: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": _canonical_json(payload),
    }


def _verify_reader_key(event: Mapping[str, Any]) -> bytes:
    expected = os.environ.get("READER_KEY_SHA256", "")
    if len(expected) != 64:
        raise ContractError("READER_NOT_PROVISIONED", 503)
    headers = {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}
    supplied = headers.get("x-twin-reader-key", "")
    actual = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise ContractError("READER_UNAUTHORIZED", 401)
    return bytes.fromhex(expected)


def _query_params(event: Mapping[str, Any]) -> tuple[dict[str, Any], datetime, datetime]:
    params = event.get("queryStringParameters") or {}
    if not isinstance(params, Mapping):
        raise ContractError("INVALID_QUERY")
    device_id = _required_text(params.get("device_id"), code="INVALID_DEVICE_ID")
    metric = _required_text(params.get("metric"), code="INVALID_METRIC")
    start = _parse_time(params.get("from"))
    end = _parse_time(params.get("to"))
    if start >= end:
        raise ContractError("INVALID_TIME_RANGE")
    try:
        bucket = int(params.get("bucket_seconds", "0"))
        limit = int(params.get("limit", str(MAX_POINTS)))
    except (TypeError, ValueError) as exc:
        raise ContractError("INVALID_QUERY") from exc
    if bucket not in (0, 3600) or not 1 <= limit <= MAX_POINTS:
        raise ContractError("INVALID_QUERY")
    if end - start > (MAX_RAW_RANGE if bucket == 0 else MAX_AGGREGATE_RANGE):
        raise ContractError("QUERY_RANGE_EXCEEDED")
    return {
        "device_id": device_id,
        "metric": metric,
        "bucket_seconds": bucket,
        "limit": limit,
        "cursor": params.get("cursor"),
    }, start, end


def _cursor_decode(value: Any, key: bytes, query_digest: str) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 16384 or "." not in value:
        raise ContractError("INVALID_CURSOR")
    encoded, signature = value.split(".", 1)
    expected = hmac.new(key, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ContractError("INVALID_CURSOR")
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("INVALID_CURSOR") from exc
    if payload.get("profile") != PROFILE or payload.get("query") != query_digest:
        raise ContractError("INVALID_CURSOR")
    if int(payload.get("expires_at", 0)) < int(datetime.now(timezone.utc).timestamp()):
        raise ContractError("CURSOR_EXPIRED")
    return payload.get("key")


def _cursor_encode(last_key: Mapping[str, Any], key: bytes, query_digest: str) -> str:
    payload = {
        "profile": PROFILE,
        "query": query_digest,
        "expires_at": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
        "key": last_key,
    }
    encoded = base64.urlsafe_b64encode(_canonical_json(payload).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{encoded}.{hmac.new(key, encoded.encode('ascii'), hashlib.sha256).hexdigest()}"


def _attribute(item: Mapping[str, Any], name: str) -> Any:
    value = item.get(name, {})
    if "S" in value:
        return value["S"]
    if "N" in value:
        number = Decimal(value["N"])
        return int(number) if number == number.to_integral() else float(number)
    return None


def raw_history_reader(event: Mapping[str, Any], _context: Any) -> dict[str, Any]:
    """Serve only the bounded ``raw_history_query.v1`` contract."""

    correlation_id = str(uuid.uuid4())
    try:
        cursor_key = _verify_reader_key(event)
        query, start, end = _query_params(event)
        query_digest = hashlib.sha256(
            _canonical_json({**query, "cursor": None, "from": _iso(start), "to": _iso(end)}).encode("utf-8")
        ).hexdigest()
        exclusive_start_key = _cursor_decode(query["cursor"], cursor_key, query_digest)
        dynamodb = _client("dynamodb")
        if query["bucket_seconds"] == 0:
            table = os.environ["RAW_TABLE_NAME"]
            response = dynamodb.query(
                TableName=table,
                IndexName="device-stored-at-index",
                KeyConditionExpression="device_id = :device AND stored_at_event_id BETWEEN :start AND :end",
                FilterExpression="metric = :metric",
                ExpressionAttributeValues={
                    ":device": {"S": query["device_id"]},
                    ":start": {"S": f"{_iso(start)}#"},
                    ":end": {"S": f"{_iso(end)}#~"},
                    ":metric": {"S": query["metric"]},
                },
                Limit=query["limit"],
                **({"ExclusiveStartKey": exclusive_start_key} if exclusive_start_key else {}),
            )
            points = [
                {
                    "stored_at": _attribute(item, "stored_at"),
                    "event_time": _attribute(item, "event_time"),
                    "value": _attribute(item, "value"),
                }
                for item in response.get("Items", [])
            ]
        else:
            table = os.environ["ROLLUP_TABLE_NAME"]
            response = dynamodb.query(
                TableName=table,
                KeyConditionExpression="device_metric = :key AND bucket_start BETWEEN :start AND :end",
                ExpressionAttributeValues={
                    ":key": {"S": f"{query['device_id']}#{query['metric']}"},
                    ":start": {"S": _iso(start)},
                    ":end": {"S": _iso(end)},
                },
                Limit=query["limit"],
                **({"ExclusiveStartKey": exclusive_start_key} if exclusive_start_key else {}),
            )
            points = []
            for item in response.get("Items", []):
                count = _attribute(item, "count")
                total = _attribute(item, "sum")
                points.append(
                    {
                        "bucket_start": _attribute(item, "bucket_start"),
                        "min": _attribute(item, "min"),
                        "max": _attribute(item, "max"),
                        "avg": total / count if count else 0,
                        "count": count,
                    }
                )
        last_key = response.get("LastEvaluatedKey")
        next_cursor = _cursor_encode(last_key, cursor_key, query_digest) if last_key else None
        return _reader_response(
            200,
            {
                "schema_version": "raw-history-query.v1",
                "device_id": query["device_id"],
                "metric": query["metric"],
                "points": points,
                "next_cursor": next_cursor,
                "truncated": bool(last_key),
                "correlation_id": correlation_id,
            },
        )
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
        return _reader_response(
            503,
            {
                "schema_version": "architecture-runtime-error.v1",
                "code": "READER_UNAVAILABLE",
                "correlation_id": correlation_id,
            },
        )
