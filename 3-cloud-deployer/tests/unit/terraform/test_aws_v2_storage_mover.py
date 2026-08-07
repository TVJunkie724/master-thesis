"""Pure contract tests for the finite AWS Five-layer v2 storage mover."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

from botocore.exceptions import ClientError


SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src/providers/aws/lambda_functions/five-layer-v2/storage-mover/storage_mover.py"
)
SPEC = importlib.util.spec_from_file_location("aws_v2_storage_mover", SOURCE)
assert SPEC is not None and SPEC.loader is not None
mover = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mover
SPEC.loader.exec_module(mover)


class _Dynamo:
    def __init__(self, items):
        self.items = items
        self.requests = []

    def query(self, **kwargs):
        self.requests.append(kwargs)
        return {"Items": self.items}


class _S3:
    def __init__(self):
        self.objects = {}

    def put_object(self, **kwargs):
        key = (kwargs["Bucket"], kwargs["Key"])
        if key in self.objects:
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"}},
                "PutObject",
            )
        self.objects[key] = kwargs

    def head_object(self, *, Bucket, Key):
        return {"Metadata": self.objects[(Bucket, Key)]["Metadata"]}


def test_due_window_and_sharded_query_are_exact():
    window = mover.due_window(
        datetime(2026, 8, 5, 12, 7, 51, tzinfo=timezone.utc),
        30,
    )
    dynamo = _Dynamo(
        [
            {
                "device_id": {"S": "device-1"},
                "event_id": {"S": "event-1"},
                "stored_at": {"S": "2026-07-06T12:00:00.000000Z"},
                "payload_json": {"S": json.dumps({"value": 1})},
            }
        ]
    )

    records = mover.query_window(dynamo, "raw", window, 2)

    assert window.key == "2026/07/06/1200"
    assert dynamo.requests[0]["ExpressionAttributeValues"][":window"]["S"] == (
        "2026-07-06T12:00:00.000000Z#002"
    )
    assert records[0][0] == "event-1"


def test_partition_lines_respects_object_and_task_limits(monkeypatch):
    monkeypatch.setattr(mover, "MAX_OBJECT_BYTES", 6)
    monkeypatch.setattr(mover, "MAX_TASK_INPUT_BYTES", 12)

    assert mover.partition_lines((b"aaa", b"bbb", b"ccc")) == (
        (b"aaa", b"bbb"),
        (b"ccc",),
    )


def test_retry_produces_the_same_immutable_manifest():
    item = {
        "device_id": {"S": "device-1"},
        "event_id": {"S": "event-1"},
        "stored_at": {"S": "2026-07-06T12:00:00.000000Z"},
        "payload_json": {"S": json.dumps({"value": 1})},
    }
    window = mover.due_window(
        datetime(2026, 8, 5, 12, 7, 51, tzinfo=timezone.utc),
        30,
    )
    s3 = _S3()

    first = mover.export_hot_window(
        dynamodb=_Dynamo([item]),
        s3=s3,
        table="raw",
        bucket="history",
        window=window,
        task_index=0,
        task_count=1,
    )
    retried = mover.export_hot_window(
        dynamodb=_Dynamo([item]),
        s3=s3,
        table="raw",
        bucket="history",
        window=window,
        task_index=0,
        task_count=1,
    )

    assert retried == first
    assert "actual_at" not in first
