"""Offline receipt-evidence tests for provider device simulators."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from src.iot_device_simulator.aws import globals as aws_globals
from src.iot_device_simulator.aws import transmission as aws_transmission
from src.iot_device_simulator.azure import globals as azure_globals
from src.iot_device_simulator.azure import transmission as azure_transmission


def test_aws_command_listener_acknowledges_execution_and_emits_checkpoint(
    monkeypatch, capsys
):
    aws_globals.config.clear()
    aws_globals.config.update(
        {
            "endpoint": "endpoint.iot.eu-central-1.amazonaws.com",
            "device_id": "device-1",
            "command_target_id": "factory-device-1",
            "command_topic_filter": (
                "$aws/commands/things/factory-device-1/"
                "executions/+/request/json"
            ),
            "root_ca_path": "root.pem",
            "key_path": "private.pem",
            "cert_path": "certificate.pem",
        }
    )
    client = MagicMock()

    def subscribe(_topic, _qos, callback):
        callback(
            client,
            None,
            SimpleNamespace(
                topic=(
                    "$aws/commands/things/factory-device-1/"
                    "executions/execution-1/request/json"
                ),
                payload=b'{"trace_id":"TRACE-ABCDEF12"}',
            ),
        )

    client.subscribe.side_effect = subscribe
    monkeypatch.setattr(aws_transmission, "AWSIoTMQTTClient", lambda _id: client)

    assert aws_transmission.listen_for_command(timeout_seconds=0.1) is True

    output = capsys.readouterr().out
    assert "T2MC_CHECKPOINT" in output
    assert '"stage":"simulator_command_received"' in output
    assert '"trace_id":"TRACE-ABCDEF12"' in output
    assert '"event_id":"execution-1"' in output
    response = client.publish.call_args
    assert response.args[0].endswith("/executions/execution-1/response/json")
    assert json.loads(response.args[1])["status"] == "SUCCEEDED"


def test_azure_command_listener_emits_message_id_checkpoint(monkeypatch, capsys):
    azure_globals.config.clear()
    azure_globals.config.update(
        {
            "connection_string": "not-used-by-mock",
            "device_id": "device-1",
        }
    )
    client = MagicMock()

    def connect():
        client.on_message_received(
            SimpleNamespace(
                message_id="event-1",
                data=b'{"message":"cool-down","trace_id":"TRACE-ABCDEF12"}',
            )
        )

    client.connect.side_effect = connect
    monkeypatch.setattr(azure_transmission, "_get_client", lambda _config: client)

    assert azure_transmission.listen_for_command(timeout_seconds=0.1) is True

    output = capsys.readouterr().out
    assert "T2MC_CHECKPOINT" in output
    assert '"stage":"simulator_command_received"' in output
    assert '"event_id":"event-1"' in output
    assert '"trace_id":"TRACE-ABCDEF12"' in output
    client.disconnect.assert_called_once_with()


@pytest.mark.parametrize("provider", ["aws", "azure"])
@pytest.mark.parametrize("matching", [False, True])
def test_combined_roundtrip_reuses_connection_and_requires_trace(provider, matching, monkeypatch, capsys):
    runtime = aws_transmission if provider == "aws" else azure_transmission
    config = aws_globals.config if provider == "aws" else azure_globals.config
    monkeypatch.setattr(runtime.globals, "config", dict(config, device_id="device-1",
        endpoint="offline.example", command_target_id="factory-device-1",
        command_topic_filter="commands", topic="telemetry", root_ca_path="root",
        key_path="key", cert_path="cert"))
    client = MagicMock()
    factory = MagicMock(return_value=client)
    callbacks = []
    def receive():
        trace = "TRACE-ABCDEF12" if matching else "TRACE-WRONG123"
        if provider == "aws":
            callbacks[0](client, None, SimpleNamespace(
                topic="$aws/commands/things/factory-device-1/executions/one/request/json",
                payload=json.dumps({"trace_id": trace}).encode()))
        else:
            client.on_message_received(SimpleNamespace(message_id="one",
                data=json.dumps({"trace_id": trace}).encode()))
    if provider == "aws":
        monkeypatch.setattr(runtime, "AWSIoTMQTTClient", factory)
        client.subscribe.side_effect = lambda _topic, _qos, callback: callbacks.append(callback)
        client.publish.side_effect = lambda topic, *_: receive() if topic == "telemetry" else None
    else:
        monkeypatch.setattr(runtime, "_get_client", factory)
        monkeypatch.setattr(runtime, "Message", lambda payload: SimpleNamespace(data=payload))
        client.send_message.side_effect = lambda _: receive()
    result = runtime.listen_for_command(timeout_seconds=0.001, telemetry_payload={
        "device_id": "device-1", "trace_id": "TRACE-ABCDEF12", "value": 21,
    })
    assert result is matching
    factory.assert_called_once()
    client.connect.assert_called_once()
    client.disconnect.assert_called_once()
    output = capsys.readouterr().out
    assert '"stage":"simulator_sent"' in output
    assert ('"stage":"simulator_command_received"' in output) is matching
    assert "TRACE-WRONG123" not in output


@pytest.mark.parametrize("runtime", [aws_transmission, azure_transmission])
@pytest.mark.parametrize("payload", [{"value": 21}, {"trace_id": "TRACE-ABCDEF12", "device_id": "other"}])
def test_combined_roundtrip_rejects_uncorrelated_or_foreign_payload(runtime, payload, monkeypatch):
    monkeypatch.setattr(runtime.globals, "config", {"device_id": "device-1"})
    with pytest.raises(ValueError, match="valid trace and matching device"):
        runtime.listen_for_command(telemetry_payload=payload)
