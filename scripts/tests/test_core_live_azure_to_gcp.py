from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from scripts import core_live_azure_to_gcp as directed
from scripts.prepare_core_runtime import prepare
from scripts.run_core_evaluation import safe_failure_metrics
from src.providers.terraform.azure_six_layer_image_publisher import image_requests as azure_images
from src.providers.terraform.gcp_six_layer_image_publisher import image_requests as gcp_images


def test_fixed_case_uses_azure_ingress_and_gcp_core(tmp_path):
    runtime = tmp_path / "runtime"
    values = prepare("gcp", runtime)
    directed.configure(values, runtime)
    assert values["layer_1_provider"] == "azure"
    assert values["layer_2_provider"] == values["event_layer_provider"] == "google"
    assert values["layer_3_hot_provider"] == "google"
    assert values["layer_4_provider"] == values["layer_5_provider"] == ""
    assert list((runtime / ".build/azure").glob("*.zip"))
    assert azure_images(runtime, values) == ()
    assert {request.name for request in gcp_images(runtime, values)} == {
        "platform", "event-runtime", "processor-extension", "storage-mover",
    }
    assert {(route["source_provider"], route["destination_provider"])
            for route in values["resolved_cross_cloud_routes"]} == {
                ("azure", "gcp"), ("gcp", "azure"),
            }


def test_directed_smoke_uses_azure_sender_and_gcp_reader(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(directed, "source_functions_ready", lambda *_: {"azure_source_function_readiness_attempts": 1})
    monkeypatch.setattr(directed.azure, "send_telemetry", lambda *_: (now, 42.0))
    monkeypatch.setattr(directed.gcp, "readback", lambda *args: {
        "sent": 10, "read_back": 10, "args": args[2:],
    })
    result = directed.smoke({}, {})
    assert result["args"] == (now, 42.0)
    assert result["source_provider"] == "azure"
    assert result["destination_provider"] == "gcp"
    assert result["azure_source_function_readiness_attempts"] == 1


def test_source_readiness_waits_for_both_triggers(monkeypatch):
    calls = []
    def arm(_values, _method, path, **_kwargs):
        if path.endswith("/resources?api-version=2021-04-01"):
            return {"value": [{"type": "Microsoft.Web/sites", "id": "/sites/source"}]}
        calls.append(path)
        names = ["source/six-layer-iot-telemetry-adapter"]
        if len(calls) == 2:
            names.append("source/six-layer-cross-cloud-telemetry-bridge")
        return {"value": [{"name": name} for name in names]}
    monkeypatch.setattr(directed.azure, "arm", arm)
    monkeypatch.setattr(directed.time, "sleep", lambda *_: None)
    assert directed.source_functions_ready({"azure_subscription_id": "sub"},
                                           {"azure_six_layer_resource_group_name": "group"}) == {
        "azure_source_function_readiness_attempts": 2,
    }


def test_readback_timeout_keeps_source_and_outbox_counts(monkeypatch):
    monkeypatch.setattr(directed, "source_functions_ready", lambda *_: {
        "azure_source_function_readiness_attempts": 2})
    monkeypatch.setattr(directed.azure, "send_telemetry", lambda *_: (datetime.now(timezone.utc), 1.0))
    monkeypatch.setattr(directed.gcp, "readback", lambda *_: (_ for _ in ()).throw(
        RuntimeError("CORE_READBACK_TIMEOUT")))
    monkeypatch.setattr(directed, "azure_outbox_metrics", lambda *_: {
        "azure_outbox_metric_http_status": 200, "azure_outbox_incoming": 10,
        "azure_outbox_outgoing": 0})
    with pytest.raises(RuntimeError, match="CORE_READBACK_TIMEOUT") as raised:
        directed.smoke({}, {})
    assert safe_failure_metrics(raised.value) == {
        "azure_source_function_readiness_attempts": 2,
        "azure_outbox_metric_http_status": 200,
        "azure_outbox_incoming": 10,
        "azure_outbox_outgoing": 0,
    }


def test_outbox_metrics_return_only_counts(monkeypatch):
    monkeypatch.setattr(directed.azure, "arm", lambda *_args, **_kwargs: {
        "value": [{"type": "Microsoft.EventHub/namespaces", "id": "/namespace/id"}]})
    monkeypatch.setattr(directed.azure, "credential", lambda *_: SimpleNamespace(
        get_token=lambda *_: SimpleNamespace(token="private-test-token")))
    def get(*_args, **_kwargs):
        return SimpleNamespace(status_code=200, json=lambda: {"value": [
            {"name": {"value": "IncomingMessages"}, "timeseries": [
                {"data": [{"total": 4}, {"total": 6}]}]},
            {"name": {"value": "OutgoingMessages"}, "timeseries": [
                {"data": [{"total": 7}]}]},
        ]})
    monkeypatch.setattr(directed.requests, "get", get)
    result = directed.azure_outbox_metrics(
        {"azure_subscription_id": "sub"}, {"azure_six_layer_resource_group_name": "group"})
    assert result == {"azure_outbox_metric_http_status": 200,
                      "azure_outbox_incoming": 10, "azure_outbox_incoming_points": 2,
                      "azure_outbox_outgoing": 7, "azure_outbox_outgoing_points": 1}
    assert "private-test-token" not in str(result)


def test_failure_diagnostics_waits_only_for_delayed_azure_logs(monkeypatch):
    polls = []
    monkeypatch.setattr(directed.azure, "diagnostics", lambda *_: polls.append(1) or {
        "workspaces": [{"data": {"tables": [{"rows": [] if len(polls) == 1 else [["safe"]]}]}}]})
    monkeypatch.setattr(directed.gcp, "diagnostics", lambda *_: {"entries": []})
    monkeypatch.setattr(directed.time, "sleep", lambda seconds: polls.append(seconds))
    result = directed.diagnostics({}, {})
    assert result["azure_log_poll_attempts"] == 2
    assert polls == [1, 10, 1]


def test_deleted_gcp_identity_pool_is_tombstone_not_active(monkeypatch):
    monkeypatch.setattr(directed.azure, "inventory", lambda *_: {"resource_groups": 0})
    monkeypatch.setattr(directed.gcp, "inventory", lambda *_: {"services": 0})
    monkeypatch.setattr(directed.azure, "credential", lambda *_: SimpleNamespace(
        get_token=lambda *_: SimpleNamespace(token="test")))
    def graph(*_args, **_kwargs):
        return SimpleNamespace(status_code=200, json=lambda: {"value": []})
    monkeypatch.setattr(directed.requests, "get", graph)
    monkeypatch.setattr(directed.gcp, "client", lambda *_: SimpleNamespace(
        get=lambda *_args, **_kwargs: SimpleNamespace(status_code=200,
                                                     json=lambda: {"state": "DELETED"})))
    result = directed.inventory({"gcp_project_id": "test-project"}, "corez2g-12345678")
    assert result["gcp:workload_identity_pools"] == 0
    assert result["pending_deletion:gcp:workload_identity_pools"] == 1
