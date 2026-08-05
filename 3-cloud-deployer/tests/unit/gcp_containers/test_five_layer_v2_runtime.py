"""GCP Five-layer v2 Cloud Run runtime contract tests."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


SOURCE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "gcp"
    / "containers"
    / "five-layer-v2"
    / "platform"
)


def _load(name: str):
    sys.path.insert(0, str(SOURCE_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(name, SOURCE_ROOT / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SOURCE_ROOT))


def _received(core, *, event_id: str = "event-1", projection: bool = True):
    return core.build_ingress_event(
        {
            "event_id": event_id,
            "device_id": "device-1",
            "twin_id": "twin-1",
            "metric": "temperature",
            "value": 21.5,
            "unit": "celsius",
            "event_time": "2026-08-05T00:00:00Z",
            "projection_candidate": projection,
        },
        deployment_id="deployment-1",
    )


def _extension_response(received):
    return {
        "schema_version": "user-function-runtime-envelope.v1",
        "invocation_id": received["event_id"],
        "correlation_id": received["correlation_id"],
        "slot_id": "processor.telemetry",
        "status": "success",
        "payload": {"value": 21.75, "quality": "accepted"},
    }


def test_ingress_event_is_deterministic_and_provider_neutral():
    core = _load("core")
    first = _received(core)
    second = _received(core)

    assert first == second
    assert first["event_type"] == "telemetry.received.v1"
    assert first["producer"] == "component.device-ingress"
    assert set(first) == core.CANONICAL_EVENT_FIELDS
    assert not any(key.startswith("gcp_") for key in first)


def test_processor_extension_response_is_closed_and_correlated():
    core = _load("core")
    received = _received(core)
    processed = core.build_processed_event(received, _extension_response(received))

    assert processed["event_type"] == "telemetry.processed.v1"
    assert processed["payload"]["value"] == 21.75
    assert processed["payload"]["quality"] == "accepted"

    invalid = _extension_response(received)
    invalid["correlation_id"] = "wrong"
    with pytest.raises(
        core.ContractError, match="INVALID_PROCESSOR_EXTENSION_RESPONSE"
    ):
        core.build_processed_event(received, invalid)


def test_firestore_raw_and_rollup_use_reviewed_time_shards_and_expiry():
    core = _load("core")
    received = _received(core)
    processed = core.build_processed_event(received, _extension_response(received))
    stored_at = datetime(2026, 8, 5, 0, 7, tzinfo=timezone.utc)

    raw = core.raw_document(
        processed,
        stored_at=stored_at,
        hot_boundary_days=30,
        shard_count=16,
    )
    rollup = core.rollup_document(raw, None)

    assert 0 <= raw["timestamp_shard"] < 16
    identity_digest = hashlib.sha256(
        f"deployment-1\0{processed['event_id']}".encode("utf-8")
    ).digest()
    assert raw["timestamp_shard"] == int.from_bytes(identity_digest[:4], "big") % 16
    assert core.raw_document_id(processed) == identity_digest.hex()
    assert raw["storage_window"] == "2026-08-05T00:05:00.000000Z"
    assert raw["expires_at"] == datetime(2026, 9, 6, 0, 7, tzinfo=timezone.utc)
    assert rollup["count"] == 1
    assert rollup["sum"] == 21.75
    assert rollup["timestamp_shard"] == raw["timestamp_shard"]


def test_twin_projection_is_sparse_and_explicit():
    core = _load("core")
    projected_source = core.build_processed_event(
        _received(core, projection=True),
        _extension_response(_received(core, projection=True)),
    )
    skipped_received = _received(core, event_id="event-2", projection=False)
    skipped_source = core.build_processed_event(
        skipped_received,
        _extension_response(skipped_received),
    )

    projection = core.build_twin_projection(projected_source)
    assert projection is not None
    assert projection["event_type"] == "twin.state.upserted"
    assert projection["payload"]["state_patch"] == {"temperature": 21.75}
    assert core.build_twin_projection(skipped_source) is None


def test_rule_matches_are_typed_and_idempotent():
    core = _load("core")
    received = _received(core)
    processed = core.build_processed_event(received, _extension_response(received))
    rules = [
        {
            "rule_id": "hot",
            "condition": "temperature > DOUBLE(20)",
            "action": {"type": "workflow", "functionName": "notify"},
        }
    ]

    first = core.build_rule_matches(processed, rules)
    second = core.build_rule_matches(processed, rules)

    assert first == second
    assert first[0]["event_type"] == "event.matched.v1"
    assert first[0]["payload"]["rule_id"] == "hot"


def test_cloud_run_ingress_publishes_one_ordered_canonical_event(monkeypatch):
    core = _load("core")
    runtime = _load("app")
    published = []
    monkeypatch.setenv("RUNTIME_ROLE", "event-adapter")
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("RECEIVED_TOPIC", "projects/test/topics/received")
    monkeypatch.setattr(runtime, "_publish", lambda topic, event: published.append((topic, event)))

    response = runtime.app.test_client().post(
        "/",
        json={
            "event_id": "event-http-1",
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.5,
            "event_time": "2026-08-05T00:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["accepted"] == 1
    assert published[0][0] == "projects/test/topics/received"
    assert published[0][1]["event_type"] == core.EVENT_TELEMETRY_RECEIVED


def test_cloud_run_ingress_rejects_cross_deployment_canonical_event(monkeypatch):
    core = _load("core")
    runtime = _load("app")
    monkeypatch.setenv("RUNTIME_ROLE", "event-adapter")
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-2")
    monkeypatch.setenv("RECEIVED_TOPIC", "projects/test/topics/received")
    event = _received(core)

    response = runtime.app.test_client().post("/", json=event)

    assert response.status_code == 400
    assert response.get_json() == {"error": {"code": "UNEXPECTED_INGRESS_EVENT"}}


def test_pubsub_decoder_rejects_noncanonical_payload():
    runtime = _load("app")
    push = {
        "message": {
            "data": base64.b64encode(json.dumps({"device_id": "device-1"}).encode()).decode()
        }
    }

    with pytest.raises(runtime.core.ContractError, match="INVALID_CANONICAL_EVENT"):
        runtime._decode_pubsub_push(push)
