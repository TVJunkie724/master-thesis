"""
IoT Device Simulator - MQTT Transmission.

This module handles MQTT communication with AWS IoT Core,
sending test payloads from the configured payloads.json file.

Migration Status:
    - Uses globals for device certificates and endpoint config.
    - This is a standalone utility - no migration needed.
"""

if __package__:
    from . import globals
else:  # Standalone package executes this module directly.
    import globals
import os
import json
import re
import threading
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from datetime import datetime, timezone


payload_index = 0
_COMMAND_TOPIC = re.compile(
    r"^\$aws/commands/things/(?P<target>[A-Za-z0-9._:-]{1,128})/"
    r"executions/(?P<execution>[A-Za-z0-9._:-]{1,128})/request/json$"
)
_TRACE_ID = re.compile(r"^(?:TRACE|VERIFY)-[A-Z0-9]{8,48}$")


def _trace_id(value):
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


def _checkpoint(stage, trace_id, event_id):
    if trace_id is None:
        return
    print(
        "T2MC_CHECKPOINT "
        + json.dumps(
            {
                "schema_version": "diagnostic-checkpoint.v1",
                "trace_id": trace_id,
                "stage": stage,
                "provider": "aws",
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


def load_config_for_device(device_id: str) -> dict:
    """
    Load device-specific config for standalone multi-device mode.
    
    Resolves either integrated generated configs or standalone package configs.
    Unknown device identities fail closed instead of reusing default credentials.
    """
    if not device_id:
        return dict(globals.config)
    
    device_config_path = globals.get_device_config_path(device_id)
    if os.path.exists(device_config_path):
        with open(device_config_path, 'r') as f:
            config_data = json.load(f)
        
        # Resolve paths relative to device config directory
        config_dir = os.path.dirname(device_config_path)
        def resolve(path):
            if os.path.isabs(path):
                return path
            return os.path.normpath(os.path.join(config_dir, path))
        
        return {
            "endpoint": config_data["endpoint"],
            "topic": config_data["topic"],
            "command_target_id": config_data["command_target_id"],
            "command_topic_filter": config_data["command_topic_filter"],
            "device_id": config_data["device_id"],
            "cert_path": resolve(config_data["cert_path"]),
            "key_path": resolve(config_data["key_path"]),
            "root_ca_path": resolve(config_data["root_ca_path"]),
            "payload_path": resolve(config_data.get("payload_path", "../payloads.json"))
        }
    
    raise ValueError(f"No simulator configuration found for device '{device_id}'")


def send_mqtt(payload, device_config=None):
    """Send a single payload via MQTT.
    
    Args:
        payload: The payload dict to send
        device_config: Optional device-specific config. If None, uses globals.config.
    """
    # Get config - either device-specific or global
    if device_config is None:
        # Check if payload has iotDeviceId and we're in standalone mode
        payload_device_id = payload.get("iotDeviceId")
        device_config = globals.config
        if payload_device_id and payload_device_id != globals.config["device_id"]:
            device_config = load_config_for_device(payload_device_id)
    
    iot_device_id = device_config["device_id"]
    
    # Info message about device routing
    payload_device_id = payload.get("iotDeviceId")
    if payload_device_id and payload_device_id != iot_device_id:
        print(f"INFO: Routing payload for '{payload_device_id}' via device '{iot_device_id}'")

    client = AWSIoTMQTTClient(iot_device_id)
    client.configureEndpoint(device_config["endpoint"], 8883)
    client.configureCredentials(device_config["root_ca_path"], device_config["key_path"], device_config["cert_path"])

    topic = device_config["topic"]

    client.connect()
    client.publish(topic, json.dumps(payload), 1)
    client.disconnect()

    _checkpoint("simulator_sent", _trace_id(payload), payload.get("event_id"))
    print(f"Message sent! Device: {iot_device_id}, Topic: {topic}")


def listen_for_command(timeout_seconds=300):
    """Wait for one AWS IoT Command, acknowledge it, and emit receipt evidence."""
    device_config = globals.config
    received = threading.Event()
    client = AWSIoTMQTTClient(device_config["device_id"])
    client.configureEndpoint(device_config["endpoint"], 8883)
    client.configureCredentials(
        device_config["root_ca_path"],
        device_config["key_path"],
        device_config["cert_path"],
    )

    def on_command(active_client, _userdata, message):
        matched = _COMMAND_TOPIC.fullmatch(message.topic)
        if matched is None or matched.group("target") != device_config["command_target_id"]:
            return
        execution_id = matched.group("execution")
        try:
            value = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = {}
        _checkpoint(
            "simulator_command_received",
            _trace_id(value),
            execution_id,
        )
        response_topic = (
            f"$aws/commands/things/{device_config['command_target_id']}/"
            f"executions/{execution_id}/response/json"
        )
        active_client.publish(
            response_topic,
            json.dumps(
                {
                    "deviceId": device_config["command_target_id"],
                    "executionId": execution_id,
                    "status": "SUCCEEDED",
                    "statusReason": {
                        "reasonCode": "SIMULATOR_RECEIVED",
                        "reasonDescription": "PoC simulator received the command",
                    },
                    "result": {"receipt": {"s": "simulator received command"}},
                },
                separators=(",", ":"),
            ),
            1,
        )
        received.set()

    client.connect()
    try:
        client.subscribe(device_config["command_topic_filter"], 1, on_command)
        return received.wait(timeout_seconds)
    finally:
        client.disconnect()


def send():
  global payload_index

  payloads_path = globals.config["payload_path"]

  with open(payloads_path, "r", encoding="utf-8") as f:
    payloads = json.load(f)

  if payload_index >= len(payloads):
    payload_index = 0

  payload = payloads[payload_index]
  payload_index += 1

  if "time" not in payload or payload["time"] == "":
    payload["time"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

  send_mqtt(payload)
