"""GCP delivery runtime for the independent Six-layer Event Layer.

Small and Medium subscriptions use authenticated Pub/Sub push requests. Large
telemetry subscriptions use one fixed Cloud Run worker pool per independent
consumer, while low-rate control remains on the same authenticated HTTP path.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Mapping

from flask import Flask, jsonify, request
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import pubsub_v1
from google.oauth2 import id_token
import requests


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = "canonical-domain-event.v1"
TELEMETRY_RECEIVED = "telemetry.received.v1"
TELEMETRY_PROCESSED = "telemetry.processed.v1"
TWIN_EVENT_TYPES = {
    "twin.state.upserted",
    "twin.model.upserted",
    "twin.relationship.upserted",
    "twin.relationship.deleted",
}
SUPPORTED_EVENT_TYPES = {
    TELEMETRY_RECEIVED,
    TELEMETRY_PROCESSED,
    "event.matched.v1",
    "notification.requested.v1",
    "extension.action.outcome.v1",
    "notification.workflow.outcome.v1",
    "device.command.requested.v1",
    "device.command.outcome.v1",
    *TWIN_EVENT_TYPES,
}
REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "event_type",
    "deployment_id",
    "source_id",
    "source_sequence",
    "occurred_at",
    "correlation_id",
    "causation_id",
    "producer",
    "payload",
}
CONSUMER_ROLES = {
    "telemetry-processor",
    "historical-persistence",
    "twin-state-update",
    "rule-evaluator",
    "audit",
    "realtime-visualization",
    "control-router",
}
PROCESSED_ROLES = {
    "historical-persistence",
    "twin-state-update",
    "rule-evaluator",
    "audit",
    "realtime-visualization",
}
MAX_EVENT_BYTES = 96 * 1024
MAX_RESPONSE_BYTES = 4096


class DeliveryError(ValueError):
    """Stable payload-free delivery failure."""


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _required_environment(name: str, *, maximum_bytes: int = 128 * 1024) -> str:
    value = os.environ.get(name, "")
    if not value or len(value.encode("utf-8")) > maximum_bytes:
        raise DeliveryError("EVENT_RUNTIME_NOT_CONFIGURED")
    return value


def _validate_event(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DeliveryError("INVALID_CANONICAL_EVENT")
    event = dict(value)
    if set(event) != REQUIRED_FIELDS or event.get("schema_version") != SCHEMA_VERSION:
        raise DeliveryError("INVALID_CANONICAL_EVENT")
    if event.get("event_type") not in SUPPORTED_EVENT_TYPES:
        raise DeliveryError("UNSUPPORTED_EVENT_TYPE")
    for field in REQUIRED_FIELDS - {"payload"}:
        if not isinstance(event.get(field), str) or not event[field]:
            raise DeliveryError("INVALID_CANONICAL_EVENT")
    if not isinstance(event.get("payload"), Mapping):
        raise DeliveryError("INVALID_CANONICAL_EVENT")
    if len(_canonical_bytes(event)) > MAX_EVENT_BYTES:
        raise DeliveryError("INVALID_CANONICAL_EVENT")
    return event


def _decode_json(raw: bytes) -> dict[str, Any]:
    if not raw or len(raw) > MAX_EVENT_BYTES:
        raise DeliveryError("INVALID_SOURCE_RECORD")
    try:
        return _validate_event(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeliveryError("INVALID_SOURCE_RECORD") from exc


def _decode_push(body: object) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        raise DeliveryError("INVALID_SOURCE_RECORD")
    message = body.get("message")
    encoded = message.get("data") if isinstance(message, Mapping) else None
    if not isinstance(encoded, str):
        raise DeliveryError("INVALID_SOURCE_RECORD")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (TypeError, ValueError) as exc:
        raise DeliveryError("INVALID_SOURCE_RECORD") from exc
    return _decode_json(raw)


def _validate_channel(event: Mapping[str, Any], role: str) -> None:
    event_type = event["event_type"]
    if role == "telemetry-processor" and event_type != TELEMETRY_RECEIVED:
        raise DeliveryError("EVENT_CHANNEL_MISMATCH")
    if role in PROCESSED_ROLES and event_type != TELEMETRY_PROCESSED:
        raise DeliveryError("EVENT_CHANNEL_MISMATCH")
    if role == "control-router" and event_type in {
        TELEMETRY_RECEIVED,
        TELEMETRY_PROCESSED,
    }:
        raise DeliveryError("EVENT_CHANNEL_MISMATCH")


def _targets() -> dict[str, str]:
    try:
        value = json.loads(_required_environment("EVENT_TARGETS_JSON"))
    except json.JSONDecodeError as exc:
        raise DeliveryError("EVENT_RUNTIME_NOT_CONFIGURED") from exc
    if not isinstance(value, dict) or any(
        not isinstance(key, str)
        or key not in CONSUMER_ROLES
        or not isinstance(target, str)
        or not target.startswith("https://")
        or len(target) > 2048
        for key, target in value.items()
    ):
        raise DeliveryError("EVENT_RUNTIME_NOT_CONFIGURED")
    return value


def _local_control_types() -> frozenset[str]:
    try:
        value = json.loads(_required_environment("EVENT_LOCAL_CONTROL_TYPES_JSON"))
    except json.JSONDecodeError as exc:
        raise DeliveryError("EVENT_RUNTIME_NOT_CONFIGURED") from exc
    if (
        not isinstance(value, list)
        or any(
            not isinstance(item, str) or item not in SUPPORTED_EVENT_TYPES
            for item in value
        )
        or len(value) != len(set(value))
    ):
        raise DeliveryError("EVENT_RUNTIME_NOT_CONFIGURED")
    return frozenset(value)


def _target_role(event: Mapping[str, Any], role: str) -> str:
    if role == "control-router" and event["event_type"] in TWIN_EVENT_TYPES:
        return "twin-state-update"
    return role


def _deliver(event: Mapping[str, Any], role: str) -> None:
    if role in {"audit", "realtime-visualization"}:
        # These Large-only consumers demonstrate independent fan-out without
        # adding another product subsystem to the thesis PoC.
        return
    if role == "control-router" and event["event_type"] not in _local_control_types():
        return
    target_role = _target_role(event, role)
    target = _targets().get(target_role)
    if not target:
        raise DeliveryError("EVENT_TARGET_NOT_CONFIGURED")
    try:
        token = id_token.fetch_id_token(GoogleAuthRequest(), target)
        response = requests.post(
            target,
            json={
                "eventing_delivery": {
                    "consumer_role": target_role,
                    "event": event,
                }
            },
            headers={"authorization": f"Bearer {token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise DeliveryError("DESTINATION_RETRYABLE_FAILURE") from exc
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise DeliveryError("DESTINATION_NOT_ACCEPTED")
    try:
        result = response.json()
    except requests.JSONDecodeError as exc:
        raise DeliveryError("DESTINATION_NOT_ACCEPTED") from exc
    if response.status_code != 202 or result != {
        "schema_version": "event-delivery-result.v1",
        "accepted": 1,
    }:
        raise DeliveryError("DESTINATION_NOT_ACCEPTED")


app = Flask(__name__)


@app.get("/healthz")
def healthz():
    return jsonify(
        {
            "status": "ok",
            "profile": "six-layer-eventing@1",
            "mode": "push",
        }
    )


@app.post("/deliver/<role>")
def push_delivery(role: str):
    try:
        if role not in CONSUMER_ROLES:
            raise DeliveryError("UNSUPPORTED_CONSUMER_ROLE")
        event = _decode_push(request.get_json(silent=True))
        _validate_channel(event, role)
        _deliver(event, role)
        return "", 204
    except DeliveryError as exc:
        LOGGER.warning("GCP Event Layer delivery failed: %s", exc)
        return jsonify({"error": {"code": str(exc)}}), 503
    except Exception:
        LOGGER.exception("GCP Event Layer retryable delivery failure")
        return jsonify({"error": {"code": "RUNTIME_RETRYABLE_FAILURE"}}), 503


def _streaming_pull_callback(message: object) -> None:
    role = _required_environment("EVENT_CONSUMER_ROLE", maximum_bytes=64)
    try:
        event = _decode_json(getattr(message, "data", b""))
        _validate_channel(event, role)
        _deliver(event, role)
        message.ack()
    except Exception:
        LOGGER.exception("GCP Event Layer StreamingPull delivery failed")
        message.nack()


def run_worker() -> None:
    subscription = _required_environment("EVENT_SUBSCRIPTION", maximum_bytes=2048)
    subscriber = pubsub_v1.SubscriberClient()
    future = subscriber.subscribe(
        subscription,
        callback=_streaming_pull_callback,
        flow_control=pubsub_v1.types.FlowControl(max_messages=1),
    )
    try:
        future.result()
    finally:
        future.cancel()
        subscriber.close()


if __name__ == "__main__":
    run_worker()
