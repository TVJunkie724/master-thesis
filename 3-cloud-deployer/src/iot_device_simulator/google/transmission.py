"""GCP Six-layer device transmission through the authenticated BifroMQ edge."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import threading

from . import globals


payload_index = 0
_COMMAND_TOPIC = re.compile(
    r"^devices/(?P<device_id>[A-Za-z0-9][A-Za-z0-9._-]{0,127})/commands$"
)
_TRACE_ID = re.compile(r"^(?:TRACE|VERIFY)-[A-Z0-9]{8,48}$")


def _trace_id(value: dict | None) -> str | None:
    if not isinstance(value, dict):
        return None
    candidates = (value.get("trace_id"), value.get("source_sequence"))
    return next(
        (
            candidate
            for candidate in candidates
            if isinstance(candidate, str) and _TRACE_ID.fullmatch(candidate)
        ),
        None,
    )


def _checkpoint(stage: str, trace_id: str | None, event_id: str | None) -> None:
    if trace_id is None:
        return
    print(
        "T2MC_CHECKPOINT "
        + json.dumps(
            {
                "schema_version": "diagnostic-checkpoint.v1",
                "trace_id": trace_id,
                "stage": stage,
                "provider": "gcp",
                "component": "simulator",
                "status": "passed",
                "observed_at": datetime.now(timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                ),
                "event_id": event_id or trace_id,
                "event_type": "device.command.requested.v1"
                if stage == "simulator_command_received"
                else "telemetry.received.v1",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _resolved_config(config_data: dict, config_dir: str) -> dict:
    def resolve(path: str) -> str:
        return (
            path
            if os.path.isabs(path)
            else os.path.normpath(os.path.join(config_dir, path))
        )

    return {
        "endpoint": config_data["endpoint"],
        "port": int(config_data.get("port", 8883)),
        "device_id": config_data["device_id"],
        "digital_twin_name": config_data.get("digital_twin_name", ""),
        "username": config_data["username"],
        "password": config_data["password"],
        "telemetry_topic": config_data["telemetry_topic"],
        "command_topic": config_data["command_topic"],
        "server_ca_path": resolve(
            config_data.get("server_ca_path", "server-ca.pem")
        ),
        "payload_path": resolve(config_data.get("payload_path", "../payloads.json")),
    }


def load_config_for_device(device_id: str) -> dict:
    """Load exact per-device MQTT metadata; unknown identities fail closed."""
    device_config_path = globals.get_device_config_path(device_id)
    if not os.path.exists(device_config_path):
        raise ValueError(f"No simulator configuration found for device '{device_id}'")
    with open(device_config_path, encoding="utf-8") as handle:
        return _resolved_config(json.load(handle), os.path.dirname(device_config_path))


def _active_config(payload: dict | None = None) -> dict:
    current = {
        "endpoint": globals.config.endpoint,
        "port": globals.config.port,
        "device_id": globals.config.device_id,
        "digital_twin_name": globals.config.digital_twin_name,
        "username": globals.config.username,
        "password": globals.config.password,
        "telemetry_topic": globals.config.telemetry_topic,
        "command_topic": globals.config.command_topic,
        "server_ca_path": globals.config.server_ca_path,
        "payload_path": globals.config.payload_path,
    }
    requested = payload.get("iotDeviceId") if payload else None
    if requested and requested != current["device_id"]:
        return load_config_for_device(requested)
    return current


def _client(device_config: dict, *, suffix: str):
    import paho.mqtt.client as mqtt

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"twin2multicloud-{device_config['device_id']}-{suffix}",
        clean_session=True,
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(device_config["username"], device_config["password"])
    client.tls_set(ca_certs=device_config["server_ca_path"])
    return client


def send_mqtt(payload: dict, device_config: dict | None = None) -> None:
    """Publish one QoS-1 telemetry payload through the deployed MQTT edge."""
    device_config = device_config or _active_config(payload)
    device_id = device_config["device_id"]
    supplied = payload.get("iotDeviceId") or payload.get("device_id")
    if supplied not in {None, device_id}:
        raise ValueError("Payload device identity does not match MQTT credentials")
    payload["iotDeviceId"] = device_id
    client = _client(device_config, suffix="telemetry")
    try:
        client.connect(device_config["endpoint"], device_config["port"], keepalive=60)
        client.loop_start()
        publication = client.publish(
            device_config["telemetry_topic"],
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            qos=1,
            retain=False,
        )
        publication.wait_for_publish(timeout=15)
        if not publication.is_published():
            raise RuntimeError("MQTT telemetry publish did not complete")
        _checkpoint("simulator_sent", _trace_id(payload), payload.get("event_id"))
    finally:
        client.loop_stop()
        client.disconnect()
    print(
        f"Message sent! Device: {device_id}, "
        f"Topic: {device_config['telemetry_topic']}"
    )


def listen_for_command(timeout_seconds: float = 300) -> bool:
    """Wait for one command and emit bounded local receipt evidence."""
    device_config = _active_config()
    received = threading.Event()
    client = _client(device_config, suffix="commands")

    def on_connect(active_client, _userdata, _flags, reason_code, _properties=None):
        if reason_code == 0:
            active_client.subscribe(device_config["command_topic"], qos=1)

    def on_message(_client, _userdata, message):
        matched = _COMMAND_TOPIC.fullmatch(message.topic)
        if matched is None or matched.group("device_id") != device_config["device_id"]:
            return
        value = json.loads(message.payload.decode("utf-8"))
        event_id = value.get("event_id") if isinstance(value, dict) else None
        _checkpoint(
            "simulator_command_received",
            _trace_id(value),
            event_id,
        )
        received.set()

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(device_config["endpoint"], device_config["port"], keepalive=60)
        client.loop_start()
        return received.wait(timeout_seconds)
    finally:
        client.loop_stop()
        client.disconnect()


def send() -> None:
    global payload_index
    with open(globals.config.payload_path, encoding="utf-8") as handle:
        payloads = json.load(handle)
    if not payloads:
        print("No payloads found in payloads.json")
        return
    if payload_index >= len(payloads):
        payload_index = 0
    payload = payloads[payload_index].copy()
    payload_index += 1
    if not payload.get("time"):
        payload["time"] = datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
    send_mqtt(payload)
