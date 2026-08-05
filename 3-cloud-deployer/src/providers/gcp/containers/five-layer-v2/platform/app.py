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


def _invoke_poc_action(event: Mapping[str, Any]) -> bool:
    action = core.event_body(event).get("action")
    if not isinstance(action, Mapping):
        raise core.ContractError("INVALID_MATCH_EVENT")
    url = os.environ.get("ACTION_URL", "")
    if not url:
        raise core.ContractError("EXTENSION_ACTION_NOT_CONFIGURED", 503)
    invocation = {
        "schema_version": "extension-action-invocation.v1",
        "invocation_id": core.event_id(event),
        "action_id": core.action_id(action),
        "event": dict(event),
    }
    headers = {
        "authorization": f"Bearer {_identity_token(url)}",
        "content-type": "application/json",
    }
    expected = {
        "schema_version": "extension-action-result.v1",
        "invocation_id": core.event_id(event),
        "action_id": invocation["action_id"],
        "status": "ACCEPTED",
    }
    for _ in range(3):
        try:
            response = requests.post(url, json=invocation, headers=headers, timeout=20)
            if response.status_code == 200 and response.json() == expected:
                return True
        except (requests.RequestException, ValueError):
            continue
    return False


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


def _store_outcome(event: Mapping[str, Any]) -> bool:
    client = _database()
    hot_days = int(os.environ.get("HOT_BOUNDARY_DAYS", "30"))
    document = core.outcome_document(
        event,
        stored_at=datetime.now(timezone.utc),
        hot_boundary_days=hot_days,
    )
    reference = client.collection("outcomes").document(core.raw_document_id(event))
    transaction = client.transaction(max_attempts=3)

    @firestore.transactional
    def write(transaction: firestore.Transaction) -> bool:
        snapshot = reference.get(transaction=transaction)
        if snapshot.exists:
            existing = snapshot.to_dict() or {}
            if existing.get("payload_digest") == document["payload_digest"]:
                return False
            raise core.ContractError("L3_IDEMPOTENCY_CONFLICT", 409)
        transaction.create(reference, document)
        return True

    return write(transaction)


def _materialize_twin_projection(event: Mapping[str, Any]) -> bool:
    validated = core.validate_twin_projection(event)
    client = _database()
    body = core.event_body(validated)
    kind = validated["event_type"]
    transaction = client.transaction(max_attempts=3)

    if kind == core.EVENT_TWIN_STATE_UPSERTED:
        twin_id = str(body["twin_id"])
        source_id = str(body["source_id"])
        twin_ref = client.collection("twins").document(twin_id)
        source_ref = twin_ref.collection("sources").document(source_id)

        @firestore.transactional
        def write_state(transaction: firestore.Transaction) -> bool:
            snapshot = source_ref.get(transaction=transaction)
            twin_snapshot = twin_ref.get(transaction=transaction)
            current = snapshot.to_dict() if snapshot.exists else None
            if not core.projection_is_newer(current, validated):
                return False
            current_values = dict((current or {}).get("current_values") or {})
            current_values.update(dict(body["state_patch"]))
            twin_current = twin_snapshot.to_dict() if twin_snapshot.exists else None
            if core.projection_is_newer(twin_current, validated):
                transaction.set(
                    twin_ref,
                    {
                        "twin_id": twin_id,
                        "updated_at": core.parse_time(str(body["observed_at"])),
                        "last_observed_at": str(body["observed_at"]),
                        "last_source_sequence": str(body["source_sequence"]),
                        "last_event_id": core.event_id(validated),
                    },
                    merge=True,
                )
            transaction.set(
                source_ref,
                {
                    "source_id": source_id,
                    "current_values": current_values,
                    "last_observed_at": str(body["observed_at"]),
                    "last_source_sequence": str(body["source_sequence"]),
                    "last_event_id": core.event_id(validated),
                },
            )
            return True

        return write_state(transaction)

    collection = "models" if kind == core.EVENT_TWIN_MODEL_UPSERTED else "relationships"
    document_id = str(
        body["model_id"]
        if kind == core.EVENT_TWIN_MODEL_UPSERTED
        else body["relationship_id"]
    )
    reference = client.collection(collection).document(document_id)

    @firestore.transactional
    def write_graph(transaction: firestore.Transaction) -> bool:
        snapshot = reference.get(transaction=transaction)
        current = snapshot.to_dict() if snapshot.exists else None
        if not core.projection_is_newer(current, validated):
            return False
        common = {
            "last_observed_at": str(validated["occurred_at"]),
            "last_source_sequence": str(validated["source_sequence"]),
            "last_event_id": core.event_id(validated),
        }
        if kind == core.EVENT_TWIN_MODEL_UPSERTED:
            document = {
                **common,
                "model_id": str(body["model_id"]),
                "model_version": str(body["model_version"]),
                "model_document": dict(body["model_document"]),
            }
        else:
            document = {
                **common,
                "relationship_id": str(body["relationship_id"]),
                "from_id": str(body["from_twin_id"]),
                "to_id": str(body["to_twin_id"]),
                "type": str(body["type"]),
                "deleted": kind == core.EVENT_TWIN_RELATIONSHIP_DELETED,
            }
        transaction.set(reference, document)
        return True

    return write_graph(transaction)


def _dispatch_match(event: Mapping[str, Any]) -> int:
    derived = core.build_match_dispatch_events(
        event,
        action_accepted=_invoke_poc_action(event),
    )
    for item in derived:
        _publish(os.environ.get("DOMAIN_TOPIC", ""), item)
    return len(derived)


def _record_workflow_outcome(value: Mapping[str, Any]) -> None:
    if set(value) != {"schema_version", "workflow_request", "status"} or value.get(
        "schema_version"
    ) != "workflow-outcome.v1":
        raise core.ContractError("INVALID_WORKFLOW_OUTCOME")
    workflow_request = value.get("workflow_request")
    if not isinstance(workflow_request, Mapping):
        raise core.ContractError("INVALID_WORKFLOW_OUTCOME")
    event = core.validate_canonical_event(workflow_request)
    if event["event_type"] != core.EVENT_NOTIFICATION_REQUESTED:
        raise core.ContractError("INVALID_WORKFLOW_OUTCOME")
    status = value.get("status")
    if status not in {"SUCCEEDED", "FAILED"}:
        raise core.ContractError("INVALID_WORKFLOW_OUTCOME")
    outcome = core.derive_event(
        event,
        event_type=core.EVENT_WORKFLOW_OUTCOME,
        producer="component.notification-workflow",
        payload={
            "device_id": core.partition_key(event),
            "invocation_id": core.event_id(event),
            "status": status,
        },
    )
    _publish(os.environ.get("DOMAIN_TOPIC", ""), outcome)


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
    if value.get("schema_version") == "extension-action-invocation.v1":
        if set(value) != {
            "schema_version",
            "invocation_id",
            "action_id",
            "event",
        }:
            raise core.ContractError("INVALID_ACTION_INVOCATION")
        event = value.get("event")
        if not isinstance(event, Mapping):
            raise core.ContractError("INVALID_ACTION_INVOCATION")
        matched = core.validate_canonical_event(event)
        action = core.event_body(matched).get("action")
        if (
            matched["event_type"] != core.EVENT_MATCHED
            or value.get("invocation_id") != core.event_id(matched)
            or not isinstance(action, Mapping)
            or value.get("action_id") != core.action_id(action)
        ):
            raise core.ContractError("INVALID_ACTION_INVOCATION")
        return {
            "schema_version": "extension-action-result.v1",
            "invocation_id": core.event_id(matched),
            "action_id": value["action_id"],
            "status": "ACCEPTED",
        }
    notification = core.validate_canonical_event(value)
    body = core.event_body(notification)
    if (
        notification["event_type"] != core.EVENT_NOTIFICATION_REQUESTED
        or not isinstance(body.get("message"), str)
        or not body["message"]
    ):
        raise core.ContractError("INVALID_NOTIFICATION_INVOCATION")
    return {
        "schema_version": "notification-delivery-result.v1",
        "event_id": core.event_id(notification),
        "status": "ACCEPTED",
    }


def _domain(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") == "workflow-outcome.v1":
        _record_workflow_outcome(value)
        return {"schema_version": "domain-consumer-result.v1", "accepted": 1}
    event = _decode_pubsub_push(value)
    kind = event["event_type"]
    handled = False
    derived = 0
    if kind == core.EVENT_MATCHED and os.environ.get("L2_PROVIDER") == "google":
        derived = _dispatch_match(event)
        handled = True
    elif (
        kind == core.EVENT_NOTIFICATION_REQUESTED
        and os.environ.get("L2_PROVIDER") == "google"
    ):
        _start_workflow(event)
        handled = True
    elif (
        kind == core.EVENT_DEVICE_COMMAND_REQUESTED
        and os.environ.get("L1_PROVIDER") == "google"
    ):
        _publish(os.environ.get("COMMAND_TOPIC", ""), event)
        handled = True
    elif kind in core.OUTCOME_EVENT_TYPES and os.environ.get("HOT_PROVIDER") == "google":
        _store_outcome(event)
        handled = True
    elif kind in {
        core.EVENT_TWIN_STATE_UPSERTED,
        core.EVENT_TWIN_MODEL_UPSERTED,
        core.EVENT_TWIN_RELATIONSHIP_UPSERTED,
        core.EVENT_TWIN_RELATIONSHIP_DELETED,
    } and os.environ.get("TWIN_PROVIDER") == "google":
        _materialize_twin_projection(event)
        handled = True
    return {
        "schema_version": "domain-consumer-result.v1",
        "accepted": 1,
        "handled": handled,
        "derived": derived,
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
        elif role == "domain-consumer":
            result = _domain(value)
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
