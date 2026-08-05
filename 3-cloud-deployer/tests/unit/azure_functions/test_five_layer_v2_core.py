"""Azure Five-layer v2 canonical envelope parity tests."""

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import uuid

import pytest


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
