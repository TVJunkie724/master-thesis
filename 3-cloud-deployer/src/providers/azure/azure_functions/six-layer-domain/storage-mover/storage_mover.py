"""Finite, idempotent Azure hot-to-cool exporter for Six-layer v1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from typing import Any, Iterable, Mapping

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings, StandardBlobTier


WINDOW = timedelta(minutes=5)
MAX_OBJECT_BYTES = 64 * 1024 * 1024
MAX_TASK_INPUT_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
ARTIFACT_SCHEMA = "six-layer-storage-window.v1"
TRANSITION_SCHEMA = "storage_transition.v1"
INDEX_SCHEMA = "six-layer-storage-index.v1"
SYSTEM_FIELDS = frozenset({"_rid", "_self", "_etag", "_attachments", "_ts"})


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
        return self.start.isoformat().replace("+00:00", "Z")


def _positive_int(name: str, default: str) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError as exc:
        raise StorageTransitionError(f"INVALID_{name}") from exc
    if value < 1:
        raise StorageTransitionError(f"INVALID_{name}")
    return value


def due_window(now: datetime, hot_boundary_days: int) -> Window:
    current = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
    current -= timedelta(minutes=current.minute % 5)
    end = current - timedelta(days=hot_boundary_days)
    return Window(start=end - WINDOW, end=end)


def canonical_line(item: Mapping[str, Any]) -> tuple[str, bytes]:
    event_id = item.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise StorageTransitionError("INVALID_HOT_DOCUMENT")
    document = {
        str(key): value for key, value in item.items() if key not in SYSTEM_FIELDS
    }
    try:
        encoded = json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StorageTransitionError("INVALID_HOT_DOCUMENT") from exc
    return event_id, encoded + b"\n"


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


def query_window(
    container: Any, window: Window, task_index: int
) -> list[tuple[str, bytes]]:
    query = (
        "SELECT * FROM c WHERE c.kind IN ('raw', 'outcome') "
        "AND c.storage_window = @window AND c.storage_task = @task"
    )
    items = container.query_items(
        query=query,
        parameters=[
            {"name": "@window", "value": window.source_key},
            {"name": "@task", "value": task_index},
        ],
        enable_cross_partition_query=True,
        max_item_count=1000,
    )
    records = [canonical_line(item) for item in items]
    records.sort(key=lambda value: value[0])
    return records


def _write_once(
    container: Any, name: str, content: bytes, metadata: dict[str, str]
) -> None:
    checksum = hashlib.sha256(content).hexdigest()
    expected = {**metadata, "sha256": checksum}
    blob = container.get_blob_client(name)
    try:
        blob.upload_blob(
            content,
            overwrite=False,
            metadata=expected,
            standard_blob_tier=StandardBlobTier.COOL,
            content_settings=ContentSettings(
                content_type=(
                    "application/json"
                    if name.endswith(".json")
                    else "application/x-ndjson"
                ),
                content_encoding="gzip" if name.endswith(".gz") else None,
            ),
        )
        return
    except ResourceExistsError:
        properties = blob.get_blob_properties()
    if (properties.metadata or {}).get("sha256") != checksum:
        raise StorageTransitionError("IMMUTABLE_STORAGE_OBJECT_CONFLICT")


def _task_prefix(window: Window, task_index: int) -> str:
    return f"hot-to-cool/{window.key}/task-{task_index:03d}"


def _contract_provider(provider: str) -> str:
    return "gcp" if provider == "google" else provider


def _batch_id(
    deployment_id: str,
    transition: str,
    source_provider: str,
    destination_provider: str,
    window: Window,
    task_index: int,
) -> str:
    material = "|".join(
        (
            deployment_id,
            transition,
            _contract_provider(source_provider),
            _contract_provider(destination_provider),
            window.source_key,
            f"{task_index:03d}",
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _existing_manifest(
    blob_container: Any,
    name: str,
    *,
    deployment_id: str,
    transition: str,
    source_provider: str,
    destination_provider: str,
    window: Window,
    task_index: int,
    task_count: int,
) -> dict[str, Any] | None:
    try:
        raw = blob_container.get_blob_client(name).download_blob().readall()
    except ResourceNotFoundError:
        return None
    if not isinstance(raw, bytes) or len(raw) > MAX_MANIFEST_BYTES:
        raise StorageTransitionError("INVALID_STORAGE_TRANSITION_MANIFEST")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageTransitionError("INVALID_STORAGE_TRANSITION_MANIFEST") from exc
    expected = {
        "schema_version": TRANSITION_SCHEMA,
        "deployment_id": deployment_id,
        "transition": transition,
        "batch_id": _batch_id(
            deployment_id,
            transition,
            source_provider,
            destination_provider,
            window,
            task_index,
        ),
        "source_provider": _contract_provider(source_provider),
        "destination_provider": _contract_provider(destination_provider),
        "window_start": window.start.isoformat().replace("+00:00", "Z"),
        "window_end": window.end.isoformat().replace("+00:00", "Z"),
        "task_index": task_index,
        "task_count": task_count,
        "status": "completed",
    }
    if not isinstance(manifest, dict) or any(
        manifest.get(field) != value for field, value in expected.items()
    ):
        raise StorageTransitionError("INVALID_STORAGE_TRANSITION_MANIFEST")
    return manifest


def export_hot_window(
    *,
    cosmos_container: Any,
    blob_container: Any,
    window: Window,
    task_index: int,
    task_count: int,
    deployment_id: str = "local-poc",
    source_provider: str = "azure",
    destination_provider: str = "azure",
) -> dict[str, Any]:
    transition = "hot_to_cool"
    prefix = _task_prefix(window, task_index)
    manifest_name = f"{prefix}/manifest.json"
    existing = _existing_manifest(
        blob_container,
        manifest_name,
        deployment_id=deployment_id,
        transition=transition,
        source_provider=source_provider,
        destination_provider=destination_provider,
        window=window,
        task_index=task_index,
        task_count=task_count,
    )
    if existing is not None:
        return existing
    started_at = datetime.now(timezone.utc)
    records = query_window(cosmos_container, window, task_index)
    parts = partition_lines(line for _, line in records)
    objects: list[dict[str, Any]] = []
    offset = 0
    for index, part in enumerate(parts):
        raw = b"".join(part)
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        event_ids = [value[0] for value in records[offset : offset + len(part)]]
        offset += len(part)
        name = f"{prefix}/part-{index:05d}.ndjson.gz"
        _write_once(
            blob_container,
            name,
            compressed,
            {
                "schema": ARTIFACT_SCHEMA,
                "count": str(len(part)),
                "first_event_id": event_ids[0],
                "last_event_id": event_ids[-1],
            },
        )
        objects.append(
            {
                "name": name,
                "count": len(part),
                "sha256": hashlib.sha256(compressed).hexdigest(),
                "payload_bytes": len(compressed),
                "uncompressed_bytes": len(raw),
            }
        )
    completed_at = datetime.now(timezone.utc)
    manifest = {
        "schema_version": TRANSITION_SCHEMA,
        "deployment_id": deployment_id,
        "transition": transition,
        "batch_id": _batch_id(
            deployment_id,
            transition,
            source_provider,
            destination_provider,
            window,
            task_index,
        ),
        "source_provider": _contract_provider(source_provider),
        "destination_provider": _contract_provider(destination_provider),
        "object_count": len(objects),
        "payload_bytes": sum(item["payload_bytes"] for item in objects),
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
        "status": "completed",
        "window_start": window.start.isoformat().replace("+00:00", "Z"),
        "window_end": window.end.isoformat().replace("+00:00", "Z"),
        "task_index": task_index,
        "task_count": task_count,
        "record_count": len(records),
        "objects": objects,
    }
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    _write_once(
        blob_container,
        manifest_name,
        encoded,
        {"schema": TRANSITION_SCHEMA},
    )
    return manifest


def _write_window_manifest(
    blob_container: Any, window: Window, task_count: int
) -> None:
    manifests = []
    for task_index in range(task_count):
        name = f"{_task_prefix(window, task_index)}/manifest.json"
        try:
            blob_container.get_blob_client(name).get_blob_properties()
        except ResourceNotFoundError:
            return
        manifests.append(name)
    document = {
        "schema_version": INDEX_SCHEMA,
        "transition": "hot-to-cool",
        "window_start": window.start.isoformat().replace("+00:00", "Z"),
        "window_end": window.end.isoformat().replace("+00:00", "Z"),
        "task_manifests": manifests,
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    _write_once(
        blob_container,
        f"hot-to-cool/{window.key}/manifest.json",
        encoded,
        {"schema": INDEX_SCHEMA},
    )


def main() -> None:
    transition = os.environ.get("TRANSITION", "")
    source_provider = os.environ.get("SOURCE_PROVIDER", "")
    destination_provider = os.environ.get("DESTINATION_PROVIDER", "")
    if transition != "hot-to-cool" or {source_provider, destination_provider} != {
        "azure"
    }:
        raise StorageTransitionError("UNSUPPORTED_STORAGE_TRANSITION_ROUTE")
    cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT", "")
    database_name = os.environ.get("COSMOS_DATABASE", "")
    container_name = os.environ.get("COSMOS_CONTAINER", "")
    blob_account_url = os.environ.get("BLOB_ACCOUNT_URL", "")
    blob_container_name = os.environ.get("BLOB_CONTAINER", "")
    if not all(
        (
            cosmos_endpoint,
            database_name,
            container_name,
            blob_account_url,
            blob_container_name,
        )
    ):
        raise StorageTransitionError("STORAGE_TRANSITION_NOT_CONFIGURED")
    task_count = _positive_int("STORAGE_TASK_COUNT", "1")
    try:
        task_index = int(os.environ.get("STORAGE_TASK_INDEX", "0"))
    except ValueError as exc:
        raise StorageTransitionError("INVALID_STORAGE_TASK_INDEX") from exc
    if task_index < 0 or task_index >= task_count:
        raise StorageTransitionError("INVALID_STORAGE_TASK_INDEX")
    boundary_days = _positive_int("HOT_BOUNDARY_DAYS", "30")
    deployment_id = os.environ.get("DEPLOYMENT_ID", "")
    if not deployment_id:
        raise StorageTransitionError("STORAGE_TRANSITION_NOT_CONFIGURED")
    now = datetime.now(timezone.utc)
    window = due_window(now, boundary_days)
    credential = DefaultAzureCredential(
        managed_identity_client_id=os.environ.get("MANAGED_IDENTITY_CLIENT_ID") or None
    )
    cosmos = CosmosClient(cosmos_endpoint, credential=credential)
    cosmos_container = cosmos.get_database_client(database_name).get_container_client(
        container_name
    )
    blob_container = BlobServiceClient(
        account_url=blob_account_url,
        credential=credential,
    ).get_container_client(blob_container_name)
    export_hot_window(
        cosmos_container=cosmos_container,
        blob_container=blob_container,
        window=window,
        task_index=task_index,
        task_count=task_count,
        deployment_id=deployment_id,
        source_provider=source_provider,
        destination_provider=destination_provider,
    )
    _write_window_manifest(blob_container, window, task_count)


if __name__ == "__main__":
    main()
