"""AWS Six-layer bounded runtime contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest

SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "aws"
    / "lambda_functions"
    / "six-layer-domain"
    / "handler.py"
)
SIX_LAYER_SOURCE = SOURCE.parents[1] / "six-layer-domain" / "handler.py"


def _module():
    spec = importlib.util.spec_from_file_location("aws_six_layer_handler", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _six_layer_module():
    spec = importlib.util.spec_from_file_location(
        "aws_six_layer_domain_handler",
        SIX_LAYER_SOURCE,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_six_layer_runtime_has_its_own_profile_identity():
    assert _six_layer_module().PROFILE == "six-layer-eventing@1"


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


class _Topic:
    def __init__(self):
        self.messages = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)
        return {"MessageId": "message-1", "SequenceNumber": "1"}


class _Lambda:
    def __init__(self, *, function_error=False):
        self.calls = []
        self.function_error = function_error

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        if self.function_error:
            return {"FunctionError": "Unhandled"}
        request = json.loads(kwargs["Payload"])
        return {
            "Payload": BytesIO(
                json.dumps(
                    {
                        "schema_version": "extension-action-result.v1",
                        "invocation_id": request["invocation_id"],
                        "action_id": request["action_id"],
                        "status": "ACCEPTED",
                    }
                ).encode("utf-8")
            )
        }


class _ProcessorExtension:
    def __init__(self, *, response_overrides=None):
        self.calls = []
        self.response_overrides = response_overrides or {}

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        request = json.loads(kwargs["Payload"])
        response = {
            "schema_version": "user-function-runtime-envelope.v1",
            "invocation_id": request["invocation_id"],
            "correlation_id": request["correlation_id"],
            "slot_id": "processor.telemetry",
            "status": "success",
            "payload": {
                "value": request["payload"]["value"],
                "quality": "accepted",
            },
        }
        response.update(self.response_overrides)
        return {"Payload": BytesIO(json.dumps(response).encode("utf-8"))}


def _passthrough_processor_extension(event):
    return {"value": event["payload"]["value"], "quality": "accepted"}


class _StepFunctions:
    def __init__(self):
        self.executions = []

    def start_execution(self, **kwargs):
        self.executions.append(kwargs)
        return {"executionArn": "arn:aws:states:eu:test:execution"}


class _Commands:
    def __init__(self):
        self.executions = []

    def start_command_execution(self, **kwargs):
        self.executions.append(kwargs)
        return {"executionId": "execution-1"}


class _TwinMaker:
    def __init__(self):
        self.entries = []

    def batch_put_property_values(self, **kwargs):
        self.entries.append(kwargs)
        return {"errorEntries": []}


class _Dynamo:
    def __init__(self, *, existing_raw=None, query_response=None):
        self.get_calls = 0
        self.existing_raw = existing_raw
        self.transaction = None
        self.puts = []
        self.query_response = query_response or {"Items": []}
        self.last_query = None

    def get_item(self, **kwargs):
        self.get_calls += 1
        if "event_id" in kwargs.get("Key", {}):
            return {"Item": self.existing_raw} if self.existing_raw else {}
        return {}

    def transact_write_items(self, **kwargs):
        self.transaction = kwargs
        return {}

    def put_item(self, **kwargs):
        self.puts.append(kwargs)
        return {}

    def query(self, **kwargs):
        self.last_query = kwargs
        return self.query_response


def test_event_adapter_emits_canonical_received_event_to_local_fifo(monkeypatch):
    runtime = _module()
    queue = _Queue()
    monkeypatch.setenv("LOCAL_PROCESSING", "true")
    monkeypatch.setenv("EVENT_QUEUE_URL", "https://sqs.example.test/queue")
    monkeypatch.setattr(
        runtime, "_client", lambda service: queue if service == "sqs" else None
    )

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
    envelope = json.loads(message["MessageBody"])
    assert envelope["event_type"] == "telemetry.received.v1"
    assert envelope["producer"] == "component.device-ingress"
    assert "stored_at" not in envelope["payload"]


def test_event_adapter_uses_outbox_when_processing_is_remote(monkeypatch):
    runtime = _module()
    stream = _Stream()
    monkeypatch.setenv("LOCAL_PROCESSING", "false")
    monkeypatch.setenv("TELEMETRY_STREAM_ARN", "arn:aws:kinesis:eu:test")
    monkeypatch.setattr(
        runtime, "_client", lambda service: stream if service == "kinesis" else None
    )

    runtime.event_adapter(
        {"event_id": "event-2", "device_id": "device-2"},
        None,
    )

    assert stream.records[0]["PartitionKey"] == "device-2"
    assert stream.records[0]["StreamARN"] == "arn:aws:kinesis:eu:test"
    assert (
        json.loads(stream.records[0]["Data"])["event_type"] == "telemetry.received.v1"
    )


def test_six_layer_event_adapter_publishes_to_received_event_log(monkeypatch):
    runtime = _six_layer_module()
    stream = _Stream()
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("LOCAL_PROCESSING", "false")
    monkeypatch.setenv(
        "EVENTING_RECEIVED_STREAM_ARN",
        "arn:aws:kinesis:eu:test:stream/received",
    )
    monkeypatch.setattr(runtime, "_client", lambda service: stream)

    result = runtime.event_adapter(
        {"event_id": "event-six-1", "device_id": "device-1"},
        None,
    )

    assert result["accepted"] == 1
    assert stream.records[0]["StreamARN"].endswith("/received")
    assert json.loads(stream.records[0]["Data"])["event_type"] == (
        "telemetry.received.v1"
    )


def test_event_adapter_rejects_event_above_frozen_bridge_limit(monkeypatch):
    runtime = _module()
    monkeypatch.setenv("LOCAL_PROCESSING", "true")
    monkeypatch.setenv("EVENT_QUEUE_URL", "https://sqs.example.test/queue")
    monkeypatch.setattr(runtime, "_client", lambda _service: pytest.fail("published"))

    with pytest.raises(RuntimeError, match="EVENT_TOO_LARGE"):
        runtime.event_adapter(
            {
                "event_id": "event-large",
                "device_id": "device-1",
                "unit": "x" * (96 * 1024),
            },
            None,
        )


def test_canonical_source_id_is_bounded_and_drives_ordering_key():
    runtime = _module()
    event = runtime._ingress_event(
        {
            "event_id": "event-1",
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.5,
            "event_time": "2026-08-05T00:00:00Z",
        }
    )
    event["payload"]["device_id"] = "conflicting-payload-device"

    runtime._validate_canonical_event(event)
    assert runtime._partition_key(event) == "device-1"

    event["source_id"] = "d" * 129
    with pytest.raises(runtime.ContractError, match="INVALID_CANONICAL_EVENT"):
        runtime._validate_canonical_event(event)


def test_processor_atomically_writes_raw_and_hourly_rollup(monkeypatch):
    runtime = _module()
    dynamo = _Dynamo()
    monkeypatch.setenv("HOT_PROVIDER", "aws")
    monkeypatch.setenv("RAW_TABLE_NAME", "raw")
    monkeypatch.setenv("ROLLUP_TABLE_NAME", "rollup")
    monkeypatch.setenv("HOT_BOUNDARY_DAYS", "30")
    monkeypatch.setenv("SOURCE_EXPIRY_GRACE_HOURS", "48")
    monkeypatch.setattr(
        runtime, "_invoke_processor_extension", _passthrough_processor_extension
    )
    monkeypatch.setattr(
        runtime, "_client", lambda service: dynamo if service == "dynamodb" else None
    )

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
    assert raw["storage_window"]["S"] == "2026-08-05T00:00:00.000000Z#000"
    expected_event_id = str(
        runtime.uuid.uuid5(
            runtime.uuid.NAMESPACE_URL,
            "event-3:telemetry.processed.v1",
        )
    )
    assert raw["event_id"]["S"] == expected_event_id
    assert raw["stored_at_event_id"]["S"].endswith(f"#{expected_event_id}")


def test_six_layer_processor_publishes_to_processed_event_log(monkeypatch):
    runtime = _six_layer_module()
    stream = _Stream()
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv(
        "EVENTING_PROCESSED_STREAM_ARN",
        "arn:aws:kinesis:eu:test:stream/processed",
    )
    monkeypatch.setattr(
        runtime, "_invoke_processor_extension", _passthrough_processor_extension
    )
    monkeypatch.setattr(runtime, "_client", lambda service: stream)

    result = runtime.processor(
        {
            "event_id": "event-six-2",
            "device_id": "device-1",
            "metric": "temperature",
            "value": 22.5,
        },
        None,
    )

    assert result["accepted"] == 1
    assert stream.records[0]["StreamARN"].endswith("/processed")
    assert json.loads(stream.records[0]["Data"])["event_type"] == (
        "telemetry.processed.v1"
    )


def test_six_layer_processed_fanout_keeps_consumer_responsibilities_independent(
    monkeypatch,
):
    runtime = _six_layer_module()
    processed = runtime._derive_event(
        {
            "event_id": "received-six-fanout",
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.0,
        },
        event_type=runtime.EVENT_TELEMETRY_PROCESSED,
        producer="component.telemetry-processor",
    )
    calls = []
    monkeypatch.setenv("HOT_PROVIDER", "aws")
    monkeypatch.setenv("L2_PROVIDER", "aws")
    monkeypatch.setattr(
        runtime,
        "_write_raw_and_rollup",
        lambda event: calls.append(("historical-persistence", event["event_id"])),
    )
    monkeypatch.setattr(
        runtime,
        "_project_twin",
        lambda event: calls.append(("twin-state-update", event["event_id"])),
    )
    monkeypatch.setattr(
        runtime,
        "_evaluate_rules",
        lambda event: calls.append(("rule-evaluator", event["event_id"])),
    )

    for role in (
        "historical-persistence",
        "twin-state-update",
        "rule-evaluator",
    ):
        result = runtime.domain_consumer(
            {"eventing_delivery": {"consumer_role": role, "event": processed}},
            None,
        )
        assert result["accepted"] == 1

    assert calls == [
        (role, processed["event_id"])
        for role in (
            "historical-persistence",
            "twin-state-update",
            "rule-evaluator",
        )
    ]


@pytest.mark.parametrize(
    ("hot_provider", "l2_provider", "expected"),
    [
        ("aws", "azure", ["persist"]),
        ("gcp", "aws", ["rules"]),
        ("aws", "aws", ["persist", "rules"]),
    ],
)
def test_six_layer_remote_processed_landing_runs_only_local_responsibilities(
    monkeypatch,
    hot_provider,
    l2_provider,
    expected,
):
    runtime = _six_layer_module()
    processed = runtime._derive_event(
        {
            "event_id": "received-six-landing",
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.0,
        },
        event_type=runtime.EVENT_TELEMETRY_PROCESSED,
        producer="component.telemetry-processor",
    )
    calls = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("EVENT_LAYER_PROVIDER", "azure")
    monkeypatch.setenv("HOT_PROVIDER", hot_provider)
    monkeypatch.setenv("L2_PROVIDER", l2_provider)
    monkeypatch.setattr(
        runtime,
        "_persist_and_project",
        lambda _event: calls.append("persist"),
    )
    monkeypatch.setattr(
        runtime,
        "_evaluate_rules",
        lambda _event: calls.append("rules"),
    )

    result = runtime.domain_consumer(processed, None)

    assert result["accepted"] == 1
    assert calls == expected


def test_processor_extension_invocation_uses_closed_runtime_envelope(monkeypatch):
    runtime = _module()
    extension = _ProcessorExtension()
    monkeypatch.setenv("PROCESSOR_EXTENSION_FUNCTION_NAME", "validated-processor")
    monkeypatch.setattr(runtime, "_client", lambda service: extension)
    source = runtime._derive_event(
        {
            "event_id": "received-extension-1",
            "device_id": "device-1",
            "twin_id": "twin-1",
            "metric": "temperature",
            "value": 2.5,
            "unit": "celsius",
            "event_time": "2026-08-05T00:00:00Z",
        },
        event_type=runtime.EVENT_TELEMETRY_RECEIVED,
        producer="component.device-ingress",
    )

    result = runtime._invoke_processor_extension(source)

    assert result == {"value": 2.5, "quality": "accepted"}
    assert len(extension.calls) == 1
    assert extension.calls[0]["FunctionName"] == "validated-processor"
    assert extension.calls[0]["InvocationType"] == "RequestResponse"
    envelope = json.loads(extension.calls[0]["Payload"])
    assert set(envelope) == {
        "schema_version",
        "invocation_id",
        "correlation_id",
        "occurred_at",
        "slot_id",
        "payload",
        "context",
    }
    assert envelope["payload"] == {"unit": "celsius", "value": 2.5}
    assert envelope["context"] == {"device_id": "device-1", "twin_id": "twin-1"}


def test_processor_extension_rejects_mismatched_response_after_bounded_retries(
    monkeypatch,
):
    runtime = _module()
    extension = _ProcessorExtension(response_overrides={"correlation_id": "wrong"})
    monkeypatch.setenv("PROCESSOR_EXTENSION_FUNCTION_NAME", "validated-processor")
    monkeypatch.setattr(runtime, "_client", lambda service: extension)
    source = runtime._derive_event(
        {
            "event_id": "received-extension-invalid-1",
            "device_id": "device-1",
            "value": 2.5,
        },
        event_type=runtime.EVENT_TELEMETRY_RECEIVED,
        producer="component.device-ingress",
    )

    with pytest.raises(
        runtime.ContractError, match="INVALID_PROCESSOR_EXTENSION_RESPONSE"
    ):
        runtime._invoke_processor_extension(source)

    assert len(extension.calls) == 3


def test_processor_extension_rejects_invalid_optional_unit_before_invocation(
    monkeypatch,
):
    runtime = _module()
    extension = _ProcessorExtension()
    monkeypatch.setenv("PROCESSOR_EXTENSION_FUNCTION_NAME", "validated-processor")
    monkeypatch.setattr(runtime, "_client", lambda service: extension)
    source = runtime._derive_event(
        {
            "event_id": "received-extension-invalid-unit-1",
            "device_id": "device-1",
            "value": 2.5,
            "unit": 123,
        },
        event_type=runtime.EVENT_TELEMETRY_RECEIVED,
        producer="component.device-ingress",
    )

    with pytest.raises(runtime.ContractError, match="INVALID_PROCESSOR_UNIT"):
        runtime._invoke_processor_extension(source)

    assert extension.calls == []


def test_remote_processed_event_is_persisted_before_projection_routing(monkeypatch):
    runtime = _module()
    dynamo = _Dynamo()
    monkeypatch.setenv("HOT_PROVIDER", "aws")
    monkeypatch.setenv("TWIN_PROVIDER", "azure")
    monkeypatch.setenv("RAW_TABLE_NAME", "raw")
    monkeypatch.setenv("ROLLUP_TABLE_NAME", "rollup")
    monkeypatch.setenv("HOT_BOUNDARY_DAYS", "30")
    monkeypatch.setenv("SOURCE_EXPIRY_GRACE_HOURS", "48")
    monkeypatch.setattr(
        runtime, "_client", lambda service: dynamo if service == "dynamodb" else None
    )

    result = runtime.domain_consumer(
        {
            "schema_version": "canonical-domain-event.v1",
            "event_id": "processed-1",
            "event_type": "telemetry.processed.v1",
            "deployment_id": "deployment-1",
            "source_id": "device-1",
            "source_sequence": "1",
            "occurred_at": "2026-08-05T00:00:00Z",
            "correlation_id": "correlation-1",
            "causation_id": "received-1",
            "producer": "component.telemetry-processor",
            "payload": {
                "device_id": "device-1",
                "twin_id": "twin-1",
                "metric": "temperature",
                "value": 19.5,
                "event_time": "2026-08-05T00:00:00Z",
            },
        },
        None,
    )

    assert result == {
        "schema_version": "domain-consumer-result.v1",
        "accepted": 1,
        "batchItemFailures": [],
    }
    assert dynamo.transaction is not None


def test_processed_event_retry_is_idempotent_across_new_storage_timestamp(monkeypatch):
    runtime = _module()
    processed = {
        "schema_version": "canonical-domain-event.v1",
        "event_id": "processed-retry-1",
        "event_type": "telemetry.processed.v1",
        "deployment_id": "deployment-1",
        "source_id": "device-1",
        "source_sequence": "1",
        "occurred_at": "2026-08-05T00:00:00Z",
        "correlation_id": "correlation-1",
        "causation_id": "received-1",
        "producer": "component.telemetry-processor",
        "payload": {
            "device_id": "device-1",
            "metric": "temperature",
            "value": 19.5,
            "event_time": "2026-08-05T00:00:00Z",
        },
    }
    digest = hashlib.sha256(
        runtime._canonical_json(processed).encode("utf-8")
    ).hexdigest()
    dynamo = _Dynamo(existing_raw={"payload_digest": {"S": digest}})
    monkeypatch.setenv("RAW_TABLE_NAME", "raw")
    monkeypatch.setenv("ROLLUP_TABLE_NAME", "rollup")
    monkeypatch.setattr(
        runtime, "_client", lambda service: dynamo if service == "dynamodb" else None
    )

    runtime._write_raw_and_rollup(processed)

    assert dynamo.transaction is None
    assert dynamo.get_calls == 1


def test_projection_candidate_updates_local_twin_with_observation_time(monkeypatch):
    runtime = _module()
    dynamo = _Dynamo()
    twinmaker = _TwinMaker()
    monkeypatch.setenv("HOT_PROVIDER", "aws")
    monkeypatch.setenv("TWIN_PROVIDER", "aws")
    monkeypatch.setenv("RAW_TABLE_NAME", "raw")
    monkeypatch.setenv("ROLLUP_TABLE_NAME", "rollup")
    monkeypatch.setenv("TWINMAKER_WORKSPACE", "workspace-1")
    monkeypatch.setattr(
        runtime, "_invoke_processor_extension", _passthrough_processor_extension
    )
    monkeypatch.setattr(
        runtime,
        "_client",
        lambda service: dynamo if service == "dynamodb" else twinmaker,
    )

    runtime.processor(
        {
            "event_id": "event-projection-1",
            "device_id": "device-1",
            "twin_id": "twin-1",
            "metric": "temperature",
            "value": 20.5,
            "event_time": "2026-08-05T00:00:00Z",
            "projection_candidate": True,
        },
        None,
    )

    assert twinmaker.entries[0]["workspaceId"] == "workspace-1"
    entries = {
        entry["entityPropertyReference"]["propertyName"]: entry
        for entry in twinmaker.entries[0]["entries"]
    }
    assert set(entries) == {"metric", "value", "sourceSequence"}
    value = entries["value"]["propertyValues"][0]
    assert runtime._iso(value["timestamp"]) == "2026-08-05T00:00:00.000000Z"
    assert value["value"] == {"doubleValue": 20.5}
    assert entries["metric"]["propertyValues"][0]["value"] == {
        "stringValue": "temperature"
    }
    assert entries["sourceSequence"]["propertyValues"][0]["value"] == {
        "stringValue": "event-projection-1"
    }


def test_projection_candidate_emits_closed_remote_projection_contract(monkeypatch):
    runtime = _module()
    dynamo = _Dynamo()
    topic = _Topic()
    monkeypatch.setenv("HOT_PROVIDER", "aws")
    monkeypatch.setenv("TWIN_PROVIDER", "azure")
    monkeypatch.setenv("RAW_TABLE_NAME", "raw")
    monkeypatch.setenv("ROLLUP_TABLE_NAME", "rollup")
    monkeypatch.setenv("CONTROL_TOPIC_ARN", "arn:aws:sns:eu:test.fifo")
    monkeypatch.setattr(
        runtime, "_invoke_processor_extension", _passthrough_processor_extension
    )
    monkeypatch.setattr(
        runtime,
        "_client",
        lambda service: dynamo if service == "dynamodb" else topic,
    )

    runtime.processor(
        {
            "event_id": "event-projection-remote-1",
            "device_id": "device-1",
            "twin_id": "twin-1",
            "metric": "temperature",
            "value": 20.5,
            "event_time": "2026-08-05T00:00:00Z",
            "projection_candidate": True,
        },
        None,
    )

    projection = json.loads(topic.messages[0]["Message"])
    assert projection["event_type"] == "twin.state.upserted"
    assert set(projection["payload"]) == {
        "twin_id",
        "source_id",
        "source_sequence",
        "observed_at",
        "state_patch",
    }
    assert projection["payload"]["state_patch"] == {"temperature": 20.5}


def test_remote_outcome_uses_ordered_control_outbox(monkeypatch):
    runtime = _module()
    topic = _Topic()
    monkeypatch.setenv("HOT_PROVIDER", "azure")
    monkeypatch.setenv("CONTROL_TOPIC_ARN", "arn:aws:sns:eu:test.fifo")
    monkeypatch.setattr(runtime, "_client", lambda service: topic)
    outcome = runtime._derive_event(
        {
            "event_id": "command-outcome-source-1",
            "device_id": "device-1",
        },
        event_type=runtime.EVENT_COMMAND_OUTCOME,
        producer="component.device-command-adapter",
    )

    runtime._store_outcome(outcome)

    assert json.loads(topic.messages[0]["Message"])["event_type"] == (
        "device.command.outcome.v1"
    )
    assert topic.messages[0]["MessageGroupId"] == "device-1"


def test_matching_rule_emits_action_workflow_and_command_events(monkeypatch):
    runtime = _module()
    queue = _Queue()
    function = _Lambda()
    monkeypatch.setenv("EVENT_QUEUE_URL", "https://sqs.example.test/events.fifo")
    monkeypatch.setenv("L1_PROVIDER", "aws")
    monkeypatch.setenv("ACTION_FUNCTION_NAME", "twin-poc-action")
    monkeypatch.setattr(
        runtime,
        "_client",
        lambda service: queue if service == "sqs" else function,
    )
    processed = {
        "schema_version": "canonical-domain-event.v1",
        "event_id": "processed-match-1",
        "event_type": "telemetry.processed.v1",
        "deployment_id": "deployment-1",
        "source_id": "device-1",
        "source_sequence": "1",
        "occurred_at": "2026-08-05T00:00:00Z",
        "correlation_id": "correlation-1",
        "causation_id": "received-1",
        "producer": "component.telemetry-processor",
        "payload": {
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.5,
            "event_time": "2026-08-05T00:00:00Z",
        },
    }
    monkeypatch.setenv(
        "RULES_JSON",
        json.dumps(
            [
                {
                    "rule_id": "hot",
                    "condition": "twin.temperature > DOUBLE(20)",
                    "action": {
                        "type": "step_function",
                        "functionName": "extension",
                        "functionNameB": "notify",
                        "feedback": {
                            "iotDeviceId": "device-1",
                            "payload": "cool-down",
                        },
                    },
                }
            ]
        ),
    )

    runtime._evaluate_rules(processed)
    matched = json.loads(queue.messages.pop(0)["MessageBody"])
    runtime._dispatch_match(matched)

    assert function.calls[0]["FunctionName"] == "twin-poc-action"
    emitted = [json.loads(message["MessageBody"]) for message in queue.messages]
    assert [event["event_type"] for event in emitted] == [
        "extension.action.outcome.v1",
        "notification.requested.v1",
        "device.command.requested.v1",
    ]
    assert emitted[0]["payload"]["action_id"] == "extension"
    assert emitted[1]["payload"]["notification_action_id"] == "notify"


def test_fixed_poc_boundary_accepts_only_correlated_action_and_notification():
    runtime = _module()
    matched = runtime._derive_event(
        {
            "event_id": "processed-action-1",
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.5,
            "action": {"type": "lambda", "functionName": "extension"},
        },
        event_type=runtime.EVENT_MATCHED,
        producer="component.rule-evaluator",
    )
    action_result = runtime.poc_boundary(
        {
            "schema_version": "extension-action-invocation.v1",
            "invocation_id": matched["event_id"],
            "action_id": "extension",
            "event": matched,
        },
        None,
    )
    notification = runtime._derive_event(
        matched,
        event_type=runtime.EVENT_NOTIFICATION_REQUESTED,
        producer="component.action-dispatcher",
        body={"device_id": "device-1", "message": "temperature matched"},
    )
    notification_result = runtime.poc_boundary(
        {
            "schema_version": "notification-delivery.v1",
            "invocation_id": notification["event_id"],
            "event": notification,
        },
        None,
    )

    assert action_result["status"] == "ACCEPTED"
    assert notification_result == {
        "schema_version": "notification-delivery-result.v1",
        "event_id": notification["event_id"],
        "status": "ACCEPTED",
    }


def test_multiple_matching_rules_have_distinct_stable_event_ids(monkeypatch):
    runtime = _module()
    queue = _Queue()
    monkeypatch.setenv("EVENT_QUEUE_URL", "https://sqs.example.test/events.fifo")
    monkeypatch.setenv(
        "RULES_JSON",
        json.dumps(
            [
                {
                    "rule_id": rule_id,
                    "condition": "twin.temperature > DOUBLE(20)",
                    "action": {"type": "lambda", "functionName": "extension"},
                }
                for rule_id in ("hot-a", "hot-b")
            ]
        ),
    )
    monkeypatch.setattr(
        runtime, "_client", lambda service: queue if service == "sqs" else None
    )
    processed = runtime._derive_event(
        {
            "event_id": "received-multi-1",
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.5,
            "event_time": "2026-08-05T00:00:00Z",
        },
        event_type=runtime.EVENT_TELEMETRY_PROCESSED,
        producer="component.telemetry-processor",
    )

    runtime._evaluate_rules(processed)

    event_ids = [json.loads(item["MessageBody"])["event_id"] for item in queue.messages]
    assert len(set(event_ids)) == 2


def test_rule_runtime_rejects_nonfinite_constants_and_duplicate_rule_ids(monkeypatch):
    runtime = _module()
    with pytest.raises(runtime.ContractError, match="INVALID_RULE_CONFIGURATION"):
        runtime._condition_operand("DOUBLE(nan)", {})

    monkeypatch.setenv(
        "RULES_JSON",
        json.dumps(
            [
                {
                    "rule_id": "duplicate",
                    "condition": "temperature > DOUBLE(20)",
                    "action": {"type": "lambda", "functionName": "first"},
                },
                {
                    "rule_id": "duplicate",
                    "condition": "temperature > DOUBLE(20)",
                    "action": {"type": "lambda", "functionName": "second"},
                },
            ]
        ),
    )
    processed = runtime._derive_event(
        {
            "event_id": "received-duplicate-rule",
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.5,
        },
        event_type=runtime.EVENT_TELEMETRY_PROCESSED,
        producer="component.telemetry-processor",
    )

    with pytest.raises(runtime.ContractError, match="INVALID_RULE_CONFIGURATION"):
        runtime._evaluate_rules(processed)


def test_domain_consumer_rejects_noncanonical_broker_record():
    runtime = _module()

    result = runtime.domain_consumer(
        {
            "Records": [
                {
                    "eventSource": "aws:sqs",
                    "messageId": "message-invalid",
                    "body": json.dumps(
                        {
                            "event_id": "event-invalid",
                            "event_type": "telemetry.received.v1",
                            "device_id": "device-1",
                        }
                    ),
                }
            ]
        },
        None,
    )

    assert result["accepted"] == 0
    assert result["batchItemFailures"] == [{"itemIdentifier": "message-invalid"}]


def test_six_layer_remote_landing_republishes_to_aws_event_layer(monkeypatch):
    runtime = _six_layer_module()
    published = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("EVENT_LAYER_PROVIDER", "aws")
    monkeypatch.setattr(runtime, "_put_eventing_stream", published.append)
    monkeypatch.setattr(
        runtime,
        "processor",
        lambda *_args: pytest.fail("landing bypassed the Event Layer"),
    )
    received = runtime._derive_event(
        {"event_id": "remote-received-1", "device_id": "device-1"},
        event_type=runtime.EVENT_TELEMETRY_RECEIVED,
        producer="component.device-ingress",
    )

    result = runtime.domain_consumer(received, None)

    assert result["accepted"] == 1
    assert published == [received]


def test_notification_request_starts_fixed_workflow(monkeypatch):
    runtime = _module()
    states = _StepFunctions()
    monkeypatch.setenv("NOTIFICATION_STATE_MACHINE_ARN", "arn:aws:states:eu:test")
    monkeypatch.setattr(
        runtime,
        "_client",
        lambda service: states if service == "stepfunctions" else None,
    )
    request = runtime._derive_event(
        {"event_id": "match-1", "device_id": "device-1"},
        event_type=runtime.EVENT_NOTIFICATION_REQUESTED,
        producer="component.action-dispatcher",
        body={"device_id": "device-1", "delivery_function_name": "notify"},
    )

    runtime.domain_consumer(request, None)

    assert states.executions[0]["stateMachineArn"] == "arn:aws:states:eu:test"
    assert states.executions[0]["name"] == request["event_id"]


def test_iot_commands_client_uses_account_specific_endpoint(monkeypatch):
    runtime = _six_layer_module()
    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setenv(
        "IOT_COMMANDS_ENDPOINT",
        "account-prefix-ats.iot.eu-central-1.amazonaws.com",
    )
    monkeypatch.setattr(runtime.boto3, "client", factory)

    assert runtime._client("iot-jobs-data") is client
    factory.assert_called_once_with(
        "iot-jobs-data",
        endpoint_url=("https://account-prefix-ats.iot.eu-central-1.amazonaws.com"),
    )


def test_sns_command_request_uses_iot_commands_and_persists_outcome(monkeypatch):
    runtime = _module()
    commands = _Commands()
    dynamo = _Dynamo()
    monkeypatch.setenv("DEVICE_COMMAND_ARN", "arn:aws:iot:eu:test:command/cool-down")
    monkeypatch.setenv("AWS_ACCOUNT_ID", "123456789012")
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.setenv("HOT_PROVIDER", "aws")
    monkeypatch.setenv("RAW_TABLE_NAME", "raw")
    monkeypatch.setattr(
        runtime,
        "_client",
        lambda service: commands if service == "iot-jobs-data" else dynamo,
    )
    request = runtime._derive_event(
        {"event_id": "match-2", "device_id": "device-1"},
        event_type=runtime.EVENT_DEVICE_COMMAND_REQUESTED,
        producer="component.action-dispatcher",
        body={"device_id": "device-1", "message": "cool-down"},
    )

    result = runtime.domain_consumer(
        {
            "Records": [
                {
                    "EventSource": "aws:sns",
                    "EventSubscriptionArn": "arn:aws:sns:eu:test:subscription",
                    "Sns": {"Message": runtime._canonical_json(request)},
                }
            ]
        },
        None,
    )

    assert result["accepted"] == 1
    execution = commands.executions[0]
    assert execution["targetArn"].endswith(":thing/device-1")
    assert execution["parameters"] == {"message": {"S": "cool-down"}}
    assert dynamo.puts[0]["Item"]["event_type"]["S"] == "device.command.outcome.v1"


def test_step_function_callback_persists_typed_workflow_outcome(monkeypatch):
    runtime = _module()
    dynamo = _Dynamo()
    monkeypatch.setenv("HOT_PROVIDER", "aws")
    monkeypatch.setenv("RAW_TABLE_NAME", "raw")
    monkeypatch.setattr(
        runtime, "_client", lambda service: dynamo if service == "dynamodb" else None
    )
    request = runtime._derive_event(
        {"event_id": "match-3", "device_id": "device-1"},
        event_type=runtime.EVENT_NOTIFICATION_REQUESTED,
        producer="component.action-dispatcher",
        body={"device_id": "device-1", "delivery_function_name": "notify"},
    )

    runtime.domain_consumer(
        {"workflow_request": request, "status": "SUCCEEDED"},
        None,
    )

    assert (
        dynamo.puts[0]["Item"]["event_type"]["S"] == "notification.workflow.outcome.v1"
    )
    assert dynamo.puts[0]["Item"]["status"]["S"] == "SUCCEEDED"


def test_reader_fails_closed_until_secure_stage_provisions_key(monkeypatch):
    runtime = _module()
    monkeypatch.setenv("READER_KEY_SHA256", "")

    response = runtime.raw_history_reader({"headers": {}}, None)

    assert response["statusCode"] == 503
    assert json.loads(response["body"])["code"] == "READER_NOT_PROVISIONED"


def test_reader_exposes_only_authenticated_datasource_health(monkeypatch):
    runtime = _module()
    secret = "reader-secret"
    monkeypatch.setenv("READER_KEY_SHA256", hashlib.sha256(secret.encode()).hexdigest())

    response = runtime.raw_history_reader(
        {"headers": {"X-Twin-Reader-Key": secret}},
        None,
    )

    assert response["statusCode"] == 200
    payload = json.loads(response["body"])
    assert payload["schema_version"] == "raw-history-health.v1"
    assert payload["status"] == "ready"


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
    monkeypatch.setattr(
        runtime, "_client", lambda service: dynamo if service == "dynamodb" else None
    )

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
    assert dynamo.last_query["IndexName"] == "device-stored-at-index"
