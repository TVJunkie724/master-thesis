"""Finite, idempotent AWS hot-to-cool exporter for Five-layer v2.

Each scheduled Fargate task owns one deterministic DynamoDB storage-window
shard. Objects and manifests use conditional creation, so retries can verify
an identical result but can never overwrite a different history object.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from typing import Any, Iterable, Mapping

import boto3
from botocore.exceptions import ClientError


WINDOW = timedelta(minutes=5)
MAX_OBJECT_BYTES = 64 * 1024 * 1024
MAX_TASK_INPUT_BYTES = 512 * 1024 * 1024
SCHEMA = "five-layer-v2-storage-window.v1"


class StorageTransitionError(RuntimeError):
    """Payload-free terminal failure for one bounded transition window."""


@dataclass(frozen=True, slots=True)
class Window:
    start: datetime
    end: datetime

    @property
    def key(self) -> str:
        return self.start.strftime("%Y/%m/%d/%H%M")

    @property
    def source_key(self) -> str:
        return self.start.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _positive_int(name: str, default: str) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError as exc:
        raise StorageTransitionError(f"INVALID_{name}") from exc
    if value < 1:
        raise StorageTransitionError(f"INVALID_{name}")
    return value


def due_window(now: datetime, hot_boundary_days: int) -> Window:
    """Resolve the last fully closed five-minute window at the hot boundary."""

    current = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
    current -= timedelta(minutes=current.minute % 5)
    end = current - timedelta(days=hot_boundary_days)
    return Window(start=end - WINDOW, end=end)


def canonical_line(item: Mapping[str, Any]) -> tuple[str, bytes]:
    event_id = item.get("event_id", {}).get("S")
    device_id = item.get("device_id", {}).get("S")
    stored_at = item.get("stored_at", {}).get("S")
    payload_json = item.get("payload_json", {}).get("S")
    if not all(
        isinstance(value, str) and value
        for value in (event_id, device_id, stored_at, payload_json)
    ):
        raise StorageTransitionError("INVALID_HOT_DOCUMENT")
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise StorageTransitionError("INVALID_HOT_DOCUMENT") from exc
    if not isinstance(payload, Mapping):
        raise StorageTransitionError("INVALID_HOT_DOCUMENT")
    document = {
        "device_id": device_id,
        "event_id": event_id,
        "stored_at": stored_at,
        "payload": payload,
    }
    return event_id, (
        json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def partition_lines(lines: Iterable[bytes]) -> tuple[tuple[bytes, ...], ...]:
    parts: list[tuple[bytes, ...]] = []
    current: list[bytes] = []
    current_size = 0
    total = 0
    for line in lines:
        if len(line) > MAX_OBJECT_BYTES:
            raise StorageTransitionError("HOT_DOCUMENT_EXCEEDS_OBJECT_LIMIT")
        total += len(line)
        if total > MAX_TASK_INPUT_BYTES:
            raise StorageTransitionError("STORAGE_TASK_INPUT_LIMIT_EXCEEDED")
        if current and current_size + len(line) > MAX_OBJECT_BYTES:
            parts.append(tuple(current))
            current = []
            current_size = 0
        current.append(line)
        current_size += len(line)
    if current:
        parts.append(tuple(current))
    return tuple(parts)


def _write_once(
    s3: Any, bucket: str, key: str, content: bytes, metadata: dict[str, str]
) -> None:
    checksum = hashlib.sha256(content).hexdigest()
    expected = {**metadata, "sha256": checksum}
    request: dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "Body": content,
        "Metadata": expected,
        "IfNoneMatch": "*",
        "ServerSideEncryption": "AES256",
        "StorageClass": "STANDARD_IA",
        "ContentType": "application/json"
        if key.endswith(".json")
        else "application/x-ndjson",
    }
    if key.endswith(".gz"):
        request["ContentEncoding"] = "gzip"
    try:
        s3.put_object(**request)
        return
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {
            "PreconditionFailed",
            "ConditionalRequestConflict",
            "412",
            "409",
        }:
            raise
    existing = s3.head_object(Bucket=bucket, Key=key)
    if existing.get("Metadata", {}).get("sha256") != checksum:
        raise StorageTransitionError("IMMUTABLE_STORAGE_OBJECT_CONFLICT")


def _task_prefix(window: Window, task_index: int) -> str:
    return f"hot-to-cool/{window.key}/task-{task_index:03d}"


def query_window(
    dynamodb: Any, table: str, window: Window, task_index: int
) -> list[tuple[str, bytes]]:
    records: list[tuple[str, bytes]] = []
    exclusive_start_key: dict[str, Any] | None = None
    while True:
        request: dict[str, Any] = {
            "TableName": table,
            "IndexName": "storage-window-index",
            "KeyConditionExpression": "storage_window = :window",
            "ExpressionAttributeValues": {
                ":window": {"S": f"{window.source_key}#{task_index:03d}"}
            },
            "ConsistentRead": False,
        }
        if exclusive_start_key is not None:
            request["ExclusiveStartKey"] = exclusive_start_key
        response = dynamodb.query(**request)
        for item in response.get("Items", []):
            if not isinstance(item, Mapping):
                raise StorageTransitionError("INVALID_HOT_DOCUMENT")
            records.append(canonical_line(item))
        exclusive_start_key = response.get("LastEvaluatedKey")
        if not exclusive_start_key:
            break
    records.sort(key=lambda value: value[0])
    return records


def export_hot_window(
    *,
    dynamodb: Any,
    s3: Any,
    table: str,
    bucket: str,
    window: Window,
    task_index: int,
    task_count: int,
) -> dict[str, Any]:
    records = query_window(dynamodb, table, window, task_index)
    parts = partition_lines(line for _, line in records)
    prefix = _task_prefix(window, task_index)
    objects: list[dict[str, Any]] = []
    offset = 0
    for index, part in enumerate(parts):
        raw = b"".join(part)
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        event_ids = [value[0] for value in records[offset : offset + len(part)]]
        offset += len(part)
        key = f"{prefix}/part-{index:05d}.ndjson.gz"
        _write_once(
            s3,
            bucket,
            key,
            compressed,
            {
                "schema": SCHEMA,
                "count": str(len(part)),
                "first-event-id": event_ids[0],
                "last-event-id": event_ids[-1],
            },
        )
        objects.append(
            {
                "name": key,
                "count": len(part),
                "sha256": hashlib.sha256(compressed).hexdigest(),
                "uncompressed_bytes": len(raw),
            }
        )
    manifest = {
        "schema_version": SCHEMA,
        "transition": "hot-to-cool",
        "window_start": window.start.isoformat().replace("+00:00", "Z"),
        "window_end": window.end.isoformat().replace("+00:00", "Z"),
        "task_index": task_index,
        "task_count": task_count,
        "record_count": len(records),
        "objects": objects,
    }
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    _write_once(s3, bucket, f"{prefix}/manifest.json", encoded, {"schema": SCHEMA})
    return manifest


def _write_window_manifest(
    s3: Any, bucket: str, window: Window, task_count: int
) -> None:
    manifests = []
    for task_index in range(task_count):
        key = f"{_task_prefix(window, task_index)}/manifest.json"
        try:
            s3.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                return
            raise
        manifests.append(key)
    document = {
        "schema_version": SCHEMA,
        "transition": "hot-to-cool",
        "window_start": window.start.isoformat().replace("+00:00", "Z"),
        "window_end": window.end.isoformat().replace("+00:00", "Z"),
        "task_manifests": manifests,
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    _write_once(
        s3,
        bucket,
        f"hot-to-cool/{window.key}/manifest.json",
        encoded,
        {"schema": SCHEMA},
    )


def main() -> None:
    transition = os.environ.get("TRANSITION", "")
    source_provider = os.environ.get("SOURCE_PROVIDER", "")
    destination_provider = os.environ.get("DESTINATION_PROVIDER", "")
    if transition != "hot-to-cool" or {source_provider, destination_provider} != {
        "aws"
    }:
        raise StorageTransitionError("UNSUPPORTED_STORAGE_TRANSITION_ROUTE")
    table = os.environ.get("RAW_TABLE_NAME", "")
    bucket = os.environ.get("HISTORY_BUCKET", "")
    if not table or not bucket:
        raise StorageTransitionError("STORAGE_TRANSITION_NOT_CONFIGURED")
    task_count = _positive_int("STORAGE_TASK_COUNT", "1")
    task_index = int(os.environ.get("STORAGE_TASK_INDEX", "0"))
    if task_index < 0 or task_index >= task_count:
        raise StorageTransitionError("INVALID_STORAGE_TASK_INDEX")
    boundary_days = _positive_int("HOT_BOUNDARY_DAYS", "30")
    actual_at = datetime.now(timezone.utc)
    window = due_window(actual_at, boundary_days)
    export_hot_window(
        dynamodb=boto3.client("dynamodb"),
        s3=boto3.client("s3"),
        table=table,
        bucket=bucket,
        window=window,
        task_index=task_index,
        task_count=task_count,
    )
    _write_window_manifest(boto3.client("s3"), bucket, window, task_count)


if __name__ == "__main__":
    main()
