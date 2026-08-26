"""Contract tests for the bounded GCP Six-layer MQTT edge."""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "gcp"
    / "containers"
    / "six-layer-domain"
    / "platform"
    / "mqtt_adapter.py"
)


def _load():
    """Load the adapter without requiring paho in the deployer test image."""

    client_module = ModuleType("paho.mqtt.client")
    client_module.Client = object
    client_module.CallbackAPIVersion = SimpleNamespace(VERSION2=2)
    client_module.MQTTv311 = 4
    client_module.MQTT_ERR_SUCCESS = 0
    mqtt_module = ModuleType("paho.mqtt")
    mqtt_module.client = client_module
    paho_module = ModuleType("paho")
    paho_module.mqtt = mqtt_module
    previous = {
        name: sys.modules.get(name)
        for name in ("paho", "paho.mqtt", "paho.mqtt.client")
    }
    sys.modules.update(
        {
            "paho": paho_module,
            "paho.mqtt": mqtt_module,
            "paho.mqtt.client": client_module,
        }
    )
    try:
        spec = importlib.util.spec_from_file_location(
            "gcp_six_layer_mqtt_adapter", SOURCE
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


@pytest.fixture()
def adapter(monkeypatch):
    module = _load()
    for name, value in {
        "BIFROMQ_TENANT_ID": "deployment-1",
        "BIFROMQ_DEVICE_USERNAME": "device-user",
        "BIFROMQ_DEVICE_PASSWORD": "device-secret",
        "BIFROMQ_BRIDGE_USERNAME": "bridge-user",
        "BIFROMQ_BRIDGE_PASSWORD": "bridge-secret",
    }.items():
        monkeypatch.setenv(name, value)
    return module


def _encoded(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def test_authentication_accepts_only_generated_device_and_bridge_credentials(adapter):
    client = adapter.app.test_client()

    device = client.post(
        "/auth",
        json={"username": "device-user", "password": _encoded("device-secret")},
    )
    bridge = client.post(
        "/auth",
        json={"username": "bridge-user", "password": _encoded("bridge-secret")},
    )
    rejected = client.post(
        "/auth",
        json={"username": "device-user", "password": _encoded("wrong")},
    )

    assert device.json["ok"]["tenantId"] == "deployment-1"
    assert device.json["ok"]["attrs"]["role"] == "device"
    assert bridge.json["ok"]["attrs"]["role"] == "bridge"
    assert rejected.json["reject"]["code"] == "BadPass"


@pytest.mark.parametrize(
    ("user_id", "action", "topic", "allowed"),
    (
        ("device-user", "pub", "devices/device-1/telemetry", True),
        ("device-user", "sub", "devices/device-1/commands", True),
        ("device-user", "sub", "devices/+/commands", False),
        ("device-user", "pub", "devices/device-1/commands", False),
        (
            "bridge-user",
            "sub",
            "$share/twin2multicloud/devices/+/telemetry",
            True,
        ),
        ("bridge-user", "pub", "devices/device-1/commands", True),
        ("bridge-user", "pub", "devices/device-1/telemetry", False),
    ),
)
def test_authorization_closes_topic_directions(
    adapter, user_id, action, topic, allowed
):
    client = adapter.app.test_client()
    key = "topic" if action == "pub" else "topicFilter"

    response = client.post(
        "/check",
        json={action: {key: topic}},
        headers={"user_id": user_id},
    )

    assert response.text == str(allowed).lower()


def test_telemetry_is_bound_to_topic_device_and_authenticated_ingress(
    adapter, monkeypatch
):
    calls = []

    class Response:
        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setenv("INGRESS_URL", "https://ingress.example")
    monkeypatch.setattr(adapter, "_ingress_token", lambda target: f"token:{target}")
    monkeypatch.setattr(
        adapter.requests,
        "post",
        lambda target, **kwargs: calls.append((target, kwargs)) or Response(),
    )

    adapter._forward_telemetry(
        "devices/device-1/telemetry",
        json.dumps({"metric": "temperature", "value": 21.5}).encode(),
    )

    assert calls == [
        (
            "https://ingress.example",
            {
                "json": {
                    "device_id": "device-1",
                    "metric": "temperature",
                    "value": 21.5,
                },
                "headers": {"Authorization": "Bearer token:https://ingress.example"},
                "timeout": 15,
            },
        )
    ]
    with pytest.raises(ValueError, match="does not match"):
        adapter._forward_telemetry(
            "devices/device-1/telemetry",
            json.dumps({"device_id": "device-2", "value": 21.5}).encode(),
        )


def test_telemetry_rejects_payload_above_frozen_96_kib_limit(adapter):
    with pytest.raises(ValueError, match="canonical limit"):
        adapter._forward_telemetry(
            "devices/device-1/telemetry",
            b"x" * (96 * 1024 + 1),
        )


class _Message:
    def __init__(self, value):
        self.data = json.dumps(value).encode("utf-8")
        self.acked = False
        self.nacked = False

    def ack(self):
        self.acked = True

    def nack(self):
        self.nacked = True


def test_command_acknowledges_only_after_qos_one_publish(adapter, monkeypatch):
    published = []
    outcomes = []

    class Publication:
        @staticmethod
        def wait_for_publish(timeout):
            assert timeout == 15

        @staticmethod
        def is_published():
            return True

    class Client:
        @staticmethod
        def is_connected():
            return True

        @staticmethod
        def publish(topic, **kwargs):
            published.append((topic, kwargs))
            return Publication()

    adapter._mqtt_client = Client()
    monkeypatch.setattr(
        adapter,
        "_record_command_outcome",
        lambda value, status: outcomes.append((value, status)),
    )
    event = {
        "event_type": "device.command.requested.v1",
        "payload": {"device_id": "device-1", "command": "cool-down"},
    }
    message = _Message(event)

    adapter._command_callback(message)

    assert message.acked is True
    assert message.nacked is False
    assert published[0][0] == "devices/device-1/commands"
    assert published[0][1]["qos"] == 1
    assert outcomes == [(event, "ACCEPTED")]


def test_command_nacks_transient_delivery_failure_but_acks_invalid_event(adapter):
    adapter._mqtt_client = None
    valid = _Message(
        {
            "event_type": "device.command.requested.v1",
            "payload": {"device_id": "device-1"},
        }
    )
    invalid = _Message({"event_type": "unreviewed.v1", "payload": {}})

    adapter._command_callback(valid)
    adapter._command_callback(invalid)

    assert valid.nacked is True and valid.acked is False
    assert invalid.acked is True and invalid.nacked is False


def test_command_records_failed_outcome_only_after_final_delivery_attempt(
    adapter, monkeypatch
):
    outcomes = []
    adapter._mqtt_client = None
    monkeypatch.setattr(
        adapter,
        "_record_command_outcome",
        lambda value, status: outcomes.append((value, status)),
    )
    event = {
        "event_type": "device.command.requested.v1",
        "payload": {"device_id": "device-1"},
    }
    message = _Message(event)
    message.delivery_attempt = 5

    adapter._command_callback(message)

    assert message.acked is True and message.nacked is False
    assert outcomes == [(event, "FAILED")]
