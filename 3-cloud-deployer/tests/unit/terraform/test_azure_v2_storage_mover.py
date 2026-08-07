"""Pure contract tests for the finite Azure Five-layer v2 storage mover."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

from azure.core.exceptions import ResourceExistsError


SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src/providers/azure/azure_functions/five-layer-v2/storage-mover/storage_mover.py"
)
SPEC = importlib.util.spec_from_file_location("azure_v2_storage_mover", SOURCE)
assert SPEC is not None and SPEC.loader is not None
mover = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mover
SPEC.loader.exec_module(mover)


class _Cosmos:
    def __init__(self, items):
        self.items = items
        self.requests = []

    def query_items(self, **kwargs):
        self.requests.append(kwargs)
        return list(self.items)


class _Blob:
    def __init__(self):
        self.content = None
        self.metadata = None

    def upload_blob(self, content, **kwargs):
        if self.content is not None:
            raise ResourceExistsError("exists")
        self.content = content
        self.metadata = kwargs["metadata"]

    def get_blob_properties(self):
        return SimpleNamespace(metadata=self.metadata)


class _BlobContainer:
    def __init__(self):
        self.objects = {}

    def get_blob_client(self, name):
        return self.objects.setdefault(name, _Blob())


def test_due_window_and_task_query_are_exact():
    window = mover.due_window(
        datetime(2026, 8, 5, 12, 7, 51, tzinfo=timezone.utc),
        30,
    )
    cosmos = _Cosmos(
        [
            {
                "event_id": "event-1",
                "device_id": "device-1",
                "_etag": "provider-metadata",
            }
        ]
    )

    records = mover.query_window(cosmos, window, 3)

    assert window.key == "2026/07/06/1200"
    assert cosmos.requests[0]["parameters"] == [
        {"name": "@window", "value": "2026-07-06T12:00:00Z"},
        {"name": "@task", "value": 3},
    ]
    assert b"provider-metadata" not in records[0][1]


def test_partition_lines_respects_object_and_task_limits(monkeypatch):
    monkeypatch.setattr(mover, "MAX_OBJECT_BYTES", 6)
    monkeypatch.setattr(mover, "MAX_TASK_INPUT_BYTES", 12)

    assert mover.partition_lines((b"aaa", b"bbb", b"ccc")) == (
        (b"aaa", b"bbb"),
        (b"ccc",),
    )


def test_retry_produces_the_same_immutable_manifest():
    window = mover.due_window(
        datetime(2026, 8, 5, 12, 7, 51, tzinfo=timezone.utc),
        30,
    )
    item = {
        "event_id": "event-1",
        "device_id": "device-1",
        "kind": "raw",
        "payload": {"value": 1},
    }
    blobs = _BlobContainer()

    first = mover.export_hot_window(
        cosmos_container=_Cosmos([item]),
        blob_container=blobs,
        window=window,
        task_index=0,
        task_count=1,
    )
    retried = mover.export_hot_window(
        cosmos_container=_Cosmos([item]),
        blob_container=blobs,
        window=window,
        task_index=0,
        task_count=1,
    )

    assert retried == first
    assert "actual_at" not in first
    assert blobs.objects[
        "hot-to-cool/2026/07/06/1200/task-000/part-00000.ndjson.gz"
    ].metadata["first_event_id"] == "event-1"
