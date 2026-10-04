from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import core_command_receipt as check
from scripts import core_live_azure_roundtrip, core_live_gcp_roundtrip


@pytest.mark.parametrize("case", ["pass", "missing", "unrelated", "negative", "timeout"])
def test_receipt_is_correlated_private_and_restores_configuration(case, tmp_path):
    original = object()
    runtime = SimpleNamespace(globals=SimpleNamespace(config=original))
    def listen(timeout, *, telemetry_payload):
        assert timeout == 300
        stamp = datetime.now(timezone.utc)
        for stage, delta in [("simulator_sent", 0), ("simulator_command_received", -1 if case == "negative" else 1)]:
            if case == "missing" and delta:
                continue
            print("T2MC_CHECKPOINT " + json.dumps({"stage": stage,
                "trace_id": "TRACE-UNRELATED" if case == "unrelated" else telemetry_payload["source_sequence"],
                "observed_at": (stamp + timedelta(seconds=delta)).isoformat()}))
        return case != "timeout"
    runtime.listen_for_command = listen
    if case == "pass":
        _, result = check.exercise(runtime, {}, {"project_path": str(tmp_path)})
        assert result["command_received"] == 1
        assert result["roundtrip_seconds"] == 1
    else:
        with pytest.raises(RuntimeError, match="COMMAND_"):
            check.exercise(runtime, {}, {"project_path": str(tmp_path)})
    assert runtime.globals.config is original
    assert (tmp_path / "simulator.log").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("matching", [True, False])
def test_history_requires_exact_timestamp_and_value(monkeypatch, matching):
    now = datetime.now(timezone.utc)
    read = Mock(return_value=[{"value": 42, "event_time": (now + timedelta(seconds=not matching)).isoformat()}])
    monkeypatch.setattr(check.time, "sleep", lambda _: None)
    if matching:
        assert check.confirm_history(read, now, {})["read_back"] == 1
    else:
        with pytest.raises(RuntimeError, match="READBACK_TIMEOUT"):
            check.confirm_history(read, now, {})
        assert read.call_count == 60


@pytest.mark.parametrize("provider", [core_live_azure_roundtrip, core_live_gcp_roundtrip])
def test_wrappers_keep_core_inventory_and_one_feedback_rule(provider, tmp_path):
    values = {}
    provider.configure(values, tmp_path)
    assert len(values["events"]) == 1
    assert values["events"][0]["action"]["feedback"]["device_id"] == check.DEVICE
    assert provider.inventory is provider.core.inventory
    assert provider.stop_builds is provider.core.stop_builds


@pytest.mark.parametrize("provider", [core_live_azure_roundtrip, core_live_gcp_roundtrip])
@pytest.mark.parametrize("status", [200, 403])
def test_provider_smoke_uses_real_simulator_and_authenticated_reader(provider, status, monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    values = {"project_path": str(tmp_path), "digital_twin_name": "fixture", "azure_subscription_id": "subscription",
              "gcp_credentials_json": "{}"}
    seen = []
    def exercise(runtime, config, _values):
        seen.append((runtime, config))
        return now, {"command_received": 1}
    monkeypatch.setattr(provider, "exercise", exercise)
    response = SimpleNamespace(status_code=status, json=lambda: {"points": [{"value": 42, "event_time": now.isoformat()}]})
    request = Mock(return_value=response)
    monkeypatch.setattr(provider.core.requests, "get", request)
    if provider is core_live_azure_roundtrip:
        monkeypatch.setattr(provider.core, "register_simulator", lambda *_: ("hub.test", "test-key"))
        monkeypatch.setattr(provider.core, "arm", Mock(side_effect=[
            {"value": [{"name": "reader", "id": "/test/reader"}]}, {"functionKeys": {"default": "reader-key"}}]))
        outputs = {"azure_six_layer_resource_group_name": "group",
                   "azure_component_storage_read_access_output": {"reader_function_name": "reader", "access_url": "https://test/reader"}}
    else:
        token = SimpleNamespace(token="test-token", refresh=Mock())
        monkeypatch.setattr(provider.core.service_account.IDTokenCredentials, "from_service_account_info", Mock(return_value=token))
        outputs = {"gcp_six_layer_mqtt_endpoint": "mqtts://test:8883",
                   "gcp_six_layer_mqtt_device_credentials": {"username": "device", "password": "test-password"},
                   "gcp_six_layer_mqtt_server_certificate": "test-certificate",
                   "gcp_component_storage_read_access_output": {"access_url": "https://test/raw-history/query"}}
    if status == 200:
        assert provider.smoke(values, outputs)["read_back"] == 1
    else:
        with pytest.raises(RuntimeError, match="UNAUTHORIZED"):
            provider.smoke(values, outputs)
    assert len(seen) == 1
    assert seen[0][0].__name__.endswith("transmission")
    assert request.call_args.kwargs["headers"]
