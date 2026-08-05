"""AWS five-layer v2 bounded runtime contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "aws"
    / "lambda_functions"
    / "five-layer-v2"
    / "handler.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("aws_five_layer_v2_handler", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Queue:
    def __init__(self):
        self.messages = []

    def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return {"MessageId": "message-1"}


class _Stream:
    def __init__(self):
        self.records = []

    def put_record(self, **kwargs):
        self.records.append(kwargs)
        return {"SequenceNumber": "1", "ShardId": "shard-1"}


class _Dynamo:
    def __init__(self, *, query_response=None):
        self.get_calls = 0
        self.transaction = None
        self.query_response = query_response or {"Items": []}

    def get_item(self, **_kwargs):
        self.get_calls += 1
        return {}

    def transact_write_items(self, **kwargs):
        self.transaction = kwargs
        return {}

    def query(self, **_kwargs):
        return self.query_response


def test_event_adapter_stamps_once_and_enqueues_fifo(monkeypatch):
    runtime = _module()
    queue = _Queue()
    monkeypatch.setenv("LOCAL_PROCESSING", "true")
    monkeypatch.setenv("EVENT_QUEUE_URL", "https://sqs.example.test/queue")
    monkeypatch.setattr(runtime, "_client", lambda service: queue if service == "sqs" else None)

    result = runtime.event_adapter(
        {
            "event_id": "event-1",
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.5,
            "event_time": "2026-08-05T00:00:00Z",
        },
        None,
    )

    assert result["accepted"] == 1
    message = queue.messages[0]
    assert message["MessageGroupId"] == "device-1"
    assert message["MessageDeduplicationId"] == "event-1"
    assert json.loads(message["MessageBody"])["stored_at"].endswith("Z")


def test_event_adapter_uses_outbox_when_processing_is_remote(monkeypatch):
    runtime = _module()
    stream = _Stream()
    monkeypatch.setenv("LOCAL_PROCESSING", "false")
    monkeypatch.setenv("TELEMETRY_STREAM_ARN", "arn:aws:kinesis:eu:test")
    monkeypatch.setattr(runtime, "_client", lambda service: stream if service == "kinesis" else None)

    runtime.event_adapter(
        {"event_id": "event-2", "device_id": "device-2"},
        None,
    )

    assert stream.records[0]["PartitionKey"] == "device-2"
    assert stream.records[0]["StreamARN"] == "arn:aws:kinesis:eu:test"


def test_processor_atomically_writes_raw_and_hourly_rollup(monkeypatch):
    runtime = _module()
    dynamo = _Dynamo()
    monkeypatch.setenv("HOT_PROVIDER", "aws")
    monkeypatch.setenv("RAW_TABLE_NAME", "raw")
    monkeypatch.setenv("ROLLUP_TABLE_NAME", "rollup")
    monkeypatch.setenv("HOT_BOUNDARY_DAYS", "30")
    monkeypatch.setenv("SOURCE_EXPIRY_GRACE_HOURS", "48")
    monkeypatch.setattr(runtime, "_client", lambda service: dynamo if service == "dynamodb" else None)

    result = runtime.processor(
        {
            "event_id": "event-3",
            "device_id": "device-3",
            "metric": "temperature",
            "value": 22.25,
            "event_time": "2026-08-05T00:00:00Z",
            "stored_at": "2026-08-05T00:01:00Z",
        },
        None,
    )

    assert result["accepted"] == 1
    assert result["batchItemFailures"] == []
    items = dynamo.transaction["TransactItems"]
    assert [item["Put"]["TableName"] for item in items] == ["raw", "rollup"]
    raw = items[0]["Put"]["Item"]
    assert raw["storage_window"]["S"] == "2026-08-05T00:00:00.000000Z"
    assert raw["stored_at_event_id"]["S"].endswith("#event-3")


def test_reader_fails_closed_until_secure_stage_provisions_key(monkeypatch):
    runtime = _module()
    monkeypatch.setenv("READER_KEY_SHA256", "")

    response = runtime.raw_history_reader({"headers": {}}, None)

    assert response["statusCode"] == 503
    assert json.loads(response["body"])["code"] == "READER_NOT_PROVISIONED"


def test_reader_returns_only_closed_raw_history_shape(monkeypatch):
    runtime = _module()
    secret = "reader-secret"
    dynamo = _Dynamo(
        query_response={
            "Items": [
                {
                    "stored_at": {"S": "2026-08-05T00:01:00.000000Z"},
                    "event_time": {"S": "2026-08-05T00:00:00.000000Z"},
                    "value": {"N": "21.5"},
                }
            ]
        }
    )
    monkeypatch.setenv("READER_KEY_SHA256", hashlib.sha256(secret.encode()).hexdigest())
    monkeypatch.setenv("RAW_TABLE_NAME", "raw")
    monkeypatch.setenv("ROLLUP_TABLE_NAME", "rollup")
    monkeypatch.setattr(runtime, "_client", lambda service: dynamo if service == "dynamodb" else None)

    response = runtime.raw_history_reader(
        {
            "headers": {"X-Twin-Reader-Key": secret},
            "queryStringParameters": {
                "device_id": "device-1",
                "metric": "temperature",
                "from": "2026-08-05T00:00:00Z",
                "to": "2026-08-05T01:00:00Z",
                "bucket_seconds": "0",
                "limit": "1000",
            },
        },
        None,
    )

    assert response["statusCode"] == 200
    payload = json.loads(response["body"])
    assert set(payload) == {
        "correlation_id",
        "device_id",
        "metric",
        "next_cursor",
        "points",
        "schema_version",
        "truncated",
    }
    assert payload["points"][0]["value"] == 21.5
