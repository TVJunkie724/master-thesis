import json

from src.log_tracing.checkpoints import CHECKPOINT_PREFIX, parse_checkpoint_message


def _checkpoint():
    return {
        "schema_version": "diagnostic-checkpoint.v1",
        "trace_id": "TRACE-1234ABCD",
        "stage": "event_layer_durable",
        "provider": "aws",
        "component": "eventing",
        "status": "passed",
        "observed_at": "2026-08-28T12:00:00Z",
        "event_id": "event-1",
        "event_type": "telemetry.received.v1",
    }


def test_checkpoint_parser_accepts_plain_and_provider_wrapped_messages():
    message = CHECKPOINT_PREFIX + json.dumps(_checkpoint())

    assert parse_checkpoint_message(message) == _checkpoint()
    assert parse_checkpoint_message(json.dumps({"message": message})) == _checkpoint()


def test_checkpoint_parser_accepts_simulator_receipt_stage():
    checkpoint = _checkpoint()
    checkpoint.update(
        stage="simulator_command_received",
        component="simulator",
        event_type="device.command.requested.v1",
    )

    assert parse_checkpoint_message(
        CHECKPOINT_PREFIX + json.dumps(checkpoint)
    ) == checkpoint


def test_checkpoint_parser_rejects_unknown_fields_and_unbounded_trace_ids():
    checkpoint = _checkpoint()
    checkpoint["payload"] = {"secret": "must-not-be-accepted"}
    assert parse_checkpoint_message(CHECKPOINT_PREFIX + json.dumps(checkpoint)) is None

    checkpoint = _checkpoint()
    checkpoint["trace_id"] = "not-a-verification-trace"
    assert parse_checkpoint_message(CHECKPOINT_PREFIX + json.dumps(checkpoint)) is None
