import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from scripts import core_live_aws as aws
from scripts.run_core_evaluation import safe_failure_metrics


def install_stream(monkeypatch, page):
    calls, pauses = [], []
    def get_records(ShardIterator, Limit):
        kind, sequence = ShardIterator.split(":")
        calls.append((kind, int(sequence)))
        return page(kind, int(sequence))
    client = SimpleNamespace(
        list_shards=lambda **_: {"Shards": [{"ShardId": "one"}]},
        get_shard_iterator=lambda **k: {"ShardIterator": k["StreamName"].rsplit("-", 1)[-1] + ":0"},
        get_records=get_records,
    )
    monkeypatch.setattr(aws, "session", lambda _: SimpleNamespace(client=lambda _: client))
    monkeypatch.setattr(aws.time, "sleep", pauses.append)
    return calls, pauses


def records(kind, *, bad_value=False, bad_quality=False):
    return [{"Data": json.dumps({
        "correlation_id": f"case-{n}", "event_type": f"telemetry.{kind}.v1",
        "payload": {"value": 99 if bad_value else n,
                    "quality": "rejected" if bad_quality else "accepted"},
    }).encode()} for n in range(10)]


def test_empty_pages_advance_cursor_without_losing_exact_event_checks(monkeypatch):
    calls, pauses = install_stream(monkeypatch, lambda kind, n: {
        "Records": [] if n < 2 else records(kind), "NextShardIterator": f"{kind}:{n+1}"})
    assert aws.stream_evidence({"digital_twin_name": "case"}) == {"received": 10, "processed": 10}
    assert calls == [(kind, n) for kind in ("received", "processed") for n in range(3)]
    assert pauses == [1] * 4


@pytest.mark.parametrize("closed,expected_calls,expected_pauses", [(False, 40, 38), (True, 2, 0)])
def test_missing_records_remain_bounded_and_do_not_pass(monkeypatch, closed, expected_calls, expected_pauses):
    calls, pauses = install_stream(monkeypatch, lambda kind, n: {
        "Records": [], "NextShardIterator": None if closed else f"{kind}:{n+1}"})
    assert aws.stream_evidence({"digital_twin_name": "case"}) == {"received": 0, "processed": 0}
    assert len(calls) == expected_calls
    assert len(pauses) == expected_pauses


@pytest.mark.parametrize("bad_value,bad_quality", [(True, False), (False, True)])
def test_invalid_values_or_processed_quality_fail_immediately(monkeypatch, bad_value, bad_quality):
    calls, pauses = install_stream(monkeypatch, lambda kind, n: {
        "Records": records(kind, bad_value=bad_value, bad_quality=bad_quality and kind == "processed"),
        "NextShardIterator": f"{kind}:{n+1}"})
    with pytest.raises(AssertionError):
        aws.stream_evidence({"digital_twin_name": "case"})
    assert len(calls) == (1 if bad_value else 2)
    assert pauses == []


def test_readback_still_requires_both_complete_streams_and_keeps_safe_counts(monkeypatch):
    payload = {"statusCode": 200, "body": json.dumps({"points": [{"value": n} for n in range(10)]})}
    client = SimpleNamespace(invoke=lambda **_: {"Payload": io.BytesIO(json.dumps(payload).encode())})
    monkeypatch.setattr(aws, "session", lambda _: SimpleNamespace(client=lambda _: client))
    monkeypatch.setattr(aws, "stream_evidence", lambda _: {"received": 10, "processed": 9})
    with pytest.raises(RuntimeError, match="CORE_EVENT_STREAM_READBACK_INCOMPLETE") as error:
        aws.readback({}, {"aws_component_storage_read_access_output": {"reader_function_name": "reader"}},
                     datetime.now(timezone.utc), 0)
    metrics = safe_failure_metrics(error.value)
    assert metrics["event_stream_received_records"] == 10
    assert metrics["event_stream_processed_records"] == 9
    assert metrics["event_stream_readback_seconds"] >= 0
