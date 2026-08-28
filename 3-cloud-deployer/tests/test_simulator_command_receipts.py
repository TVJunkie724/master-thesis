"""Offline receipt-evidence tests for provider device simulators."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

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
