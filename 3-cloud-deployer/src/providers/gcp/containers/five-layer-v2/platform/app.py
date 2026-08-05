"""Role-selected Cloud Run HTTP runtime for GCP Five-layer v2."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Mapping

from flask import Flask, jsonify, request
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import firestore, pubsub_v1
from google.cloud.workflows import executions_v1
from google.oauth2 import id_token
import requests

import core


LOGGER = logging.getLogger(__name__)
app = Flask(__name__)

_firestore_client: firestore.Client | None = None
_publisher_client: pubsub_v1.PublisherClient | None = None
_executions_client: executions_v1.ExecutionsClient | None = None


def _database() -> firestore.Client:
    global _firestore_client
    if _firestore_client is None:
        database = os.environ.get("FIRESTORE_DATABASE", "")
        if not database:
            raise core.ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
        _firestore_client = firestore.Client(database=database)
    return _firestore_client


def _publisher() -> pubsub_v1.PublisherClient:
    global _publisher_client
    if _publisher_client is None:
        _publisher_client = pubsub_v1.PublisherClient(
            publisher_options=pubsub_v1.types.PublisherOptions(
                enable_message_ordering=True
            )
        )
    return _publisher_client


def _executions() -> executions_v1.ExecutionsClient:
    global _executions_client
    if _executions_client is None:
        _executions_client = executions_v1.ExecutionsClient()
    return _executions_client


def _json_object() -> dict[str, Any]:
    if request.content_length is not None and request.content_length > core.MAX_EVENT_BYTES:
        raise core.ContractError("EVENT_TOO_LARGE")
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise core.ContractError("INVALID_UTF8_JSON")
    return value


def _decode_pubsub_push(value: Mapping[str, Any]) -> dict[str, Any]:
    message = value.get("message")
    encoded = message.get("data") if isinstance(message, Mapping) else None
    if not isinstance(encoded, str):
        raise core.ContractError("INVALID_PUBSUB_MESSAGE")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > core.MAX_EVENT_BYTES:
            raise core.ContractError("EVENT_TOO_LARGE")
        decoded = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise core.ContractError("INVALID_PUBSUB_MESSAGE") from exc
    return core.validate_canonical_event(decoded)


def _publish(topic: str, event: Mapping[str, Any]) -> None:
    if not topic:
        raise core.ContractError("EVENT_ROUTE_NOT_CONFIGURED", 503)
    core.validate_canonical_event(event)
    future = _publisher().publish(
        topic,
        core.canonical_json(event).encode("utf-8"),
        ordering_key=core.partition_key(event),
        event_type=str(event["event_type"]),
    )
    future.result(timeout=30)


def _identity_token(audience: str) -> str:
    try:
        return id_token.fetch_id_token(GoogleAuthRequest(), audience)
    except Exception as exc:
        raise core.ContractError("WORKLOAD_IDENTITY_UNAVAILABLE", 503) from exc


def _invoke_processor_extension(event: Mapping[str, Any]) -> dict[str, Any]:
    url = os.environ.get("PROCESSOR_EXTENSION_URL", "")
    if not url:
        raise core.ContractError("PROCESSOR_EXTENSION_NOT_CONFIGURED", 503)
    payload = core.processor_extension_request(event)
    headers = {
        "authorization": f"Bearer {_identity_token(url)}",
        "content-type": "application/json",
    }
    for _ in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            if response.status_code == 200:
                value = response.json()
                if isinstance(value, dict):
                    return value
        except (requests.RequestException, ValueError):
            continue
    raise core.ContractError("PROCESSOR_EXTENSION_FAILED", 503)


def _configured_rules() -> list[Mapping[str, Any]]:
    try:
        value = json.loads(os.environ.get("RULES_JSON", "[]"))
    except json.JSONDecodeError as exc:
        raise core.ContractError("INVALID_RULE_CONFIGURATION", 503) from exc
    if not isinstance(value, list):
        raise core.ContractError("INVALID_RULE_CONFIGURATION", 503)
    return value


def _start_workflow(event: Mapping[str, Any]) -> None:
    workflow_name = os.environ.get("WORKFLOW_NAME", "")
    if not workflow_name:
        raise core.ContractError("WORKFLOW_NOT_CONFIGURED", 503)
    execution = executions_v1.Execution(argument=core.canonical_json(dict(event)))
    _executions().create_execution(parent=workflow_name, execution=execution)


def _persist(event: Mapping[str, Any]) -> bool:
    client = _database()
    hot_days = int(os.environ.get("HOT_BOUNDARY_DAYS", "30"))
    shard_count = int(os.environ.get("TIMESTAMP_SHARDS", "1"))
    raw = core.raw_document(
        event,
        stored_at=datetime.now(timezone.utc),
        hot_boundary_days=hot_days,
        shard_count=shard_count,
    )
    raw_ref = client.collection("telemetry").document(core.raw_document_id(event))
    rollup_ref = client.collection("hourly_rollups").document(
        core.rollup_document_id(raw)
    )
    transaction = client.transaction(max_attempts=3)

    @firestore.transactional
    def write(transaction: firestore.Transaction) -> bool:
        raw_snapshot = raw_ref.get(transaction=transaction)
        if raw_snapshot.exists:
            existing = raw_snapshot.to_dict() or {}
            if existing.get("payload_digest") == raw["payload_digest"]:
                return False
            raise core.ContractError("L3_IDEMPOTENCY_CONFLICT", 409)
        rollup_snapshot = rollup_ref.get(transaction=transaction)
        current = rollup_snapshot.to_dict() if rollup_snapshot.exists else None
        transaction.create(raw_ref, raw)
        transaction.set(rollup_ref, core.rollup_document(raw, current))
        return True

    return write(transaction)


def _ingress(value: Mapping[str, Any]) -> dict[str, Any]:
    deployment_id = os.environ.get("DEPLOYMENT_ID", "local-poc")
    if value.get("schema_version") == "canonical-domain-event.v1":
        event = core.validate_canonical_event(value)
    else:
        event = core.build_ingress_event(
            value,
            deployment_id=deployment_id,
        )
    if (
        event["event_type"] != core.EVENT_TELEMETRY_RECEIVED
        or event["deployment_id"] != deployment_id
    ):
        raise core.ContractError("UNEXPECTED_INGRESS_EVENT")
    _publish(os.environ.get("RECEIVED_TOPIC", ""), event)
    return {"schema_version": "event-adapter-result.v1", "accepted": 1}


def _process(value: Mapping[str, Any]) -> dict[str, Any]:
    received = _decode_pubsub_push(value)
    if received["event_type"] != core.EVENT_TELEMETRY_RECEIVED:
        raise core.ContractError("UNEXPECTED_PROCESSOR_EVENT")
    processed = core.build_processed_event(
        received,
        _invoke_processor_extension(received),
    )
    _publish(os.environ.get("PROCESSED_TOPIC", ""), processed)
    matches = core.build_rule_matches(processed, _configured_rules())
    for matched in matches:
        _publish(os.environ.get("DOMAIN_TOPIC", ""), matched)
        action = core.event_body(matched).get("action")
        if isinstance(action, Mapping) and action.get("type") in {
            "step_function",
            "logic_app",
            "workflow",
        }:
            _start_workflow(matched)
    return {
        "schema_version": "processor-result.v1",
        "accepted": 1,
        "matched": len(matches),
    }


def _persistence(value: Mapping[str, Any]) -> dict[str, Any]:
    processed = _decode_pubsub_push(value)
    if processed["event_type"] != core.EVENT_TELEMETRY_PROCESSED:
        raise core.ContractError("UNEXPECTED_HOT_STORAGE_EVENT")
    created = _persist(processed)
    projection = core.build_twin_projection(processed)
    if projection is not None:
        _publish(os.environ.get("DOMAIN_TOPIC", ""), projection)
    return {
        "schema_version": "persistence-result.v1",
        "accepted": 1,
        "created": created,
        "projected": projection is not None,
    }


def _poc_boundary(value: Mapping[str, Any]) -> dict[str, Any]:
    invocation_id = core.required_text(
        value.get("invocation_id") or value.get("event_id"),
        code="INVALID_ACTION_INVOCATION",
    )
    action_id = core.required_text(
        value.get("action_id") or "fixed-poc-action",
        code="INVALID_ACTION_INVOCATION",
    )
    return {
        "schema_version": "extension-action-result.v1",
        "invocation_id": invocation_id,
        "action_id": action_id,
        "status": "ACCEPTED",
    }


@app.get("/healthz")
def healthz():
    return jsonify(
        {
            "status": "ok",
            "profile": core.PROFILE,
            "role": os.environ.get("RUNTIME_ROLE", "unset"),
        }
    )


@app.post("/")
def dispatch():
    try:
        value = _json_object()
        role = os.environ.get("RUNTIME_ROLE", "")
        if role == "event-adapter":
            result = _ingress(value)
        elif role == "processor":
            result = _process(value)
        elif role == "persistence":
            result = _persistence(value)
        elif role == "poc-boundary":
            result = _poc_boundary(value)
        else:
            raise core.ContractError("RUNTIME_ROLE_NOT_CONFIGURED", 503)
        return jsonify(result), 200
    except core.ContractError as exc:
        LOGGER.warning("GCP Five-layer v2 contract failure: %s", exc.code)
        return jsonify({"error": {"code": exc.code}}), exc.status
    except Exception:
        LOGGER.exception("GCP Five-layer v2 retryable runtime failure")
        return jsonify({"error": {"code": "RUNTIME_RETRYABLE_FAILURE"}}), 503
