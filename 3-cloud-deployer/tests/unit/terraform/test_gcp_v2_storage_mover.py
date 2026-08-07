"""Pure contract tests for the finite GCP Five-layer v2 storage mover."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys

import pytest


SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src/providers/gcp/containers/five-layer-v2/storage-mover/storage_mover.py"
)
SPEC = importlib.util.spec_from_file_location("gcp_v2_storage_mover", SOURCE)
assert SPEC is not None and SPEC.loader is not None
mover = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mover
SPEC.loader.exec_module(mover)


class _Snapshot:
    id = "document-1"

    @staticmethod
    def to_dict():
        return {"event_id": "event-1", "value": 1}


class _Query:
    def where(self, **_kwargs):
        return self

    def order_by(self, _field):
        return self

    @staticmethod
    def stream():
        return [_Snapshot()]


class _Database:
    @staticmethod
    def collection(_name):
        return _Query()


class _Blob:
    def __init__(self, name):
        self.name = name
        self.metadata = None
        self.content = None

    def upload_from_string(self, content, **_kwargs):
        if self.content is not None:
            raise mover.PreconditionFailed("already exists")
        self.content = content

    def reload(self):
        return None


class _Bucket:
    def __init__(self):
        self.objects = {}

    def blob(self, name):
        return self.objects.setdefault(name, _Blob(name))


def test_due_window_is_the_last_closed_boundary_window():
    window = mover.due_window(
        datetime(2026, 8, 5, 12, 7, 51, tzinfo=timezone.utc),
        30,
    )

    assert window.start == datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    assert window.end == datetime(2026, 7, 6, 12, 5, tzinfo=timezone.utc)
    assert window.key == "2026/07/06/1200"


def test_large_task_shards_are_disjoint_and_complete():
    assignments = [set(mover.assigned_shards(16, 3, index)) for index in range(3)]

    assert set.union(*assignments) == set(range(16))
    assert all(left.isdisjoint(right) for left, right in ((assignments[0], assignments[1]), (assignments[0], assignments[2]), (assignments[1], assignments[2])))


def test_partition_lines_respects_object_and_task_limits(monkeypatch):
    monkeypatch.setattr(mover, "MAX_OBJECT_BYTES", 6)
    monkeypatch.setattr(mover, "MAX_TASK_INPUT_BYTES", 12)

    assert mover.partition_lines((b"aaa", b"bbb", b"ccc")) == (
        (b"aaa", b"bbb"),
        (b"ccc",),
    )
    with pytest.raises(mover.StorageTransitionError, match="TASK_INPUT"):
        mover.partition_lines((b"aaaaaa", b"bbbbbb", b"c"))


def test_retry_produces_the_same_immutable_manifest():
    window = mover.due_window(
        datetime(2026, 8, 5, 12, 7, 51, tzinfo=timezone.utc),
        30,
    )
    bucket = _Bucket()

    first = mover.export_hot_window(
        database=_Database(),
        bucket=bucket,
        window=window,
        shards=(0,),
        task_index=0,
        task_count=1,
    )
    retried = mover.export_hot_window(
        database=_Database(),
        bucket=bucket,
        window=window,
        shards=(0,),
        task_index=0,
        task_count=1,
    )

    assert retried == first
    assert "actual_at" not in first
