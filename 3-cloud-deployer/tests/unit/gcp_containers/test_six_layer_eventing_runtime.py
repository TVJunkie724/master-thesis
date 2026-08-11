"""Offline contract tests for the GCP Six-layer Event Layer runtime."""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "gcp"
    / "containers"
    / "six-layer-eventing"
    / "app.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("gcp_six_layer_eventing", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(event_type: str = "telemetry.received.v1") -> dict:
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": "event-1",
        "event_type": event_type,
        "deployment_id": "deployment-1",
        "source_id": "device-1",
        "source_sequence": "1",
        "occurred_at": "2026-08-11T00:00:00Z",
        "correlation_id": "correlation-1",
        "causation_id": "event-1",
        "producer": "component.device-ingress",
        "payload": {"device_id": "device-1"},
    }


def _push(event: dict) -> dict:
    return {
        "message": {
            "messageId": "message-1",
            "data": base64.b64encode(
                json.dumps(event, separators=(",", ":")).encode()
            ).decode(),
        },
        "deliveryAttempt": 1,
    }


def test_push_decodes_canonical_event_and_rejects_role_channel_mismatch():
    runtime = _load()
    event = runtime._decode_push(_push(_event()))

    assert event["event_type"] == runtime.TELEMETRY_RECEIVED
    runtime._validate_channel(event, "telemetry-processor")
    with pytest.raises(runtime.DeliveryError, match="EVENT_CHANNEL_MISMATCH"):
        runtime._validate_channel(event, "historical-persistence")


def test_delivery_uses_short_lived_id_token_and_closed_ack(monkeypatch):
    runtime = _load()
    target = "https://processor.example.test"
    monkeypatch.setenv(
        "EVENT_TARGETS_JSON",
        json.dumps({"telemetry-processor": target}),
    )
    monkeypatch.setattr(runtime.id_token, "fetch_id_token", lambda _request, aud: f"token:{aud}")
    captured = {}

    def post(url, *, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return SimpleNamespace(
            status_code=202,
            content=b"accepted",
            json=lambda: {
                "schema_version": "event-delivery-result.v1",
                "accepted": 1,
            },
        )

    monkeypatch.setattr(runtime.requests, "post", post)
    runtime._deliver(_event(), "telemetry-processor")

    assert captured["url"] == target
    assert captured["headers"] == {"authorization": f"Bearer token:{target}"}
    assert captured["json"]["eventing_delivery"]["consumer_role"] == "telemetry-processor"


def test_large_audit_consumer_is_intentionally_side_effect_free(monkeypatch):
    runtime = _load()
    monkeypatch.delenv("EVENT_TARGETS_JSON", raising=False)

    runtime._deliver(_event("telemetry.processed.v1"), "audit")
