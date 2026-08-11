from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "azure"
    / "azure_functions"
    / "six-layer-eventing"
    / "function_app.py"
)
SPEC = importlib.util.spec_from_file_location("azure_six_layer_eventing", SOURCE)
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
        "payload": {"device_id": "device-1"},
    }


class _Message:
    def __init__(self, payload: dict):
        self.payload = payload

    def get_body(self):
        return json.dumps(self.payload).encode("utf-8")


def _context(retry_count: int = 0):
    return SimpleNamespace(retry_context=SimpleNamespace(retry_count=retry_count))


def test_received_batch_uses_canonical_same_cloud_delivery(monkeypatch):
    deliver = Mock()
    monkeypatch.setattr(runtime, "_post_delivery", deliver)

    runtime._telemetry_batch(
        [_Message(_event("telemetry.received.v1"))],
        role="telemetry-processor",
        expected_type="telemetry.received.v1",
        context=_context(),
    )

    deliver.assert_called_once_with(_event("telemetry.received.v1"), None)


def test_processed_batch_names_independent_consumer(monkeypatch):
    deliver = Mock()
    event = _event("telemetry.processed.v1")
    monkeypatch.setattr(runtime, "_post_delivery", deliver)

    runtime._telemetry_batch(
        [_Message(event)],
        role="historical-persistence",
        expected_type="telemetry.processed.v1",
        context=_context(),
    )

    deliver.assert_called_once_with(event, "historical-persistence")


def test_large_observation_consumers_are_bounded_noops(monkeypatch):
    deliver = Mock()
    monkeypatch.setattr(runtime, "_post_delivery", deliver)

    runtime._telemetry_batch(
        [_Message(_event("telemetry.processed.v1"))],
        role="audit",
        expected_type="telemetry.processed.v1",
        context=_context(),
    )

    deliver.assert_not_called()


def test_retryable_batch_failure_uses_stable_error_without_payload(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "_post_delivery",
        Mock(side_effect=RuntimeError("provider detail device-1")),
    )

    with pytest.raises(RuntimeError, match="EVENT_DELIVERY_RETRYABLE_FAILURE") as exc:
        runtime._telemetry_batch(
            [_Message(_event("telemetry.received.v1"))],
            role="telemetry-processor",
            expected_type="telemetry.received.v1",
            context=_context(4),
        )

    assert "device-1" not in str(exc.value)


def test_exhausted_event_hub_retry_writes_explicit_failure_log(monkeypatch):
    failures = Mock()
    monkeypatch.setattr(
        runtime,
        "_post_delivery",
        Mock(side_effect=runtime.DeliveryError("DESTINATION_NOT_ACCEPTED")),
    )
    monkeypatch.setattr(runtime, "_publish_terminal_failures", failures)

    runtime._telemetry_batch(
        [_Message(_event("telemetry.received.v1"))],
        role="telemetry-processor",
        expected_type="telemetry.received.v1",
        context=_context(5),
    )

    stored = failures.call_args.args[0]
    assert stored[0][0]["event_id"] == "event-1"
    assert stored[0][1] == "DESTINATION_NOT_ACCEPTED"


def test_invalid_consumer_configuration_is_fail_closed(monkeypatch):
    monkeypatch.setenv(
        "EVENT_LOCAL_PROCESSED_ROLES_JSON",
        '["historical-persistence", "unknown"]',
    )

    with pytest.raises(runtime.DeliveryError, match="EVENT_RUNTIME_NOT_CONFIGURED"):
        runtime._configured_processed_roles()


def test_canonical_envelope_rejects_provider_route_metadata():
    event = _event("telemetry.received.v1")
    event["destination_provider"] = "azure"

    with pytest.raises(runtime.DeliveryError, match="INVALID_CANONICAL_EVENT"):
        runtime._validate(event)
