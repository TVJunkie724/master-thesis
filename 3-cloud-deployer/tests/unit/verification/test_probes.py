from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.verification import probes


@pytest.mark.parametrize("sequence,success", [("VERIFY-TARGET", True), ("VERIFY-OTHER", False)])
def test_azure_storage_probe_uses_entra_and_keeps_exact_correlation(monkeypatch, sequence, success):
    import sys

    credential = object()
    monkeypatch.setitem(sys.modules, "azure.identity", SimpleNamespace(ClientSecretCredential=Mock(return_value=credential)))
    master_keys = Mock(side_effect=AssertionError("Account keys must not be used"))
    monkeypatch.setitem(sys.modules, "azure.mgmt.cosmosdb", SimpleNamespace(CosmosDBManagementClient=master_keys))
    container = Mock()
    container.query_items.return_value = [{"payload": {"source_sequence": sequence}}]
    client = Mock()
    client.get_database_client.return_value.get_container_client.return_value = container
    factory = Mock(return_value=client)
    monkeypatch.setitem(sys.modules, "azure.cosmos", SimpleNamespace(CosmosClient=factory))
    bundle = {"endpoint": "https://test.documents.azure.com", "database_name": "history", "container_name": "telemetry"}
    result = probes._check_azure_hot_storage_trace(
        "device-1", "VERIFY-TARGET", {"azure_component_hot_storage_output": bundle}, {}, .002, .001
    )
    assert result.success is success
    factory.assert_called_once_with(bundle["endpoint"], credential=credential)
    master_keys.assert_not_called()
    assert container.query_items.call_args.kwargs["partition_key"] == "device-1"


@pytest.mark.parametrize("change,success", [
    ({}, True), ({"metric": "other"}, False), ({"value": 21.0}, False),
    ({"value": float("nan")}, False), ({"sourceSequence": "older"}, False),
    ({"observedAt": "2000-01-01T00:00:00Z"}, False),
    ({"observedAt": "2099-01-01T00:00:00Z"}, False),
    ({"observedAt": "2026-10-04T00:00:00"}, False),
    ({"state": "UPDATING"}, False),
])
def test_twinmaker_requires_one_matching_native_snapshot(monkeypatch, change, success):
    import boto3

    sent_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    fields = dict(metric="temperature", value=20.5, sourceSequence="seq-1",
                  observedAt=sent_at.isoformat(), state="ACTIVE")
    fields.update(change)
    response = {
        "status": {"state": fields.pop("state")},
        "components": {"telemetry": {"properties": {
            key: {"value": {"doubleValue" if key == "value" else "stringValue": value}}
            for key, value in fields.items()
        }}},
    }
    client = SimpleNamespace(get_entity=lambda **_: response)
    monkeypatch.setattr(boto3, "Session", lambda **_: SimpleNamespace(client=lambda _: client))
    ticks = iter([0, 0, 2, 3, 4])
    monkeypatch.setattr(probes.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(probes.time, "sleep", lambda _: None)
    result = probes.check_twinmaker_projection(
        "workspace", "sensor", "temperature", 20.5, "seq-1", sent_at, 1, 0,
        aws_region="eu-central-1", aws_credentials={},
    )
    assert result.success is success
    if success:
        assert result.evidence["kind"] == "twinmaker_property_projection"


class _Response:
    status_code = 200

    @staticmethod
    def json():
        return {
            "items": [
                {"trace_id": "VERIFY-OTHER"},
                {"trace_id": "VERIFY-TARGET"},
            ]
        }


def test_hot_reader_rejects_non_https_endpoint(monkeypatch):
    called = False

    def get(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(probes.requests, "get", get)

    result = probes.poll_hot_reader(
        "http://example.test/reader",
        "device-1",
        None,
        1,
        0,
        trace_id="VERIFY-TARGET",
    )

    assert result.success is False
    assert "HTTPS" in result.error
    assert called is False


def test_hot_reader_only_accepts_current_trace(monkeypatch):
    monkeypatch.setattr(probes.requests, "get", lambda *args, **kwargs: _Response())

    result = probes.poll_hot_reader(
        "https://example.test/reader",
        "device-1",
        "token",
        1,
        0,
        trace_id="VERIFY-TARGET",
    )

    assert result.success is True
    assert result.evidence == {"record_count": 1}


def test_unknown_log_provider_fails_without_cloud_access():
    result = probes.check_cloud_logs(
        "unsupported",
        "marker",
        "event_checker",
        {},
        {},
        Path("/tmp/project"),
        1,
        0,
    )

    assert result.success is False
    assert result.error == "Unsupported provider: unsupported"


def test_hot_storage_trace_dispatches_gcp_alias(monkeypatch):
    captured = {}

    def check(*args):
        captured["args"] = args
        return probes.ProbeResult(success=True)

    monkeypatch.setattr(probes, "_check_gcp_hot_storage_trace", check)

    result = probes.check_hot_storage_trace(
        "google",
        "device-1",
        "VERIFY-1234ABCD",
        {},
        {"gcp": {}},
        Path("/tmp/project"),
        1,
        0,
    )

    assert result.success is True
    assert captured["args"][0:2] == ("device-1", "VERIFY-1234ABCD")
