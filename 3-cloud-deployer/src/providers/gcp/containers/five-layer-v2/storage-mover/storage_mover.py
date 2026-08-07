"""Finite, idempotent GCP hot-to-cool exporter for Five-layer v2.

Each Cloud Run task owns a deterministic subset of Firestore timestamp shards
for exactly one five-minute storage window. Objects and manifests use
conditional creation; therefore a scheduler or task retry cannot overwrite
already exported telemetry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from typing import Any, Iterable, Mapping

from google.api_core.exceptions import PreconditionFailed
from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter


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


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_line(document_id: str, value: Mapping[str, Any]) -> bytes:
    document = {"document_id": document_id, **_json_value(value)}
    try:
        return (
            json.dumps(
                document,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as exc:
        raise StorageTransitionError("INVALID_HOT_DOCUMENT") from exc


def partition_lines(lines: Iterable[bytes]) -> tuple[tuple[bytes, ...], ...]:
    """Split sorted NDJSON lines into deterministic <=64 MiB objects."""

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


def assigned_shards(shard_count: int, task_count: int, task_index: int) -> tuple[int, ...]:
    if task_index < 0 or task_index >= task_count:
        raise StorageTransitionError("INVALID_CLOUD_RUN_TASK_INDEX")
    return tuple(shard for shard in range(shard_count) if shard % task_count == task_index)


def _write_once(bucket: Any, name: str, content: bytes, metadata: dict[str, str]) -> None:
    checksum = hashlib.sha256(content).hexdigest()
    expected = {**metadata, "sha256": checksum}
    blob = bucket.blob(name)
    try:
        blob.metadata = expected
        blob.upload_from_string(
            content,
            content_type="application/json" if name.endswith(".json") else "application/gzip",
            if_generation_match=0,
        )
        return
    except PreconditionFailed:
        blob.reload()
    if (blob.metadata or {}).get("sha256") != checksum:
        raise StorageTransitionError("IMMUTABLE_STORAGE_OBJECT_CONFLICT")


def _task_prefix(window: Window, task_index: int) -> str:
    return f"hot-to-cool/{window.key}/task-{task_index:03d}"


def export_hot_window(
    *,
    database: Any,
    bucket: Any,
    window: Window,
    shards: tuple[int, ...],
    task_index: int,
    task_count: int,
) -> dict[str, Any]:
    records: list[tuple[str, bytes]] = []
    for shard in shards:
        query = (
            database.collection("telemetry")
            .where(filter=FieldFilter("timestamp_shard", "==", shard))
            .where(filter=FieldFilter("stored_at", ">=", window.start))
            .where(filter=FieldFilter("stored_at", "<", window.end))
            .order_by("stored_at")
        )
        for snapshot in query.stream():
            value = snapshot.to_dict()
            if not isinstance(value, Mapping):
                raise StorageTransitionError("INVALID_HOT_DOCUMENT")
            event_id = value.get("event_id")
            if not isinstance(event_id, str) or not event_id:
                raise StorageTransitionError("INVALID_HOT_DOCUMENT")
            records.append((event_id, canonical_line(snapshot.id, value)))
    records.sort(key=lambda item: item[0])
    parts = partition_lines(line for _, line in records)
    prefix = _task_prefix(window, task_index)
    objects: list[dict[str, Any]] = []
    offset = 0
    for index, part in enumerate(parts):
        raw = b"".join(part)
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        event_ids = [item[0] for item in records[offset : offset + len(part)]]
        offset += len(part)
        name = f"{prefix}/part-{index:05d}.ndjson.gz"
        metadata = {
            "schema": SCHEMA,
            "count": str(len(part)),
            "first-event-id": event_ids[0],
            "last-event-id": event_ids[-1],
        }
        _write_once(bucket, name, compressed, metadata)
        objects.append(
            {
                "name": name,
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
        "shards": list(shards),
        "record_count": len(records),
        "objects": objects,
    }
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    _write_once(bucket, f"{prefix}/manifest.json", encoded, {"schema": SCHEMA})
    return manifest


def _write_window_manifest(bucket: Any, window: Window, task_count: int) -> None:
    manifests = []
    for task_index in range(task_count):
        name = f"{_task_prefix(window, task_index)}/manifest.json"
        blob = bucket.blob(name)
        if not blob.exists():
            return
        manifests.append(name)
    document = {
        "schema_version": SCHEMA,
        "transition": "hot-to-cool",
        "window_start": window.start.isoformat().replace("+00:00", "Z"),
        "window_end": window.end.isoformat().replace("+00:00", "Z"),
        "task_manifests": manifests,
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    _write_once(
        bucket,
        f"hot-to-cool/{window.key}/manifest.json",
        encoded,
        {"schema": SCHEMA},
    )


def main() -> None:
    transition = os.environ.get("TRANSITION", "")
    source_provider = os.environ.get("SOURCE_PROVIDER", "")
    destination_provider = os.environ.get("DESTINATION_PROVIDER", "")
    if transition != "hot-to-cool" or {source_provider, destination_provider} != {"google"}:
        raise StorageTransitionError("UNSUPPORTED_STORAGE_TRANSITION_ROUTE")
    database_name = os.environ.get("FIRESTORE_DATABASE", "")
    bucket_name = os.environ.get("HISTORY_BUCKET", "")
    if not database_name or not bucket_name:
        raise StorageTransitionError("STORAGE_TRANSITION_NOT_CONFIGURED")

    task_count = _positive_int("CLOUD_RUN_TASK_COUNT", "1")
    task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
    shard_count = _positive_int("TIMESTAMP_SHARDS", "1")
    boundary_days = _positive_int("HOT_BOUNDARY_DAYS", "30")
    actual_at = datetime.now(timezone.utc)
    window = due_window(actual_at, boundary_days)
    database = firestore.Client(database=database_name)
    bucket = storage.Client().bucket(bucket_name)
    export_hot_window(
        database=database,
        bucket=bucket,
        window=window,
        shards=assigned_shards(shard_count, task_count, task_index),
        task_index=task_index,
        task_count=task_count,
    )
    _write_window_manifest(bucket, window, task_count)


if __name__ == "__main__":
    main()
