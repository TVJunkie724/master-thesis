from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.log_tracing.checkpoints import parse_checkpoint_message


SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "aws"
    / "lambda_functions"
    / "six-layer-eventing"
    / "lambda_function.py"
)
SPEC = importlib.util.spec_from_file_location("aws_six_layer_eventing", SOURCE)
assert SPEC is not None and SPEC.loader is not None
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def _event(event_type: str) -> dict:
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": "event-1",
        "event_type": event_type,
        "deployment_id": "deployment-1",
        "source_id": "device-1",
        "source_sequence": "1",
        "occurred_at": "2026-08-11T00:00:00Z",
        "correlation_id": "correlation-1",
        "causation_id": "cause-1",
        "producer": "component.ingestion",
        "payload": {"device_id": "device-1", "message": "bounded-command"},
    }


def _kinesis(payload: dict) -> dict:
    return {
        "Records": [
            {
                "eventSource": "aws:kinesis",
                "eventID": "record-1",
                "kinesis": {
                    "data": base64.b64encode(
                        json.dumps(payload).encode("utf-8")
                    ).decode("ascii")
                },
            }
        ]
    }


def _sqs(payload: dict, *, receive_count: int = 1) -> dict:
    return {
        "Records": [
            {
                "eventSource": "aws:sqs",
                "messageId": "record-1",
                "body": json.dumps(payload),
                "attributes": {
                    "ApproximateReceiveCount": str(receive_count),
                },
            }
        ]
    }


def test_kinesis_telemetry_acknowledges_only_async_lambda_acceptance(
    monkeypatch,
):
    lambda_client = Mock()
    lambda_client.invoke.return_value = {"StatusCode": 202}
    monkeypatch.setenv("PROCESSING_FUNCTION_NAME", "processor")
    monkeypatch.setenv("CONSUMER_ROLE", "telemetry-processor")
    monkeypatch.setattr(runtime, "_client", lambda service: lambda_client)

    result = runtime.lambda_handler(_kinesis(_event("telemetry.received.v1")), None)

    assert result == {
        "schema_version": "event-delivery-result.v1",
        "accepted": 1,
        "batchItemFailures": [],
    }
    assert lambda_client.invoke.call_args.kwargs["InvocationType"] == "Event"


def test_diagnostic_checkpoint_is_payload_free_and_parseable(capsys):
    event = _event("telemetry.received.v1")
    event["payload"]["trace_id"] = "TRACE-1234ABCD"

    runtime._diagnostic_checkpoint(event)

    checkpoint = parse_checkpoint_message(capsys.readouterr().out.strip())
    assert checkpoint is not None
    assert checkpoint["trace_id"] == "TRACE-1234ABCD"
    assert checkpoint["stage"] == "event_layer_durable"
    assert "payload" not in checkpoint


def test_processed_stream_delivery_names_the_independent_consumer(monkeypatch):
    lambda_client = Mock()
    lambda_client.invoke.return_value = {"StatusCode": 202}
    monkeypatch.setenv("HOT_FUNCTION_NAME", "hot-consumer")
    monkeypatch.setenv("CONSUMER_ROLE", "historical-persistence")
    monkeypatch.setattr(runtime, "_client", lambda service: lambda_client)

    result = runtime.lambda_handler(
        _kinesis(_event("telemetry.processed.v1")),
        None,
    )

    assert result["accepted"] == 1
    delivered = json.loads(lambda_client.invoke.call_args.kwargs["Payload"])
    assert lambda_client.invoke.call_args.kwargs["FunctionName"] == "hot-consumer"
    assert delivered["eventing_delivery"]["consumer_role"] == ("historical-persistence")
    assert delivered["eventing_delivery"]["event"]["event_id"] == "event-1"


def test_control_delivery_invokes_processing_with_canonical_event(monkeypatch):
    lambda_client = Mock()
    lambda_client.invoke.return_value = {"StatusCode": 202}
    monkeypatch.setenv("PROCESSING_FUNCTION_NAME", "processor")
    monkeypatch.setenv("CONSUMER_ROLE", "control-router")
    monkeypatch.setattr(runtime, "_client", lambda service: lambda_client)

    result = runtime.lambda_handler(
        _sqs(_event("event.matched.v1")),
        None,
    )

    assert result["accepted"] == 1
    delivered = json.loads(lambda_client.invoke.call_args.kwargs["Payload"])
    assert delivered["eventing_delivery"]["consumer_role"] == "control-router"
    assert delivered["eventing_delivery"]["event"]["event_type"] == ("event.matched.v1")


def test_control_outcome_delivery_targets_hot_consumer(monkeypatch):
    lambda_client = Mock()
    lambda_client.invoke.return_value = {"StatusCode": 202}
    monkeypatch.setenv("HOT_FUNCTION_NAME", "hot-consumer")
    monkeypatch.setenv("CONSUMER_ROLE", "control-router")
    monkeypatch.setattr(runtime, "_client", lambda service: lambda_client)

    result = runtime.lambda_handler(
        _sqs(_event("device.command.outcome.v1")),
        None,
    )

    assert result["accepted"] == 1
    assert lambda_client.invoke.call_args.kwargs["FunctionName"] == "hot-consumer"


def test_control_delivery_uses_local_iot_command_target(monkeypatch):
    iot_client = Mock()
    iot_client.start_command_execution.return_value = {"executionId": "accepted"}
    sns_client = Mock()
    sns_client.publish.return_value = {"MessageId": "outcome-1"}
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.setenv("AWS_ACCOUNT_ID", "123456789012")
    monkeypatch.setenv(
        "DEVICE_COMMAND_ARN", "arn:aws:iot:eu-central-1:123456789012:command/poc"
    )
    monkeypatch.setenv("CONTROL_TOPIC_ARN", "arn:aws:sns:eu:test:control.fifo")
    monkeypatch.setenv("CONSUMER_ROLE", "control-router")
    monkeypatch.setattr(
        runtime,
        "_client",
        lambda service: sns_client if service == "sns" else iot_client,
    )

    result = runtime.lambda_handler(
        _sqs(_event("device.command.requested.v1")),
        None,
    )

    assert result["accepted"] == 1
    assert result["batchItemFailures"] == []
    assert iot_client.start_command_execution.call_args.kwargs["targetArn"].endswith(
        ":thing/device-1"
    )
    outcome = json.loads(sns_client.publish.call_args.kwargs["Message"])
    assert outcome["event_type"] == "device.command.outcome.v1"
    assert outcome["payload"]["execution_id"] == "accepted"


def test_iot_commands_client_uses_account_specific_endpoint(monkeypatch):
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


def test_exhausted_sqs_delivery_is_acknowledged_only_after_control_dlq_write(
    monkeypatch,
):
    iot_client = Mock()
    iot_client.start_command_execution.side_effect = RuntimeError("provider detail")
    sqs_client = Mock()
    sqs_client.send_message.return_value = {"MessageId": "failure-1"}
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.setenv("AWS_ACCOUNT_ID", "123456789012")
    monkeypatch.setenv(
        "DEVICE_COMMAND_ARN", "arn:aws:iot:eu-central-1:123456789012:command/poc"
    )
    monkeypatch.setenv("CONTROL_FAILURE_QUEUE_URL", "control-failure-dlq")
    monkeypatch.setenv("MAX_RECEIVE_COUNT", "6")
    monkeypatch.setenv("CONSUMER_ROLE", "control-router")
    monkeypatch.setattr(
        runtime,
        "_client",
        lambda service: sqs_client if service == "sqs" else iot_client,
    )

    result = runtime.lambda_handler(
        _sqs(_event("device.command.requested.v1"), receive_count=6),
        None,
    )

    assert result["accepted"] == 1
    assert result["batchItemFailures"] == []
    stored = json.loads(sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert stored["error_code"] == "DESTINATION_RETRYABLE_FAILURE"
    assert stored["canonical_event"]["event_id"] == "event-1"
    assert "provider detail" not in json.dumps(stored)


def test_event_type_must_match_the_source_channel(monkeypatch):
    client = Mock()
    monkeypatch.setenv("CONSUMER_ROLE", "telemetry-processor")
    monkeypatch.setattr(runtime, "_client", lambda service: client)

    result = runtime.lambda_handler(
        _kinesis(_event("device.command.requested.v1")),
        None,
    )

    assert result["accepted"] == 0
    assert result["batchItemFailures"] == [{"itemIdentifier": "record-1"}]
    client.start_command_execution.assert_not_called()


def test_canonical_event_rejects_payload_above_portable_96_kib_limit():
    event = _event("telemetry.received.v1")
    event["payload"] = {"value": "x" * runtime.MAX_EVENT_BYTES}

    assert runtime.MAX_EVENT_BYTES == 96 * 1024
    with pytest.raises(runtime.DeliveryError, match="INVALID_CANONICAL_EVENT"):
        runtime._validate_event(event)


def test_retryable_failure_returns_only_record_identifier(monkeypatch):
    lambda_client = Mock()
    lambda_client.invoke.return_value = {"StatusCode": 500}
    monkeypatch.setenv("PROCESSING_FUNCTION_NAME", "processor")
    monkeypatch.setenv("CONSUMER_ROLE", "telemetry-processor")
    monkeypatch.setattr(runtime, "_client", lambda service: lambda_client)

    result = runtime.lambda_handler(_kinesis(_event("telemetry.received.v1")), None)

    assert result["accepted"] == 0
    assert result["batchItemFailures"] == [{"itemIdentifier": "record-1"}]
    assert "device-1" not in json.dumps(result)


def test_empty_batch_fails_with_stable_code():
    with pytest.raises(RuntimeError, match="INVALID_SOURCE_RECORD"):
        runtime.lambda_handler({"Records": []}, None)
