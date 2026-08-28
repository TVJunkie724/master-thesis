"""Offline contract tests for the GCP Six-layer MQTT simulator."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.iot_device_simulator.google import globals, transmission


def _config(tmp_path):
    runtime = tmp_path / "_runtime"
    runtime.mkdir()
    (runtime / "server-ca.pem").write_text("certificate", encoding="utf-8")
    payloads = tmp_path / "payloads.json"
    payloads.write_text('[{"iotDeviceId":"device-1","value":21}]', encoding="utf-8")
    device = tmp_path / "device-1"
    device.mkdir()
    config = device / "config_generated.json"
    config.write_text(
        json.dumps(
            {
                "endpoint": "203.0.113.10",
                "port": 8883,
                "device_id": "device-1",
                "username": "device-user",
                "password": "device-secret",
                "telemetry_topic": "devices/device-1/telemetry",
                "command_topic": "devices/device-1/commands",
                "server_ca_path": "../_runtime/server-ca.pem",
                "payload_path": "../payloads.json",
            }
        ),
        encoding="utf-8",
    )
    globals.load_config(str(config))
    return config


def test_load_config_resolves_mqtt_files_relative_to_device_config(tmp_path):
    config = _config(tmp_path)

    assert globals.config.endpoint == "203.0.113.10"
    assert globals.config.port == 8883
    assert globals.config.telemetry_topic == "devices/device-1/telemetry"
    assert globals.config.command_topic == "devices/device-1/commands"
    assert globals.config.server_ca_path == str(
        (config.parent / "../_runtime/server-ca.pem").resolve()
    )


def test_send_mqtt_uses_authenticated_tls_qos_one_edge(tmp_path, monkeypatch):
    _config(tmp_path)
    publication = MagicMock()
    publication.is_published.return_value = True
    client = MagicMock()
    client.publish.return_value = publication
    monkeypatch.setattr(transmission, "_client", lambda *_args, **_kwargs: client)

    transmission.send_mqtt({"iotDeviceId": "device-1", "value": 21})

    client.connect.assert_called_once_with("203.0.113.10", 8883, keepalive=60)
    call = client.publish.call_args
    assert call.args[0] == "devices/device-1/telemetry"
    assert json.loads(call.args[1]) == {"iotDeviceId": "device-1", "value": 21}
    assert call.kwargs == {"qos": 1, "retain": False}
    publication.wait_for_publish.assert_called_once_with(timeout=15)


def test_send_mqtt_rejects_payload_for_another_device(tmp_path, monkeypatch):
    _config(tmp_path)
    monkeypatch.setattr(
        globals,
        "get_device_config_path",
        lambda _device_id: str(tmp_path / "missing"),
    )

    with pytest.raises(ValueError, match="No simulator configuration"):
        transmission.send_mqtt({"iotDeviceId": "other-device", "value": 21})


def test_command_listener_emits_device_receipt_checkpoint(tmp_path, monkeypatch, capsys):
    _config(tmp_path)
    client = MagicMock()

    def loop_start():
        client.on_connect(client, None, None, 0)
        client.on_message(
            client,
            None,
            SimpleNamespace(
                topic="devices/device-1/commands",
                payload=json.dumps(
                    {"event_id": "event-1", "trace_id": "TRACE-ABCDEF12"}
                ).encode("utf-8"),
            ),
        )

    client.loop_start.side_effect = loop_start
    monkeypatch.setattr(transmission, "_client", lambda *_args, **_kwargs: client)

    assert transmission.listen_for_command(timeout_seconds=0.1) is True

    output = capsys.readouterr().out
    assert "T2MC_CHECKPOINT" in output
    assert '"stage":"simulator_command_received"' in output
    assert '"event_id":"event-1"' in output
    assert '"trace_id":"TRACE-ABCDEF12"' in output
    client.subscribe.assert_called_once_with("devices/device-1/commands", qos=1)
