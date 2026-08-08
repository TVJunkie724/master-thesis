"""Bounded authenticated MQTT-to-GCP bridge for the Five-layer v2 PoC.

The adapter deliberately owns only the protocol edge:

* BifroMQ delegates username/password authentication and topic authorization
  to the two small HTTP endpoints in this process.
* Telemetry is consumed with a shared QoS-1 subscription and forwarded to the
  authenticated Cloud Run ingress adapter. The Cloud Run runtime remains the
  sole canonical-event publisher.
* Device commands are pulled from the deployment Pub/Sub subscription and
  acknowledged only after a QoS-1 MQTT publish completes.

This is a deployment-scoped thesis boundary, not a general device registry.
All demo devices share one generated credential and remain isolated from the
separate bridge credential.
"""

from __future__ import annotations

import base64
import hmac
import json
import logging
import os
import re
import threading
import time
from typing import Any, Mapping

from flask import Flask, Response, jsonify, request
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import pubsub_v1
from google.oauth2 import id_token
import paho.mqtt.client as mqtt
import requests


LOGGER = logging.getLogger(__name__)
app = Flask(__name__)

MAX_PAYLOAD_BYTES = 96 * 1024
DEVICE_TOPIC = re.compile(r"^devices/(?P<device_id>[A-Za-z0-9._:-]{1,128})/telemetry$")
COMMAND_TOPIC = re.compile(r"^devices/(?P<device_id>[A-Za-z0-9._:-]{1,128})/commands$")
SHARED_TELEMETRY_FILTER = "$share/twin2multicloud/devices/+/telemetry"
AUTH_PROVIDER_SCHEMA = "bifromq-auth-webhook.v1"

_subscriber: pubsub_v1.SubscriberClient | None = None
_mqtt_client: mqtt.Client | None = None
_started = False
_start_lock = threading.Lock()


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Missing required runtime setting: {name}")
    return value


def _json_object(maximum_bytes: int = MAX_PAYLOAD_BYTES) -> dict[str, Any]:
    if request.content_length is not None and request.content_length > maximum_bytes:
        raise ValueError("request too large")
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _decode_password(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    try:
        return base64.b64decode(value, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return ""


def _credential_role(username: str, password: str) -> str | None:
    candidates = (
        (
            "device",
            os.environ.get("BIFROMQ_DEVICE_USERNAME", ""),
            os.environ.get("BIFROMQ_DEVICE_PASSWORD", ""),
        ),
        (
            "bridge",
            os.environ.get("BIFROMQ_BRIDGE_USERNAME", ""),
            os.environ.get("BIFROMQ_BRIDGE_PASSWORD", ""),
        ),
    )
    for role, expected_username, expected_password in candidates:
        if expected_username and expected_password and hmac.compare_digest(
            username, expected_username
        ) and hmac.compare_digest(password, expected_password):
            return role
    return None


@app.post("/auth")
def authenticate():
    """Implement BifroMQ's bundled demo AuthProvider webhook contract."""

    try:
        value = _json_object(16 * 1024)
    except ValueError:
        return jsonify({"reject": {"code": "Error", "reason": "invalid request"}})
    username = value.get("username")
    password = _decode_password(value.get("password"))
    role = _credential_role(username if isinstance(username, str) else "", password)
    if role is None:
        return jsonify({"reject": {"code": "BadPass", "reason": "invalid credential"}})
    return jsonify(
        {
            "ok": {
                "tenantId": _required_environment("BIFROMQ_TENANT_ID"),
                "userId": username,
                "attrs": {"role": role, "schema": AUTH_PROVIDER_SCHEMA},
            }
        }
    )


def _action_topic(value: Mapping[str, Any]) -> tuple[str, str] | None:
    for action in ("pub", "sub", "unsub"):
        body = value.get(action)
        if not isinstance(body, Mapping):
            continue
        key = "topic" if action == "pub" else "topicFilter"
        topic = body.get(key)
        if isinstance(topic, str):
            return action, topic
    if isinstance(value.get("conn"), Mapping):
        return "conn", ""
    return None


def _authorized(user_id: str, action: str, topic: str) -> bool:
    bridge_user = os.environ.get("BIFROMQ_BRIDGE_USERNAME", "")
    device_user = os.environ.get("BIFROMQ_DEVICE_USERNAME", "")
    if action == "conn":
        return user_id in {bridge_user, device_user}
    if user_id == bridge_user:
        return (
            action == "sub" and topic == SHARED_TELEMETRY_FILTER
        ) or (action == "pub" and COMMAND_TOPIC.fullmatch(topic) is not None)
    if user_id == device_user:
        return (
            action == "pub" and DEVICE_TOPIC.fullmatch(topic) is not None
        ) or (
            action in {"sub", "unsub"}
            and COMMAND_TOPIC.fullmatch(topic) is not None
        )
    return False


@app.post("/check")
def authorize():
    """Allow only the two PoC telemetry/command topic directions."""

    try:
        value = _json_object(16 * 1024)
    except ValueError:
        return Response("false", status=200, content_type="text/plain")
    parsed = _action_topic(value)
    user_id = request.headers.get("user_id", "")
    allowed = parsed is not None and _authorized(user_id, *parsed)
    return Response("true" if allowed else "false", status=200, content_type="text/plain")


@app.get("/healthz")
def health():
    return jsonify({"schema_version": "mqtt-adapter-health.v1", "ready": _started})


def _ingress_token(audience: str) -> str:
    return id_token.fetch_id_token(GoogleAuthRequest(), audience)


def _record_command_outcome(event: dict, status: str) -> None:
    target = _required_environment("INGRESS_URL")
    response = requests.post(
        target,
        json={
            "schema_version": "device-command-delivery.v1",
            "command": event,
            "status": status,
        },
        headers={"Authorization": f"Bearer {_ingress_token(target)}"},
        timeout=15,
    )
    response.raise_for_status()


def _forward_telemetry(topic: str, payload: bytes) -> None:
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("MQTT payload exceeds the canonical limit")
    matched = DEVICE_TOPIC.fullmatch(topic)
    if matched is None:
        raise ValueError("Unsupported telemetry topic")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Telemetry payload must be a JSON object")
    device_id = matched.group("device_id")
    supplied_device_id = value.get("device_id")
    if supplied_device_id not in {None, device_id}:
        raise ValueError("Telemetry device_id does not match its MQTT topic")
    value["device_id"] = device_id
    target = _required_environment("INGRESS_URL")
    response = requests.post(
        target,
        json=value,
        headers={"Authorization": f"Bearer {_ingress_token(target)}"},
        timeout=15,
    )
    response.raise_for_status()


def _on_connect(client, _userdata, _flags, reason_code, _properties=None):
    if reason_code != 0:
        LOGGER.error("MQTT bridge connection rejected with code %s", reason_code)
        return
    result, _mid = client.subscribe(SHARED_TELEMETRY_FILTER, qos=1)
    if result != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError("Could not subscribe the MQTT telemetry bridge")


def _on_message(client, _userdata, message):
    try:
        _forward_telemetry(message.topic, message.payload)
        client.ack(message.mid, message.qos)
    except Exception:
        LOGGER.exception("MQTT telemetry forwarding failed; reconnecting without ack")
        client.disconnect()


def _command_callback(message) -> None:
    value = None
    command_published = False
    try:
        value = json.loads(message.data.decode("utf-8"))
        if not isinstance(value, dict) or value.get("event_type") != "device.command.requested.v1":
            raise ValueError("Unsupported command event")
        payload = value.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("Command event payload is invalid")
        device_id = payload.get("device_id")
        if not isinstance(device_id, str) or DEVICE_TOPIC.fullmatch(
            f"devices/{device_id}/telemetry"
        ) is None:
            raise ValueError("Command device_id is invalid")
        client = _mqtt_client
        if client is None or not client.is_connected():
            raise RuntimeError("MQTT bridge is not connected")
        info = client.publish(
            f"devices/{device_id}/commands",
            payload=json.dumps(value, separators=(",", ":"), sort_keys=True),
            qos=1,
            retain=False,
        )
        info.wait_for_publish(timeout=15)
        if not info.is_published():
            raise RuntimeError("MQTT command publish did not complete")
        command_published = True
        _record_command_outcome(value, "ACCEPTED")
        message.ack()
    except ValueError:
        LOGGER.warning("Rejecting malformed command event")
        message.ack()
    except Exception:
        delivery_attempt = getattr(message, "delivery_attempt", 1) or 1
        if delivery_attempt >= 5 and not command_published and isinstance(value, dict):
            try:
                _record_command_outcome(value, "FAILED")
                message.ack()
                return
            except Exception:
                LOGGER.exception(
                    "Failed to persist final command outcome; requesting Pub/Sub redelivery"
                )
        LOGGER.exception("Command delivery failed; requesting Pub/Sub redelivery")
        message.nack()


def _run_bridge() -> None:
    global _mqtt_client, _subscriber, _started
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"twin2multicloud-adapter-{os.environ.get('HOSTNAME', 'poc')}",
        clean_session=False,
        protocol=mqtt.MQTTv311,
        manual_ack=True,
    )
    client.username_pw_set(
        _required_environment("BIFROMQ_BRIDGE_USERNAME"),
        _required_environment("BIFROMQ_BRIDGE_PASSWORD"),
    )
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(
        _required_environment("BIFROMQ_HOST"),
        int(os.environ.get("BIFROMQ_PORT", "1883")),
        keepalive=60,
    )
    client.loop_start()
    _mqtt_client = client

    subscriber = pubsub_v1.SubscriberClient()
    subscriber.subscribe(
        _required_environment("COMMAND_SUBSCRIPTION"),
        callback=_command_callback,
        flow_control=pubsub_v1.types.FlowControl(max_messages=100),
    )
    _subscriber = subscriber
    _started = True
    while True:
        time.sleep(60)


def start_bridge_once() -> None:
    global _started
    with _start_lock:
        if _started:
            return
        thread = threading.Thread(target=_run_bridge, name="mqtt-pubsub-bridge", daemon=True)
        thread.start()


if __name__ == "__main__":
    start_bridge_once()
    # Cloud Run requires the container listener on every interface.
    app.run(
        host="0.0.0.0",  # nosec B104
        port=int(os.environ.get("PORT", "8080")),
        threaded=True,
    )
