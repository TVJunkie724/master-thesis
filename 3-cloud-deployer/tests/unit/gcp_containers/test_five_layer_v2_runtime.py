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
SIX_LAYER_SOURCE_ROOT = SOURCE_ROOT.parents[1] / "six-layer-domain" / "platform"


def _load_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load(name: str):
    sys.path.insert(0, str(SOURCE_ROOT))
    try:
        if name == "core":
            return _load_from_path(
                "gcp_five_layer_v2_core",
                SOURCE_ROOT / "core.py",
            )

        core = _load_from_path(
            "gcp_five_layer_v2_app_core",
            SOURCE_ROOT / "core.py",
        )
        previous_core = sys.modules.get("core")
        sys.modules["core"] = core
        try:
            return _load_from_path(
                "gcp_five_layer_v2_app",
                SOURCE_ROOT / "app.py",
            )
        finally:
            if previous_core is None:
                sys.modules.pop("core", None)
            else:
                sys.modules["core"] = previous_core
    finally:
        sys.path.remove(str(SOURCE_ROOT))


def _load_six_layer(name: str):
    sys.path.insert(0, str(SIX_LAYER_SOURCE_ROOT))
    try:
        core = _load_from_path(
            "gcp_six_layer_domain_core",
            SIX_LAYER_SOURCE_ROOT / "core.py",
        )
        if name == "core":
            return core
        previous_core = sys.modules.get("core")
        sys.modules["core"] = core
        try:
            return _load_from_path(
                "gcp_six_layer_domain_app",
                SIX_LAYER_SOURCE_ROOT / "app.py",
            )
        finally:
            if previous_core is None:
                sys.modules.pop("core", None)
            else:
                sys.modules["core"] = previous_core
    finally:
        sys.path.remove(str(SIX_LAYER_SOURCE_ROOT))


def test_six_layer_runtime_has_its_own_profile_identity():
    assert _load_six_layer("core").PROFILE == "six-layer-eventing@1"


def test_six_layer_health_reports_its_own_profile(monkeypatch):
    runtime = _load_six_layer("app")
    monkeypatch.setenv("RUNTIME_ROLE", "audit")

    response = runtime.app.test_client().get("/healthz")

    assert response.status_code == 200
    assert response.get_json()["profile"] == "six-layer-eventing@1"


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


def _matched(core):
    received = _received(core)
    processed = core.build_processed_event(received, _extension_response(received))
    return core.build_rule_matches(
        processed,
        [
            {
                "rule_id": "hot",
                "condition": "temperature > DOUBLE(20)",
                "action": {
                    "type": "workflow",
                    "functionName": "fixed-action",
                    "functionNameB": "fixed-notification",
                    "feedback": {"payload": "cool-down"},
                },
            }
        ],
    )[0]


def test_ingress_event_is_deterministic_and_provider_neutral():
    core = _load("core")
    first = _received(core)
    second = _received(core)

    assert first == second
    assert first["event_type"] == "telemetry.received.v1"
    assert first["producer"] == "component.device-ingress"
    assert set(first) == core.CANONICAL_EVENT_FIELDS
    assert not any(key.startswith("gcp_") for key in first)


def test_source_id_is_bounded_and_wins_over_payload_device_for_ordering():
    core = _load("core")
    event = _received(core)
    event["payload"]["device_id"] = "conflicting-payload-device"

    assert core.partition_key(event) == "device-1"

    event["source_id"] = "d" * 129
    with pytest.raises(core.ContractError, match="INVALID_CANONICAL_EVENT"):
        core.validate_canonical_event(event)


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


def test_match_dispatch_derives_each_terminal_flow_deterministically():
    core = _load("core")
    matched = _matched(core)

    first = core.build_match_dispatch_events(matched, action_accepted=True)
    second = core.build_match_dispatch_events(matched, action_accepted=True)

    assert first == second
    assert [event["event_type"] for event in first] == [
        core.EVENT_ACTION_OUTCOME,
        core.EVENT_NOTIFICATION_REQUESTED,
        core.EVENT_DEVICE_COMMAND_REQUESTED,
    ]
    assert first[0]["payload"]["status"] == "SUCCEEDED"


def test_twin_projection_order_rejects_duplicate_and_stale_state():
    core = _load("core")
    received = _received(core)
    processed = core.build_processed_event(received, _extension_response(received))
    projection = core.build_twin_projection(processed)
    assert projection is not None

    current = {
        "last_observed_at": projection["payload"]["observed_at"],
        "last_source_sequence": projection["payload"]["source_sequence"],
        "last_event_id": projection["event_id"],
    }
    assert core.projection_is_newer(None, projection) is True
    assert core.projection_is_newer(current, projection) is False

    stale = dict(projection)
    stale["event_id"] = "stale-event"
    stale["payload"] = {
        **projection["payload"],
        "observed_at": "2026-08-04T23:59:59Z",
    }
    assert core.projection_is_newer(current, stale) is False

    numeric_current = {**current, "last_source_sequence": "1"}
    same_time_newer_sequence = dict(projection)
    same_time_newer_sequence["event_id"] = "newer-event"
    same_time_newer_sequence["payload"] = {
        **projection["payload"],
        "source_sequence": "2",
    }
    assert core.projection_is_newer(numeric_current, same_time_newer_sequence) is True


def test_poc_boundary_closes_action_and_notification_invocations():
    core = _load("core")
    runtime = _load("app")
    matched = _matched(core)
    action = matched["payload"]["action"]

    action_result = runtime._poc_boundary(
        {
            "schema_version": "extension-action-invocation.v1",
            "invocation_id": matched["event_id"],
            "action_id": action["functionName"],
            "event": matched,
        }
    )
    notification = core.build_match_dispatch_events(matched, action_accepted=True)[1]
    notification_result = runtime._poc_boundary(notification)

    assert action_result["status"] == "ACCEPTED"
    assert notification_result == {
        "schema_version": "notification-delivery-result.v1",
        "event_id": notification["event_id"],
        "status": "ACCEPTED",
    }


def test_domain_consumer_routes_match_only_for_local_l2(monkeypatch):
    core = _load("core")
    runtime = _load("app")
    matched = _matched(core)
    encoded = base64.b64encode(core.canonical_json(matched).encode()).decode()
    push = {"message": {"data": encoded}}
    monkeypatch.setenv("L2_PROVIDER", "google")
    monkeypatch.setattr(runtime, "_dispatch_match", lambda event: 3)

    result = runtime._domain(push)

    assert result == {
        "schema_version": "domain-consumer-result.v1",
        "accepted": 1,
        "handled": True,
        "derived": 3,
    }


def test_workflow_callback_publishes_one_terminal_outcome(monkeypatch):
    core = _load("core")
    runtime = _load("app")
    notification = core.build_match_dispatch_events(
        _matched(core), action_accepted=True
    )[1]
    published = []
    monkeypatch.setenv("DOMAIN_TOPIC", "projects/test/topics/domain")
    monkeypatch.setattr(
        runtime, "_publish", lambda topic, event: published.append((topic, event))
    )

    runtime._record_workflow_outcome(
        {
            "schema_version": "workflow-outcome.v1",
            "workflow_request": notification,
            "status": "SUCCEEDED",
        }
    )

    assert len(published) == 1
    assert published[0][1]["event_type"] == core.EVENT_WORKFLOW_OUTCOME
    assert published[0][1]["payload"]["status"] == "SUCCEEDED"


def test_model_and_relationship_projection_variants_are_closed():
    core = _load("core")
    source = _received(core)
    model = core.derive_event(
        source,
        event_type=core.EVENT_TWIN_MODEL_UPSERTED,
        producer="component.twin-management",
        payload={
            "model_id": "poc-device",
            "model_version": "1",
            "model_document": {"display_name": "PoC Device"},
        },
    )
    relationship = core.derive_event(
        source,
        event_type=core.EVENT_TWIN_RELATIONSHIP_UPSERTED,
        producer="component.twin-management",
        payload={
            "relationship_id": "contains-1",
            "from_twin_id": "twin-1",
            "to_twin_id": "twin-2",
            "type": "contains",
        },
    )

    assert core.validate_twin_projection(model) == model
    assert core.validate_twin_projection(relationship) == relationship

    invalid = dict(relationship)
    invalid["payload"] = {**relationship["payload"], "unbounded": True}
    with pytest.raises(core.ContractError, match="INVALID_TWIN_PROJECTION"):
        core.validate_twin_projection(invalid)


def test_l4_seed_is_deterministic_bounded_and_firestore_path_safe():
    core = _load("core")
    devices = [
        {
            "id": "building/floor/device-1",
            "properties": [
                {"name": "temperature", "dataType": "DOUBLE", "initValue": 21.5}
            ],
        },
        {"id": "device-2", "properties": []},
    ]

    first = core.build_seed_twin_documents(devices, deployment_id="deployment-1")
    second = core.build_seed_twin_documents(devices, deployment_id="deployment-1")

    assert first == second
    assert len(first) == 6
    assert all(len(path.split("/")) in {2, 4} for path in first)
    assert any(
        document.get("twin_id") == "building/floor/device-1"
        for document in first.values()
    )
    assert any(
        document.get("current_values", {}).get("temperature") == 21.5
        for document in first.values()
    )

    fallback = core.build_seed_twin_documents([], deployment_id="deployment-1")
    assert any(
        document.get("twin_id") == "poc-device-001" for document in fallback.values()
    )


def test_twin_materializer_is_a_separate_runtime_boundary(monkeypatch):
    core = _load("core")
    runtime = _load("app")
    projection = core.build_twin_projection(
        core.build_processed_event(
            _received(core),
            _extension_response(_received(core)),
        )
    )
    assert projection is not None
    encoded = base64.b64encode(core.canonical_json(projection).encode()).decode()
    monkeypatch.setattr(runtime, "_ensure_seeded_twin_content", lambda: False)
    monkeypatch.setattr(runtime, "_materialize_twin_projection", lambda event: True)

    result = runtime._twin_materializer({"message": {"data": encoded}})

    assert result == {
        "schema_version": "twin-materializer-result.v1",
        "accepted": 1,
        "changed": True,
    }


def test_twin_explorer_health_requires_readable_seed(monkeypatch):
    runtime = _load("app")
    calls = []
    monkeypatch.setenv("RUNTIME_ROLE", "twin-explorer")
    monkeypatch.setattr(
        runtime, "_probe_seeded_twin_content", lambda: calls.append(True)
    )

    response = runtime.app.test_client().get("/healthz")

    assert response.status_code == 200
    assert response.get_json()["role"] == "twin-explorer"
    assert calls == [True]


def test_twin_explorer_is_read_only_bounded_and_escapes_content(monkeypatch):
    runtime = _load("app")
    monkeypatch.setenv("RUNTIME_ROLE", "twin-explorer")
    monkeypatch.setattr(
        runtime,
        "_list_twin_collection",
        lambda collection, limit: (
            [{"twin_id": "<device&1>"}] if collection == "twins" else []
        ),
    )
    monkeypatch.setattr(runtime, "_twin_detail", lambda twin_id: {"twin": twin_id})

    response = runtime.app.test_client().get("/?twin_id=%3Cdevice%261%3E")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert b"&lt;device&amp;1&gt;" in response.data
    assert b"<device&1>" not in response.data


def test_raw_history_query_cursor_and_points_are_closed():
    core = _load("core")
    params = {
        "device_id": "device-1",
        "metric": "temperature",
        "from": "2026-08-05T00:00:00Z",
        "to": "2026-08-05T01:00:00Z",
        "bucket_seconds": "0",
        "limit": "10",
    }
    query, start, end = core.parse_raw_history_query(params)
    query_digest = core.raw_history_query_digest(query, start, end)
    now = datetime(2026, 8, 5, 1, 0, tzinfo=timezone.utc)
    cursor = core.encode_history_cursor(
        {
            "kind": "raw",
            "shards": {
                "0": {
                    "stored_at": "2026-08-05T00:10:00Z",
                    "document_id": "document-1",
                }
            },
        },
        hmac_key="c" * 32,
        query_digest=query_digest,
        deployment_id="deployment-1",
        now=now,
    )

    decoded = core.decode_history_cursor(
        cursor,
        hmac_key="c" * 32,
        query_digest=query_digest,
        deployment_id="deployment-1",
        now=now,
    )
    assert decoded["kind"] == "raw"
    with pytest.raises(core.ContractError, match="INVALID_CURSOR"):
        core.decode_history_cursor(
            cursor,
            hmac_key="c" * 32,
            query_digest=query_digest,
            deployment_id="other-deployment",
            now=now,
        )

    points = core.normalize_history_points(
        [
            {
                "stored_at": "2026-08-05T00:10:00Z",
                "event_time": "2026-08-05T00:09:59Z",
                "value": 21.5,
            }
        ],
        0,
    )
    assert points == [
        {
            "stored_at": "2026-08-05T00:10:00.000000Z",
            "event_time": "2026-08-05T00:09:59.000000Z",
            "value": 21.5,
        }
    ]


def test_raw_history_reader_uses_hashed_deployment_key_and_closed_response(monkeypatch):
    runtime = _load("app")
    reader_key = "reader-secret"
    monkeypatch.setenv("RUNTIME_ROLE", "raw-history-reader")
    monkeypatch.setenv(
        "READER_KEY_SHA256", hashlib.sha256(reader_key.encode()).hexdigest()
    )
    monkeypatch.setattr(
        runtime,
        "_read_raw_history",
        lambda params: {
            "schema_version": "raw-history-query.v1",
            "device_id": params["device_id"],
            "metric": params["metric"],
            "points": [],
            "next_cursor": None,
            "truncated": False,
            "correlation_id": "correlation-1",
        },
    )
    path = (
        "/raw-history/v1?device_id=device-1&metric=temperature"
        "&from=2026-08-05T00:00:00Z&to=2026-08-05T01:00:00Z"
    )

    unauthorized = runtime.app.test_client().get(path)
    accepted = runtime.app.test_client().get(
        path,
        headers={"x-twin2multicloud-reader-key": reader_key},
    )
    health_unauthorized = runtime.app.test_client().get("/raw-history-health/v1")
    health = runtime.app.test_client().get(
        "/raw-history-health/v1",
        headers={"x-twin2multicloud-reader-key": reader_key},
    )

    assert unauthorized.status_code == 401
    assert unauthorized.get_json()["code"] == "READER_UNAUTHORIZED"
    assert health_unauthorized.status_code == 401
    assert health.get_json() == {
        "schema_version": "raw-history-health.v1",
        "status": "ready",
    }
    assert accepted.status_code == 200
    assert set(accepted.get_json()) == {
        "schema_version",
        "device_id",
        "metric",
        "points",
        "next_cursor",
        "truncated",
        "correlation_id",
    }
    assert accepted.headers["cache-control"] == "no-store"


def test_cloud_run_ingress_publishes_one_ordered_canonical_event(monkeypatch):
    core = _load("core")
    runtime = _load("app")
    published = []
    monkeypatch.setenv("RUNTIME_ROLE", "event-adapter")
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("L2_PROVIDER", "google")
    monkeypatch.setenv("RECEIVED_TOPIC", "projects/test/topics/received")
    monkeypatch.setattr(
        runtime, "_publish", lambda topic, event: published.append((topic, event))
    )

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


def test_cross_cloud_sources_use_directional_gcp_outboxes(monkeypatch):
    core = _load("core")
    runtime = _load("app")
    received = _received(core)
    processed = core.build_processed_event(received, _extension_response(received))
    projection = core.build_twin_projection(processed)
    command = core.derive_event(
        processed,
        event_type=core.EVENT_DEVICE_COMMAND_REQUESTED,
        producer="component.rule-dispatcher",
        payload={"device_id": "device-1", "message": "cool-down"},
    )
    outcome = core.derive_event(
        command,
        event_type=core.EVENT_COMMAND_OUTCOME,
        producer="component.device-command-adapter",
        payload={
            "device_id": "device-1",
            "invocation_id": command["event_id"],
            "status": "ACCEPTED",
        },
    )
    published = []
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("L1_PROVIDER", "aws")
    monkeypatch.setenv("L2_PROVIDER", "azure")
    monkeypatch.setenv("HOT_PROVIDER", "aws")
    monkeypatch.setenv("TWIN_PROVIDER", "azure")
    monkeypatch.setenv(
        "REMOTE_TELEMETRY_TOPIC", "projects/test/topics/remote-telemetry"
    )
    monkeypatch.setenv("REMOTE_CONTROL_TOPIC", "projects/test/topics/remote-control")
    monkeypatch.setattr(
        runtime, "_publish", lambda topic, event: published.append((topic, event))
    )
    monkeypatch.setattr(
        runtime,
        "_invoke_processor_extension",
        lambda _event: _extension_response(received),
    )
    monkeypatch.setattr(runtime, "_configured_rules", lambda: [])
    monkeypatch.setattr(runtime, "_persist", lambda _event: True)

    runtime._ingress(dict(received))
    runtime._process(
        {
            "message": {
                "data": base64.b64encode(
                    core.canonical_json(received).encode()
                ).decode()
            }
        }
    )
    runtime._persistence(
        {
            "message": {
                "data": base64.b64encode(
                    core.canonical_json(processed).encode()
                ).decode()
            }
        }
    )
    for event in (command, outcome):
        runtime._domain(
            {
                "message": {
                    "data": base64.b64encode(
                        core.canonical_json(event).encode()
                    ).decode()
                }
            }
        )

    assert [(topic, event["event_type"]) for topic, event in published] == [
        ("projects/test/topics/remote-telemetry", core.EVENT_TELEMETRY_RECEIVED),
        ("projects/test/topics/remote-telemetry", core.EVENT_TELEMETRY_PROCESSED),
        ("projects/test/topics/remote-control", projection["event_type"]),
        ("projects/test/topics/remote-control", core.EVENT_DEVICE_COMMAND_REQUESTED),
        ("projects/test/topics/remote-control", core.EVENT_COMMAND_OUTCOME),
    ]


@pytest.mark.parametrize(
    ("event_factory", "provider_name", "topic_name"),
    (
        (lambda core: _received(core), "L2_PROVIDER", "received"),
        (
            lambda core: core.build_processed_event(
                _received(core), _extension_response(_received(core))
            ),
            "HOT_PROVIDER",
            "processed",
        ),
        (
            lambda core: core.build_twin_projection(
                core.build_processed_event(
                    _received(core), _extension_response(_received(core))
                )
            ),
            "TWIN_PROVIDER",
            "domain",
        ),
    ),
)
def test_remote_landing_republishes_only_to_selected_local_owner(
    monkeypatch, event_factory, provider_name, topic_name
):
    core = _load("core")
    runtime = _load("app")
    event = event_factory(core)
    published = []
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv(provider_name, "google")
    monkeypatch.setenv("REMOTE_EVENT_TYPES_JSON", json.dumps([event["event_type"]]))
    monkeypatch.setenv("RECEIVED_TOPIC", "projects/test/topics/received")
    monkeypatch.setenv("PROCESSED_TOPIC", "projects/test/topics/processed")
    monkeypatch.setenv("DOMAIN_TOPIC", "projects/test/topics/domain")
    monkeypatch.setattr(
        runtime, "_publish", lambda topic, item: published.append((topic, item))
    )

    result = runtime._remote_landing(
        {
            "message": {
                "data": base64.b64encode(core.canonical_json(event).encode()).decode()
            }
        }
    )

    assert result["event_type"] == event["event_type"]
    assert published == [(f"projects/test/topics/{topic_name}", event)]


def test_six_layer_remote_landing_republishes_to_gcp_event_layer(monkeypatch):
    core = _load_six_layer("core")
    runtime = _load_six_layer("app")
    event = _received(core)
    published = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("EVENT_LAYER_PROVIDER", "google")
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("REMOTE_EVENT_TYPES_JSON", json.dumps([event["event_type"]]))
    monkeypatch.setenv("RECEIVED_TOPIC", "projects/test/topics/event-received")
    monkeypatch.setattr(
        runtime,
        "_publish",
        lambda topic, item: published.append((topic, item)),
    )

    result = runtime._remote_landing(
        {
            "message": {
                "data": base64.b64encode(core.canonical_json(event).encode()).decode()
            }
        }
    )

    assert result["event_type"] == event["event_type"]
    assert published == [("projects/test/topics/event-received", event)]


def test_six_layer_processor_returns_processed_event_to_remote_event_layer(
    monkeypatch,
):
    core = _load_six_layer("core")
    runtime = _load_six_layer("app")
    received = _received(core)
    published = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("EVENT_LAYER_PROVIDER", "aws")
    monkeypatch.setenv(
        "REMOTE_TELEMETRY_TOPIC",
        "projects/test/topics/to-event-layer",
    )
    monkeypatch.setattr(
        runtime,
        "_invoke_processor_extension",
        lambda _event: _extension_response(received),
    )
    monkeypatch.setattr(
        runtime,
        "_publish",
        lambda topic, event: published.append((topic, event)),
    )
    monkeypatch.setattr(
        runtime,
        "_configured_rules",
        lambda: pytest.fail("Six-layer processor evaluated rules before Eventing"),
    )

    result = runtime._process(
        {
            "message": {
                "data": base64.b64encode(
                    core.canonical_json(received).encode()
                ).decode()
            }
        }
    )

    assert result["matched"] == 0
    assert published[0][0] == "projects/test/topics/to-event-layer"
    assert published[0][1]["event_type"] == core.EVENT_TELEMETRY_PROCESSED


def test_six_layer_ingress_routes_to_remote_event_layer_even_when_l2_is_local(
    monkeypatch,
):
    core = _load_six_layer("core")
    runtime = _load_six_layer("app")
    published = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("EVENT_LAYER_PROVIDER", "aws")
    monkeypatch.setenv("L2_PROVIDER", "google")
    monkeypatch.setenv("RECEIVED_TOPIC", "projects/test/topics/local-received")
    monkeypatch.setenv(
        "REMOTE_TELEMETRY_TOPIC",
        "projects/test/topics/to-event-layer",
    )
    monkeypatch.setattr(
        runtime,
        "_publish",
        lambda topic, event: published.append((topic, event)),
    )

    result = runtime._ingress(dict(_received(core)))

    assert result["accepted"] == 1
    assert published[0][0] == "projects/test/topics/to-event-layer"
    assert published[0][1]["event_type"] == core.EVENT_TELEMETRY_RECEIVED


def test_six_layer_ingress_routes_to_local_event_layer_when_l2_is_remote(
    monkeypatch,
):
    core = _load_six_layer("core")
    runtime = _load_six_layer("app")
    published = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("EVENT_LAYER_PROVIDER", "google")
    monkeypatch.setenv("L2_PROVIDER", "azure")
    monkeypatch.setenv("RECEIVED_TOPIC", "projects/test/topics/local-received")
    monkeypatch.setenv(
        "REMOTE_TELEMETRY_TOPIC",
        "projects/test/topics/unused-remote",
    )
    monkeypatch.setattr(
        runtime,
        "_publish",
        lambda topic, event: published.append((topic, event)),
    )

    result = runtime._ingress(dict(_received(core)))

    assert result["accepted"] == 1
    assert published[0][0] == "projects/test/topics/local-received"
    assert published[0][1]["event_type"] == core.EVENT_TELEMETRY_RECEIVED


def test_six_layer_processed_landing_fans_out_to_local_hot_and_l2(monkeypatch):
    core = _load_six_layer("core")
    runtime = _load_six_layer("app")
    received = _received(core)
    processed = core.build_processed_event(received, _extension_response(received))
    matched = core.derive_event(
        processed,
        event_type=core.EVENT_MATCHED,
        producer="component.rule-evaluator",
        payload={"device_id": "device-1", "rule_id": "rule-1", "action": {}},
    )
    published = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("EVENT_LAYER_PROVIDER", "aws")
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("HOT_PROVIDER", "google")
    monkeypatch.setenv("L2_PROVIDER", "google")
    monkeypatch.setenv(
        "REMOTE_EVENT_TYPES_JSON",
        json.dumps([core.EVENT_TELEMETRY_PROCESSED]),
    )
    monkeypatch.setenv("PROCESSED_TOPIC", "projects/test/topics/processed")
    monkeypatch.setenv(
        "REMOTE_CONTROL_TOPIC",
        "projects/test/topics/to-event-layer-control",
    )
    monkeypatch.setattr(runtime, "_configured_rules", lambda: [])
    monkeypatch.setattr(
        runtime.core,
        "build_rule_matches",
        lambda _event, _rules: [matched],
    )
    monkeypatch.setattr(
        runtime,
        "_publish",
        lambda topic, event: published.append((topic, event)),
    )

    result = runtime._remote_landing(
        {
            "message": {
                "data": base64.b64encode(
                    core.canonical_json(processed).encode()
                ).decode()
            }
        }
    )

    assert result["accepted"] == 1
    assert [(topic, event["event_type"]) for topic, event in published] == [
        ("projects/test/topics/processed", core.EVENT_TELEMETRY_PROCESSED),
        ("projects/test/topics/to-event-layer-control", core.EVENT_MATCHED),
    ]


def test_six_layer_event_delivery_rejects_a_misowned_consumer_role(monkeypatch):
    core = _load_six_layer("core")
    runtime = _load_six_layer("app")
    processed = core.build_processed_event(
        _received(core),
        _extension_response(_received(core)),
    )
    monkeypatch.setenv("HOT_PROVIDER", "aws")

    with pytest.raises(
        runtime.core.ContractError,
        match="EVENTING_CONSUMER_PROVIDER_MISMATCH",
    ):
        runtime._consume_eventing_delivery("historical-persistence", processed)


def test_six_layer_local_rule_evaluator_returns_match_to_event_control(monkeypatch):
    core = _load_six_layer("core")
    runtime = _load_six_layer("app")
    processed = core.build_processed_event(
        _received(core),
        _extension_response(_received(core)),
    )
    matched = core.derive_event(
        processed,
        event_type=core.EVENT_MATCHED,
        producer="component.rule-evaluator",
        payload={"device_id": "device-1", "rule_id": "rule-1", "action": {}},
    )
    published = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("L2_PROVIDER", "google")
    monkeypatch.setenv(
        "REMOTE_CONTROL_TOPIC",
        "projects/test/topics/event-control",
    )
    monkeypatch.setattr(runtime, "_configured_rules", lambda: [])
    monkeypatch.setattr(
        runtime.core,
        "build_rule_matches",
        lambda _event, _rules: [matched],
    )
    monkeypatch.setattr(
        runtime,
        "_publish",
        lambda topic, event: published.append((topic, event)),
    )

    runtime._consume_eventing_delivery("rule-evaluator", processed)

    assert published == [("projects/test/topics/event-control", matched)]


def test_six_layer_control_landing_routes_match_to_local_l2(monkeypatch):
    core = _load_six_layer("core")
    runtime = _load_six_layer("app")
    processed = core.build_processed_event(
        _received(core),
        _extension_response(_received(core)),
    )
    matched = core.derive_event(
        processed,
        event_type=core.EVENT_MATCHED,
        producer="component.rule-evaluator",
        payload={"device_id": "device-1", "rule_id": "rule-1", "action": {}},
    )
    published = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("EVENT_LAYER_PROVIDER", "aws")
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("L2_PROVIDER", "google")
    monkeypatch.setenv(
        "REMOTE_EVENT_TYPES_JSON",
        json.dumps([core.EVENT_MATCHED]),
    )
    monkeypatch.setenv("DOMAIN_TOPIC", "projects/test/topics/domain")
    monkeypatch.setattr(
        runtime,
        "_publish",
        lambda topic, event: published.append((topic, event)),
    )

    result = runtime._remote_landing(
        {
            "message": {
                "data": base64.b64encode(core.canonical_json(matched).encode()).decode()
            }
        }
    )

    assert result["accepted"] == 1
    assert published == [("projects/test/topics/domain", matched)]


@pytest.mark.parametrize(
    ("deployment_id", "allowed_event_types"),
    (
        ("another-deployment", ["telemetry.received.v1"]),
        ("deployment-1", ["telemetry.processed.v1"]),
    ),
)
def test_remote_landing_rejects_cross_deployment_or_unselected_event(
    monkeypatch, deployment_id, allowed_event_types
):
    core = _load("core")
    runtime = _load("app")
    event = _received(core)
    event["deployment_id"] = deployment_id
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("L2_PROVIDER", "google")
    monkeypatch.setenv("REMOTE_EVENT_TYPES_JSON", json.dumps(allowed_event_types))

    with pytest.raises(runtime.core.ContractError, match="UNEXPECTED_REMOTE_EVENT"):
        runtime._remote_landing(
            {
                "message": {
                    "data": base64.b64encode(
                        core.canonical_json(event).encode()
                    ).decode()
                }
            }
        )


def test_ingress_records_canonical_device_command_outcome(monkeypatch):
    core = _load("core")
    runtime = _load("app")
    command = core.derive_event(
        _received(core),
        event_type=core.EVENT_DEVICE_COMMAND_REQUESTED,
        producer="component.rule-dispatcher",
        payload={"device_id": "device-1", "message": "cool-down"},
    )
    published = []
    monkeypatch.setenv("DEPLOYMENT_ID", "deployment-1")
    monkeypatch.setenv("DOMAIN_TOPIC", "projects/test/topics/domain")
    monkeypatch.setattr(
        runtime, "_publish", lambda topic, event: published.append((topic, event))
    )

    result = runtime._ingress(
        {
            "schema_version": "device-command-delivery.v1",
            "command": command,
            "status": "ACCEPTED",
        }
    )

    assert result["event_type"] == core.EVENT_COMMAND_OUTCOME
    assert published[0][0] == "projects/test/topics/domain"
    assert published[0][1]["payload"]["status"] == "ACCEPTED"


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
            "data": base64.b64encode(
                json.dumps({"device_id": "device-1"}).encode()
            ).decode()
        }
    }

    with pytest.raises(runtime.core.ContractError, match="INVALID_CANONICAL_EVENT"):
        runtime._decode_pubsub_push(push)
