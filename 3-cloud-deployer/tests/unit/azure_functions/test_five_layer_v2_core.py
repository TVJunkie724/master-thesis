"""Azure Five-layer v2 canonical envelope parity tests."""

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
from unittest.mock import MagicMock
import uuid

import pytest
from azure.core.exceptions import ResourceNotFoundError
from azure.cosmos.exceptions import CosmosBatchOperationError, CosmosResourceExistsError


CORE_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "azure"
    / "azure_functions"
    / "five-layer-v2"
    / "core.py"
)
SPEC = importlib.util.spec_from_file_location("azure_five_layer_v2_core", CORE_PATH)
assert SPEC and SPEC.loader
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)
FUNCTION_APP_PATH = CORE_PATH.with_name("function_app.py")
FUNCTION_SPEC = importlib.util.spec_from_file_location(
    "azure_five_layer_v2_function_app", FUNCTION_APP_PATH
)
assert FUNCTION_SPEC and FUNCTION_SPEC.loader
function_app = importlib.util.module_from_spec(FUNCTION_SPEC)
previous_core = sys.modules.get("core")
try:
    sys.modules["core"] = core
    FUNCTION_SPEC.loader.exec_module(function_app)
finally:
    if previous_core is None:
        sys.modules.pop("core", None)
    else:
        sys.modules["core"] = previous_core


def _event(**overrides):
    event_id = str(uuid.uuid4())
    value = {
        "schema_version": "canonical-domain-event.v1",
        "event_id": event_id,
        "event_type": "telemetry.received.v1",
        "deployment_id": "deployment",
        "source_id": "device-1",
        "source_sequence": "1",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": event_id,
        "causation_id": event_id,
        "producer": "component.device-ingress",
        "payload": {"device_id": "device-1", "temperature": 21.5},
    }
    value.update(overrides)
    return value


def test_accepts_exact_canonical_event_and_partition_key():
    event = _event()

    assert core.validate_canonical_event(event) == event
    assert core.partition_key(event) == "device-1"


def test_rejects_provider_route_metadata_in_domain_envelope():
    event = _event(destination_provider="aws")

    with pytest.raises(core.ContractError, match="INVALID_CANONICAL_EVENT"):
        core.validate_canonical_event(event)


def test_rejects_unknown_event_type_and_non_json_body():
    with pytest.raises(core.ContractError, match="UNKNOWN_DOMAIN_EVENT"):
        core.validate_canonical_event(_event(event_type="custom.event"))
    with pytest.raises(core.ContractError, match="INVALID_UTF8_JSON"):
        core.decode_message_body(b"not-json")


def test_legacy_json_decoder_is_bounded_without_requiring_event_fields():
    assert core.decode_json_object(b'{"iotDeviceId":"sensor-1"}') == {
        "iotDeviceId": "sensor-1"
    }
    with pytest.raises(core.ContractError, match="EVENT_TOO_LARGE"):
        core.decode_json_object(b"{" + b'"x":"' + b"a" * 300_000 + b'"}')


def test_derived_event_is_deterministic_and_preserves_correlation():
    source = _event()

    first = core.derive_event(
        source,
        event_type="telemetry.processed.v1",
        producer="component.telemetry-processor",
    )
    second = core.derive_event(
        source,
        event_type="telemetry.processed.v1",
        producer="component.telemetry-processor",
    )

    assert first == second
    assert first["causation_id"] == source["event_id"]
    assert first["correlation_id"] == source["correlation_id"]


def test_existing_simulator_payload_is_adapted_to_canonical_ingress():
    now = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)
    payload = {
        "iotDeviceId": "temperature-sensor-1",
        "time": "2026-08-04T11:59:59Z",
        "temperature": 28,
        "trace_id": "TRACE-12345678",
    }

    event = core.build_ingress_event(
        payload,
        deployment_id="deployment",
        default_metric="temperature",
        now=now,
    )

    assert event["event_type"] == "telemetry.received.v1"
    assert event["source_sequence"] == event["event_id"]
    assert event["payload"] == {
        "device_id": "temperature-sensor-1",
        "twin_id": "temperature-sensor-1",
        "metric": "temperature",
        "value": 28,
        "unit": "unspecified",
        "event_time": "2026-08-04T11:59:59Z",
        "projection_candidate": False,
    }


def test_processed_event_requires_exact_extension_result():
    source = core.build_ingress_event(
        {
            "iotDeviceId": "sensor-1",
            "time": "2026-08-04T11:59:59Z",
            "temperature": 2,
        },
        deployment_id="deployment",
        default_metric="temperature",
    )

    processed = core.build_processed_event(
        source,
        {"value": 4, "quality": "accepted"},
    )

    assert processed["event_type"] == "telemetry.processed.v1"
    assert processed["source_sequence"] == source["source_sequence"]
    assert processed["payload"]["value"] == 4
    with pytest.raises(core.ContractError, match="INVALID_PROCESSOR_RESULT"):
        core.build_processed_event(source, {"value": 4})


def test_processor_extension_invocation_uses_closed_runtime_envelope(monkeypatch):
    source = core.build_ingress_event(
        {
            "iotDeviceId": "sensor-1",
            "time": "2026-08-04T11:59:59Z",
            "temperature": 2,
            "unit": "celsius",
        },
        deployment_id="deployment",
        default_metric="temperature",
    )
    captured = {}

    def response(envelope):
        captured.update(envelope)
        return {
            "schema_version": "user-function-runtime-envelope.v1",
            "invocation_id": envelope["invocation_id"],
            "correlation_id": envelope["correlation_id"],
            "slot_id": "processor.telemetry",
            "status": "success",
            "payload": {"value": 4, "quality": "accepted"},
        }

    monkeypatch.setattr(function_app, "_post_extension", response)

    result = function_app._invoke_processor_extension(source)

    assert result == {"value": 4, "quality": "accepted"}
    assert set(captured) == {
        "schema_version",
        "invocation_id",
        "correlation_id",
        "occurred_at",
        "slot_id",
        "payload",
        "context",
    }
    assert captured["payload"] == {"value": 2, "unit": "celsius"}
    assert captured["context"] == {"twin_id": "sensor-1", "device_id": "sensor-1"}


def test_local_azure_processing_enqueues_processed_then_persists_projects_and_rules(
    monkeypatch,
):
    source = core.build_ingress_event(
        {
            "iotDeviceId": "sensor-1",
            "time": "2026-08-04T11:59:59Z",
            "temperature": 2,
            "projection_candidate": True,
        },
        deployment_id="deployment",
        default_metric="temperature",
    )
    writer = MagicMock(return_value=True)
    materializer = MagicMock()
    enqueue = MagicMock()
    rule_evaluator = MagicMock()
    monkeypatch.setenv("V2_HOT_PROVIDER", "azure")
    monkeypatch.setenv("V2_TWIN_PROVIDER", "azure")
    monkeypatch.setattr(
        function_app,
        "_invoke_processor_extension",
        lambda _event: {"value": 4, "quality": "accepted"},
    )
    monkeypatch.setattr(function_app, "_enqueue", enqueue)
    monkeypatch.setattr(function_app, "_write_raw_and_rollup", writer)
    monkeypatch.setattr(function_app, "_materialize_twin_projection", materializer)
    monkeypatch.setattr(function_app, "_evaluate_rules", rule_evaluator)

    function_app._process_received(source)

    processed = enqueue.call_args.args[0]
    assert processed["event_type"] == "telemetry.processed.v1"
    assert processed["payload"]["value"] == 4
    writer.assert_not_called()

    function_app._consume(processed)

    writer.assert_called_once_with(processed)
    projection = materializer.call_args.args[0]
    assert projection["event_type"] == "twin.state.upserted"
    assert projection["payload"]["state_patch"] == {"temperature": 4}
    rule_evaluator.assert_called_once_with(processed)


def test_rule_matches_have_distinct_ids_and_drive_all_embedded_paths(monkeypatch):
    event = _processed_event(projection_candidate=False)
    rules = [
        {
            "rule_id": "workflow-and-command",
            "condition": "sensor-1.temperature == DOUBLE(4)",
            "action": {
                "type": "logic_app",
                "functionName": "poc-action",
                "feedback": {
                    "iotDeviceId": "sensor-1",
                    "payload": "cool-down",
                },
            },
        },
        {
            "rule_id": "second-match",
            "condition": "temperature >= INTEGER(4)",
            "action": {"type": "lambda", "functionName": "second-action"},
        },
    ]

    matches = core.build_rule_matches(event, rules)

    assert len(matches) == 2
    assert matches[0]["event_id"] != matches[1]["event_id"]
    assert matches[0]["payload"]["rule_id"] == "workflow-and-command"
    enqueued = []
    monkeypatch.setattr(function_app, "_enqueue", enqueued.append)
    monkeypatch.setattr(function_app, "_invoke_poc_action", lambda *_args: True)

    function_app._dispatch_match(matches[0])

    assert [item["event_type"] for item in enqueued] == [
        "extension.action.outcome.v1",
        "notification.requested.v1",
        "device.command.requested.v1",
    ]

    with pytest.raises(core.ContractError, match="INVALID_RULE_CONFIGURATION"):
        core.build_rule_matches(
            event,
            [
                rules[0] | {"rule_id": "duplicate"},
                rules[1] | {"rule_id": "duplicate"},
            ],
        )


def test_fixed_poc_action_contract_is_closed_and_correlated():
    matched = core.build_rule_matches(
        _processed_event(projection_candidate=False),
        [
            {
                "condition": "temperature == DOUBLE(4)",
                "action": {"type": "lambda", "functionName": "poc-action"},
            }
        ],
    )[0]
    invocation = {
        "schema_version": "extension-action-invocation.v1",
        "invocation_id": matched["event_id"],
        "action_id": "poc-action",
        "event": matched,
    }

    assert function_app._poc_action_result(invocation) == {
        "schema_version": "extension-action-result.v1",
        "invocation_id": matched["event_id"],
        "action_id": "poc-action",
        "status": "ACCEPTED",
    }
    with pytest.raises(core.ContractError, match="INVALID_ACTION_INVOCATION"):
        function_app._poc_action_result(invocation | {"unknown": True})


def test_fixed_poc_notification_contract_accepts_only_notification_events():
    matched = core.build_rule_matches(
        _processed_event(projection_candidate=False),
        [
            {
                "condition": "temperature == DOUBLE(4)",
                "action": {"type": "logic_app", "functionName": "poc-action"},
            }
        ],
    )[0]
    notification = core.derive_event(
        matched,
        event_type="notification.requested.v1",
        producer="component.action-dispatcher",
        payload={"device_id": "sensor-1", "message": "temperature matched"},
    )

    assert function_app._poc_notification_result(notification) == {
        "schema_version": "notification-delivery-result.v1",
        "event_id": notification["event_id"],
        "status": "ACCEPTED",
    }
    with pytest.raises(core.ContractError, match="INVALID_NOTIFICATION_INVOCATION"):
        function_app._poc_notification_result(matched)


def test_duplicate_raw_retry_still_reaches_twin_and_rule_edges(monkeypatch):
    processed = _processed_event()
    materializer = MagicMock()
    evaluator = MagicMock()
    monkeypatch.setenv("V2_HOT_PROVIDER", "azure")
    monkeypatch.setenv("V2_TWIN_PROVIDER", "azure")
    monkeypatch.setattr(
        function_app, "_write_raw_and_rollup", MagicMock(return_value=False)
    )
    monkeypatch.setattr(function_app, "_materialize_twin_projection", materializer)
    monkeypatch.setattr(function_app, "_evaluate_rules", evaluator)

    function_app._consume(processed)

    materializer.assert_called_once()
    evaluator.assert_called_once_with(processed)


def test_workflow_and_command_emit_correlated_terminal_outcomes(monkeypatch):
    matched = core.build_rule_matches(
        _processed_event(projection_candidate=False),
        [
            {
                "condition": "temperature == DOUBLE(4)",
                "action": {
                    "type": "logic_app",
                    "functionName": "poc-action",
                    "feedback": {"iotDeviceId": "sensor-1", "payload": "cool-down"},
                },
            }
        ],
    )[0]
    emitted = []
    monkeypatch.setattr(function_app, "_enqueue", emitted.append)
    monkeypatch.setattr(
        function_app,
        "_post_bound_json",
        lambda _url, event, **_kwargs: {
            "status": "ACCEPTED",
            "event_id": event["event_id"],
        },
    )
    monkeypatch.setattr(function_app, "_send_device_command", lambda _event: True)
    notification = core.derive_event(
        matched,
        event_type="notification.requested.v1",
        producer="component.action-dispatcher",
        payload={"device_id": "sensor-1", "message": "test"},
    )
    command = core.derive_event(
        matched,
        event_type="device.command.requested.v1",
        producer="component.action-dispatcher",
        payload={"device_id": "sensor-1", "message": "test"},
    )

    function_app._start_notification_workflow(notification)
    function_app._deliver_device_command(command)

    assert [event["event_type"] for event in emitted] == [
        "notification.workflow.outcome.v1",
        "device.command.outcome.v1",
    ]
    assert all(
        event["correlation_id"] == matched["correlation_id"] for event in emitted
    )


def test_terminal_outcome_storage_is_idempotent_and_non_rollup(monkeypatch):
    processed = _processed_event(projection_candidate=False)
    outcome = core.derive_event(
        processed,
        event_type="extension.action.outcome.v1",
        producer="component.action-dispatcher",
        payload={
            "device_id": "sensor-1",
            "invocation_id": processed["event_id"],
            "status": "SUCCEEDED",
        },
    )
    stored_at = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)
    expected = core.outcome_document(
        outcome,
        stored_at=stored_at,
        hot_boundary_days=30,
    )
    container = MagicMock()
    monkeypatch.setenv("V2_HOT_PROVIDER", "azure")
    monkeypatch.setenv("V2_HOT_BOUNDARY_DAYS", "30")
    monkeypatch.setattr(function_app, "_COSMOS_CONTAINER", container)

    function_app._store_outcome(outcome, stored_at=stored_at)

    assert container.create_item.call_args.kwargs["body"] == expected
    assert expected["kind"] == "outcome"
    assert "metric" not in expected

    container.create_item.side_effect = CosmosResourceExistsError(message="exists")
    container.read_item.return_value = {"payload_digest": expected["payload_digest"]}
    function_app._store_outcome(outcome, stored_at=stored_at)

    container.read_item.return_value = {"payload_digest": "different"}
    with pytest.raises(core.ContractError, match="IDEMPOTENCY_CONFLICT"):
        function_app._store_outcome(outcome, stored_at=stored_at)


def test_envelope_field_set_matches_aws_v2_runtime():
    aws_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "providers"
        / "aws"
        / "lambda_functions"
        / "five-layer-v2"
        / "handler.py"
    )
    aws_spec = importlib.util.spec_from_file_location("aws_five_layer_v2", aws_path)
    assert aws_spec and aws_spec.loader
    aws = importlib.util.module_from_spec(aws_spec)
    aws_spec.loader.exec_module(aws)

    assert core.CANONICAL_EVENT_FIELDS == aws.CANONICAL_EVENT_FIELDS
    assert core.DOMAIN_EVENT_TYPES == aws.DOMAIN_EVENT_TYPES


def _history_params(**overrides):
    end = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)
    value = {
        "device_id": "device-1",
        "metric": "temperature",
        "from": (end - timedelta(hours=1)).isoformat(),
        "to": end.isoformat(),
        "bucket_seconds": "0",
        "limit": "1000",
    }
    value.update(overrides)
    return value


def test_raw_history_query_enforces_ranges_buckets_and_limit():
    query, start, end = core.parse_raw_history_query(_history_params())

    assert query == {
        "device_id": "device-1",
        "metric": "temperature",
        "bucket_seconds": 0,
        "limit": 1000,
        "cursor": None,
    }
    assert end - start == timedelta(hours=1)

    with pytest.raises(core.ContractError, match="INVALID_QUERY"):
        core.parse_raw_history_query(_history_params(unknown="ignored"))
    with pytest.raises(core.ContractError, match="INVALID_QUERY"):
        core.parse_raw_history_query(_history_params(bucket_seconds="60"))
    with pytest.raises(core.ContractError, match="INVALID_QUERY"):
        core.parse_raw_history_query(_history_params(limit="1001"))


def test_raw_history_query_rejects_more_than_24_hours_raw_and_allows_30_day_rollup():
    end = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)
    with pytest.raises(core.ContractError, match="QUERY_RANGE_EXCEEDED"):
        core.parse_raw_history_query(
            _history_params(**{"from": (end - timedelta(hours=25)).isoformat()})
        )

    query, start, parsed_end = core.parse_raw_history_query(
        _history_params(
            **{
                "from": (end - timedelta(days=30)).isoformat(),
                "bucket_seconds": "3600",
            }
        )
    )
    assert query["bucket_seconds"] == 3600
    assert parsed_end - start == timedelta(days=30)


def test_cursor_is_query_bound_tamper_evident_and_expires_after_15_minutes():
    now = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)
    query, start, end = core.parse_raw_history_query(_history_params())
    digest = core.raw_history_query_digest(query, start, end)
    key = "k" * 32
    cursor = core.encode_cursor(
        "opaque-cosmos-token",
        hmac_key=key,
        query_digest=digest,
        now=now,
    )

    assert (
        core.decode_cursor(
            cursor,
            hmac_key=key,
            query_digest=digest,
            now=now + timedelta(minutes=15),
        )
        == "opaque-cosmos-token"
    )
    with pytest.raises(core.ContractError, match="INVALID_CURSOR"):
        core.decode_cursor(cursor + "x", hmac_key=key, query_digest=digest, now=now)
    with pytest.raises(core.ContractError, match="INVALID_CURSOR"):
        core.decode_cursor(cursor, hmac_key=key, query_digest="different", now=now)
    with pytest.raises(core.ContractError, match="CURSOR_EXPIRED"):
        core.decode_cursor(
            cursor,
            hmac_key=key,
            query_digest=digest,
            now=now + timedelta(minutes=15, seconds=1),
        )


def test_cosmos_queries_are_partition_scoped_and_points_are_typed():
    raw = core.cosmos_raw_history_statement(0)
    rollup = core.cosmos_raw_history_statement(3600)

    assert "c.device_id = @device_id" in raw
    assert "c.kind = 'raw'" in raw
    assert "c.kind = 'hourly_rollup'" in rollup
    assert core.normalize_history_points(
        [
            {
                "bucket_start": "2026-08-04T11:00:00Z",
                "min": 1,
                "max": 3,
                "sum": 4,
                "count": 2,
            }
        ],
        3600,
    ) == [
        {
            "bucket_start": "2026-08-04T11:00:00Z",
            "min": 1,
            "max": 3,
            "avg": 2,
            "count": 2,
        }
    ]


def _processed_event(*, projection_candidate=True):
    source = core.build_ingress_event(
        {
            "iotDeviceId": "sensor-1",
            "time": "2026-08-04T11:59:59Z",
            "temperature": 2,
            "projection_candidate": projection_candidate,
        },
        deployment_id="deployment",
        default_metric="temperature",
    )
    return core.build_processed_event(
        source,
        {"value": 4, "quality": "accepted"},
    )


def test_cosmos_raw_and_rollup_documents_are_finite_and_deterministic():
    event = _processed_event()
    stored_at = datetime(2026, 8, 4, 12, 3, 4, tzinfo=timezone.utc)

    raw = core.raw_document(
        event,
        stored_at=stored_at,
        hot_boundary_days=30,
    )
    first = core.next_rollup_document(raw, None)
    second = core.next_rollup_document(raw | {"value": 3}, first)

    assert raw["storage_window"] == "2026-08-04T12:00:00Z"
    assert raw["bucket_start"] == "2026-08-04T12:00:00Z"
    assert raw["ttl"] == 32 * 86400
    assert first["count"] == 1
    assert second["count"] == 2
    assert second["sum"] == 7
    assert second["min"] == 3
    assert second["max"] == 4
    assert second["version"] == 2


def test_twin_projection_is_sparse_and_explicit():
    assert (
        core.build_twin_projection(_processed_event(projection_candidate=False)) is None
    )

    projection = core.build_twin_projection(_processed_event())

    assert projection is not None
    assert projection["event_type"] == "twin.state.upserted"
    assert projection["payload"]["state_patch"] == {"temperature": 4}


def test_cosmos_writer_executes_one_partition_transaction(monkeypatch):
    container = MagicMock()
    monkeypatch.setattr(function_app, "_COSMOS_CONTAINER", container)
    monkeypatch.setattr(
        function_app,
        "_read_item_or_none",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setenv("V2_HOT_BOUNDARY_DAYS", "30")

    function_app._write_raw_and_rollup(
        _processed_event(),
        stored_at=datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
    )

    call = container.execute_item_batch.call_args
    assert call.kwargs["partition_key"] == "sensor-1"
    operations = call.kwargs["batch_operations"]
    assert [operation[0] for operation in operations] == ["create", "create"]
    assert operations[0][1][0]["kind"] == "raw"
    assert operations[1][1][0]["kind"] == "hourly_rollup"


def test_cosmos_writer_reuses_identical_raw_event_and_rejects_conflict(monkeypatch):
    event = _processed_event()
    raw = core.raw_document(
        event,
        stored_at=datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
        hot_boundary_days=30,
    )
    container = MagicMock()
    monkeypatch.setattr(function_app, "_COSMOS_CONTAINER", container)
    monkeypatch.setenv("V2_HOT_BOUNDARY_DAYS", "30")
    monkeypatch.setattr(
        function_app,
        "_read_item_or_none",
        lambda *_args, **_kwargs: {"payload_digest": raw["payload_digest"]},
    )

    function_app._write_raw_and_rollup(
        event,
        stored_at=datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
    )
    container.execute_item_batch.assert_not_called()

    monkeypatch.setattr(
        function_app,
        "_read_item_or_none",
        lambda *_args, **_kwargs: {"payload_digest": "different"},
    )
    with pytest.raises(core.ContractError, match="IDEMPOTENCY_CONFLICT"):
        function_app._write_raw_and_rollup(
            event,
            stored_at=datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
        )


def test_cosmos_writer_retries_etag_conflict_with_fresh_rollup(monkeypatch):
    event = _processed_event()
    raw = core.raw_document(
        event,
        stored_at=datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
        hot_boundary_days=30,
    )
    old_rollup = core.next_rollup_document(raw, None) | {"_etag": "etag-1"}
    fresh_rollup = core.next_rollup_document(raw | {"value": 1}, old_rollup) | {
        "_etag": "etag-2"
    }
    container = MagicMock()
    container.execute_item_batch.side_effect = [
        CosmosBatchOperationError(
            headers={},
            status_code=412,
            operation_responses=[{"statusCode": 412}],
        ),
        None,
    ]
    reads = iter([None, old_rollup, None, fresh_rollup])
    monkeypatch.setattr(function_app, "_COSMOS_CONTAINER", container)
    monkeypatch.setattr(
        function_app,
        "_read_item_or_none",
        lambda *_args, **_kwargs: next(reads),
    )
    monkeypatch.setattr(function_app.time, "sleep", lambda _delay: None)
    monkeypatch.setenv("V2_HOT_BOUNDARY_DAYS", "30")

    function_app._write_raw_and_rollup(
        event,
        stored_at=datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
    )

    assert container.execute_item_batch.call_count == 2
    replacement = container.execute_item_batch.call_args.kwargs["batch_operations"][1]
    assert replacement[0] == "replace"
    assert replacement[2] == {"if_match_etag": "etag-2"}


def test_adt_projection_is_idempotent_and_updates_seed_properties(monkeypatch):
    projection = core.build_twin_projection(_processed_event())
    assert projection is not None
    client = MagicMock()
    client.get_digital_twin.return_value = {"lastEventId": "older"}
    monkeypatch.setattr(function_app, "_ADT_CLIENT", client)

    function_app._materialize_twin_projection(projection)

    paths = {item["path"] for item in client.update_digital_twin.call_args.args[1]}
    assert paths == {
        "/status",
        "/lastUpdate",
        "/sourceSequence",
        "/lastEventId",
        "/metric",
        "/value",
    }
    client.reset_mock()
    client.get_digital_twin.return_value = {"lastEventId": projection["event_id"]}

    function_app._materialize_twin_projection(projection)

    client.update_digital_twin.assert_not_called()


def test_adt_projection_creates_a_missing_poc_twin(monkeypatch):
    projection = core.build_twin_projection(_processed_event())
    assert projection is not None
    client = MagicMock()
    client.get_digital_twin.side_effect = ResourceNotFoundError("missing")
    monkeypatch.setattr(function_app, "_ADT_CLIENT", client)
    monkeypatch.setenv("V2_HOT_PROVIDER", "gcp")

    function_app._materialize_twin_projection(projection)

    twin_id, twin = client.upsert_digital_twin.call_args.args
    assert twin_id == "sensor-1"
    assert twin["$metadata"]["$model"] == "dtmi:twin2multicloud:poc:TwinNode;1"
    assert twin["provider"] == "gcp"
    assert twin["metric"] == "temperature"
    assert twin["value"] == 4
