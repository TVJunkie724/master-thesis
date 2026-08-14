"""Role-selected Cloud Run HTTP runtime for GCP Six-layer v1."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import html
import json
import logging
import os
import time
from typing import Any, Mapping
from urllib.parse import quote
import uuid

from flask import Flask, Response, jsonify, request
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import firestore, pubsub_v1
from google.cloud.firestore_v1.base_query import FieldFilter
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
            role = os.environ.get("RUNTIME_ROLE", "")
            code = (
                "TWIN_STORAGE_NOT_CONFIGURED"
                if role in {"twin-materializer", "twin-explorer"}
                else "HOT_STORAGE_NOT_CONFIGURED"
            )
            raise core.ContractError(code, 503)
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
    if (
        request.content_length is not None
        and request.content_length > core.MAX_EVENT_BYTES
    ):
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


def _route_topic(*, local_provider: str, local_topic: str, remote_topic: str) -> str:
    return local_topic if local_provider == "google" else remote_topic


def _six_layer_eventing() -> bool:
    return os.environ.get("ARCHITECTURE_PROFILE") == "six-layer-eventing@1"


def _domain_output_topic() -> str:
    return os.environ.get(
        "REMOTE_CONTROL_TOPIC" if _six_layer_eventing() else "DOMAIN_TOPIC",
        "",
    )


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
        twin_ref = client.collection("twins").document(
            core.firestore_document_id(twin_id, code="INVALID_TWIN_PROJECTION")
        )
        source_ref = twin_ref.collection("sources").document(
            core.firestore_document_id(source_id, code="INVALID_TWIN_PROJECTION")
        )

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
    reference = client.collection(collection).document(
        core.firestore_document_id(document_id, code="INVALID_TWIN_PROJECTION")
    )

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
        _publish(_domain_output_topic(), item)
    return len(derived)


def _record_workflow_outcome(value: Mapping[str, Any]) -> None:
    if (
        set(value) != {"schema_version", "workflow_request", "status"}
        or value.get("schema_version") != "workflow-outcome.v1"
    ):
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
    _publish(_domain_output_topic(), outcome)


def _record_command_outcome(value: Mapping[str, Any]) -> dict[str, Any]:
    if (
        set(value) != {"schema_version", "command", "status"}
        or value.get("schema_version") != "device-command-delivery.v1"
    ):
        raise core.ContractError("INVALID_COMMAND_OUTCOME")
    command = value.get("command")
    if not isinstance(command, Mapping):
        raise core.ContractError("INVALID_COMMAND_OUTCOME")
    event = core.validate_canonical_event(command)
    if event["event_type"] != core.EVENT_DEVICE_COMMAND_REQUESTED or event[
        "deployment_id"
    ] != os.environ.get("DEPLOYMENT_ID", "local-poc"):
        raise core.ContractError("INVALID_COMMAND_OUTCOME")
    status = value.get("status")
    if status not in {"ACCEPTED", "FAILED"}:
        raise core.ContractError("INVALID_COMMAND_OUTCOME")
    outcome = core.derive_event(
        event,
        event_type=core.EVENT_COMMAND_OUTCOME,
        producer="component.device-command-adapter",
        payload={
            "device_id": core.partition_key(event),
            "invocation_id": core.event_id(event),
            "status": status,
        },
    )
    _publish(_domain_output_topic(), outcome)
    return outcome


def _ingress(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") == "device-command-delivery.v1":
        outcome = _record_command_outcome(value)
        return {
            "schema_version": "event-adapter-result.v1",
            "accepted": 1,
            "event_type": outcome["event_type"],
        }
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
    _publish(
        _route_topic(
            local_provider=os.environ.get("L2_PROVIDER", ""),
            local_topic=os.environ.get("RECEIVED_TOPIC", ""),
            remote_topic=os.environ.get("REMOTE_TELEMETRY_TOPIC", ""),
        ),
        event,
    )
    return {"schema_version": "event-adapter-result.v1", "accepted": 1}


def _process(value: Mapping[str, Any]) -> dict[str, Any]:
    received = _decode_pubsub_push(value)
    if received["event_type"] != core.EVENT_TELEMETRY_RECEIVED:
        raise core.ContractError("UNEXPECTED_PROCESSOR_EVENT")
    processed = core.build_processed_event(
        received,
        _invoke_processor_extension(received),
    )
    if _six_layer_eventing():
        _publish(
            _route_topic(
                local_provider=os.environ.get("EVENT_LAYER_PROVIDER", ""),
                local_topic=os.environ.get("PROCESSED_TOPIC", ""),
                remote_topic=os.environ.get("REMOTE_TELEMETRY_TOPIC", ""),
            ),
            processed,
        )
        matches = []
    else:
        _publish(
            _route_topic(
                local_provider=os.environ.get("HOT_PROVIDER", ""),
                local_topic=os.environ.get("PROCESSED_TOPIC", ""),
                remote_topic=os.environ.get("REMOTE_TELEMETRY_TOPIC", ""),
            ),
            processed,
        )
        matches = core.build_rule_matches(processed, _configured_rules())
        for matched in matches:
            _publish(_domain_output_topic(), matched)
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
    projection = _project_processed(processed)
    return {
        "schema_version": "persistence-result.v1",
        "accepted": 1,
        "created": created,
        "projected": projection is not None,
    }


def _project_processed(processed: Mapping[str, Any]) -> Mapping[str, Any] | None:
    projection = core.build_twin_projection(processed)
    if projection is None:
        return None
    if _six_layer_eventing() and os.environ.get("TWIN_PROVIDER") == "google":
        _materialize_twin_projection(projection)
    else:
        _publish(
            _route_topic(
                local_provider=os.environ.get("TWIN_PROVIDER", ""),
                local_topic=os.environ.get("DOMAIN_TOPIC", ""),
                remote_topic=os.environ.get(
                    "TWIN_REMOTE_CONTROL_TOPIC",
                    os.environ.get("REMOTE_CONTROL_TOPIC", ""),
                ),
            ),
            projection,
        )
    return projection


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


def _document_reference(client: firestore.Client, path: str):
    parts = path.split("/")
    if len(parts) == 2:
        return client.collection(parts[0]).document(parts[1])
    if len(parts) == 4:
        return (
            client.collection(parts[0])
            .document(parts[1])
            .collection(parts[2])
            .document(parts[3])
        )
    raise core.ContractError("INVALID_TWIN_SEED", 503)


def _ensure_seeded_twin_content() -> bool:
    try:
        configured = json.loads(os.environ.get("IOT_DEVICES_JSON", "[]"))
    except json.JSONDecodeError as exc:
        raise core.ContractError("INVALID_TWIN_SEED", 503) from exc
    if not isinstance(configured, list):
        raise core.ContractError("INVALID_TWIN_SEED", 503)
    documents = core.build_seed_twin_documents(
        configured,
        deployment_id=os.environ.get("DEPLOYMENT_ID", "local-poc"),
    )
    client = _database()
    marker = client.collection("_twin2multicloud").document("l4-seed-v1")
    transaction = client.transaction(max_attempts=3)

    @firestore.transactional
    def seed(transaction: firestore.Transaction) -> bool:
        if marker.get(transaction=transaction).exists:
            return False
        for path, document in documents.items():
            transaction.set(_document_reference(client, path), document)
        transaction.set(
            marker,
            {
                "seed_revision": "gcp-l4-seed.v1",
                "content_digest": hashlib.sha256(
                    core.canonical_json(documents).encode("utf-8")
                ).hexdigest(),
                "document_count": len(documents),
            },
        )
        return True

    return seed(transaction)


def _probe_seeded_twin_content() -> None:
    """Prove the bounded seed is readable through the Explorer identity."""
    try:
        configured = json.loads(os.environ.get("IOT_DEVICES_JSON", "[]"))
    except json.JSONDecodeError as exc:
        raise core.ContractError("INVALID_TWIN_SEED", 503) from exc
    if not isinstance(configured, list):
        raise core.ContractError("INVALID_TWIN_SEED", 503)
    documents = core.build_seed_twin_documents(
        configured,
        deployment_id=os.environ.get("DEPLOYMENT_ID", "local-poc"),
    )
    client = _database()
    marker = client.collection("_twin2multicloud").document("l4-seed-v1").get()
    marker_value = marker.to_dict() if marker.exists else None
    expected_digest = hashlib.sha256(
        core.canonical_json(documents).encode("utf-8")
    ).hexdigest()
    if not isinstance(marker_value, Mapping):
        raise core.ContractError("TWIN_SEED_NOT_READY", 503)
    if marker_value.get("seed_revision") != "gcp-l4-seed.v1":
        raise core.ContractError("TWIN_SEED_NOT_READY", 503)
    if marker_value.get("content_digest") != expected_digest:
        raise core.ContractError("TWIN_SEED_NOT_READY", 503)
    if marker_value.get("document_count") != len(documents):
        raise core.ContractError("TWIN_SEED_NOT_READY", 503)
    for path in documents:
        if not _document_reference(client, path).get().exists:
            raise core.ContractError("TWIN_SEED_NOT_READY", 503)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return core.iso_time(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _snapshot_document(snapshot) -> dict[str, Any]:
    value = snapshot.to_dict() or {}
    if not isinstance(value, Mapping):
        raise core.ContractError("INVALID_TWIN_MATERIALIZATION_STATE", 503)
    return _json_safe(dict(value))


def _bounded_twin_limit(raw: object, maximum: int = 100) -> int:
    try:
        value = int(str(raw or maximum))
    except ValueError as exc:
        raise core.ContractError("INVALID_TWIN_QUERY") from exc
    if not 1 <= value <= maximum:
        raise core.ContractError("INVALID_TWIN_QUERY")
    return value


def _list_twin_collection(collection: str, *, limit: int) -> list[dict[str, Any]]:
    if collection not in {"models", "twins"}:
        raise core.ContractError("INVALID_TWIN_QUERY")
    documents = [
        _snapshot_document(snapshot)
        for snapshot in _database().collection(collection).limit(limit).stream()
    ]
    identifier = "model_id" if collection == "models" else "twin_id"
    return sorted(documents, key=lambda item: str(item.get(identifier, "")))


def _twin_detail(twin_id: str) -> dict[str, Any]:
    logical_id = core.required_text(twin_id, code="INVALID_TWIN_QUERY")
    client = _database()
    reference = client.collection("twins").document(
        core.firestore_document_id(logical_id, code="INVALID_TWIN_QUERY")
    )
    snapshot = reference.get()
    if not snapshot.exists:
        raise core.ContractError("TWIN_NOT_FOUND", 404)
    sources = [
        _snapshot_document(item)
        for item in reference.collection("sources").limit(32).stream()
    ]
    relationships: list[dict[str, Any]] = []
    for field in ("from_id", "to_id"):
        query = (
            client.collection("relationships")
            .where(filter=FieldFilter(field, "==", logical_id))
            .limit(100)
        )
        relationships.extend(
            _snapshot_document(item)
            for item in query.stream()
            if not (item.to_dict() or {}).get("deleted")
        )
    unique_relationships = {
        str(item.get("relationship_id")): item for item in relationships
    }
    return {
        "schema_version": "bounded-twin-read.v1",
        "twin": _snapshot_document(snapshot),
        "sources": sorted(sources, key=lambda item: str(item.get("source_id", ""))),
        "relationships": sorted(
            unique_relationships.values(),
            key=lambda item: str(item.get("relationship_id", "")),
        ),
    }


def _model_detail(model_id: str) -> dict[str, Any]:
    logical_id = core.required_text(model_id, code="INVALID_TWIN_QUERY")
    snapshot = (
        _database()
        .collection("models")
        .document(core.firestore_document_id(logical_id, code="INVALID_TWIN_QUERY"))
        .get()
    )
    if not snapshot.exists:
        raise core.ContractError("MODEL_NOT_FOUND", 404)
    return {
        "schema_version": "bounded-twin-model.v1",
        "model": _snapshot_document(snapshot),
    }


def _verify_reader_key() -> None:
    expected = os.environ.get("READER_KEY_SHA256", "")
    supplied = request.headers.get("x-twin2multicloud-reader-key", "")
    if len(expected) != 64 or any(
        character not in "0123456789abcdef" for character in expected
    ):
        raise core.ContractError("READER_NOT_PROVISIONED", 503)
    actual = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise core.ContractError("READER_UNAUTHORIZED", 401)


def _history_deadline_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise core.ContractError("READER_TIMEOUT", 503)
    return remaining


def _cursor_position(value: object, *, key: str) -> tuple[datetime, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {key, "document_id"}:
        raise core.ContractError("INVALID_CURSOR")
    return (
        core.parse_time(value.get(key)),
        core.required_text(value.get("document_id"), code="INVALID_CURSOR"),
    )


def _raw_history_documents(
    query: Mapping[str, Any],
    start: datetime,
    end: datetime,
    cursor_state: Mapping[str, Any] | None,
    *,
    deadline: float,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, bool]:
    try:
        shard_count = int(os.environ.get("TIMESTAMP_SHARDS", "1"))
    except ValueError as exc:
        raise core.ContractError("HOT_STORAGE_NOT_CONFIGURED", 503) from exc
    if shard_count not in {1, 16}:
        raise core.ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
    if cursor_state is not None and (
        set(cursor_state) != {"kind", "shards"}
        or cursor_state.get("kind") != "raw"
        or not isinstance(cursor_state.get("shards"), Mapping)
    ):
        raise core.ContractError("INVALID_CURSOR")
    previous = dict((cursor_state or {}).get("shards") or {})
    if set(previous) - {str(shard) for shard in range(shard_count)}:
        raise core.ContractError("INVALID_CURSOR")
    collection = _database().collection("telemetry")
    candidates: list[dict[str, Any]] = []
    for shard in range(shard_count):
        history_query = (
            collection.where(filter=FieldFilter("device_id", "==", query["device_id"]))
            .where(filter=FieldFilter("metric", "==", query["metric"]))
            .where(filter=FieldFilter("timestamp_shard", "==", shard))
            .where(filter=FieldFilter("stored_at", ">=", start))
            .where(filter=FieldFilter("stored_at", "<=", end))
            .select(["stored_at", "event_time", "value", "timestamp_shard"])
            .order_by("stored_at")
            .order_by("__name__")
        )
        position = _cursor_position(previous.get(str(shard)), key="stored_at")
        if position is not None:
            stored_at, document_id = position
            history_query = history_query.start_after(
                {
                    "stored_at": stored_at,
                    "__name__": collection.document(document_id),
                }
            )
        snapshots = history_query.limit(int(query["limit"]) + 1).stream(
            timeout=_history_deadline_timeout(deadline)
        )
        for snapshot in snapshots:
            document = _snapshot_document(snapshot)
            stored_at = core.parse_time(document.get("stored_at"))
            candidates.append(
                {
                    **document,
                    "_document_id": snapshot.id,
                    "_shard": shard,
                    "_sort_time": stored_at,
                }
            )
        _history_deadline_timeout(deadline)
    candidates.sort(key=lambda item: (item["_sort_time"], item["_document_id"]))
    selected = candidates[: int(query["limit"])]
    has_more = len(candidates) > len(selected)
    next_shards = previous
    for item in selected:
        next_shards[str(item["_shard"])] = {
            "stored_at": core.iso_time(item["_sort_time"]),
            "document_id": item["_document_id"],
        }
    documents = [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in selected
    ]
    return (
        documents,
        ({"kind": "raw", "shards": next_shards} if has_more else None),
        has_more,
    )


def _aggregate_history_documents(
    query: Mapping[str, Any],
    start: datetime,
    end: datetime,
    cursor_state: Mapping[str, Any] | None,
    *,
    deadline: float,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, bool]:
    if cursor_state is not None and (
        set(cursor_state) != {"kind", "last"} or cursor_state.get("kind") != "aggregate"
    ):
        raise core.ContractError("INVALID_CURSOR")
    collection = _database().collection("hourly_rollups")
    history_query = (
        collection.where(filter=FieldFilter("device_id", "==", query["device_id"]))
        .where(filter=FieldFilter("metric", "==", query["metric"]))
        .where(filter=FieldFilter("bucket_start", ">=", start))
        .where(filter=FieldFilter("bucket_start", "<=", end))
        .select(["bucket_start", "min", "max", "sum", "count"])
        .order_by("bucket_start")
        .order_by("__name__")
    )
    position = _cursor_position((cursor_state or {}).get("last"), key="bucket_start")
    if position is not None:
        bucket_start, document_id = position
        history_query = history_query.start_after(
            {
                "bucket_start": bucket_start,
                "__name__": collection.document(document_id),
            }
        )
    snapshots = list(
        history_query.limit(int(query["limit"]) + 1).stream(
            timeout=_history_deadline_timeout(deadline)
        )
    )
    _history_deadline_timeout(deadline)
    selected = snapshots[: int(query["limit"])]
    has_more = len(snapshots) > len(selected)
    documents = [_snapshot_document(snapshot) for snapshot in selected]
    next_state = None
    if has_more and selected:
        final = documents[-1]
        next_state = {
            "kind": "aggregate",
            "last": {
                "bucket_start": core.iso_time(
                    core.parse_time(final.get("bucket_start"))
                ),
                "document_id": selected[-1].id,
            },
        }
    return documents, next_state, has_more


def _read_raw_history(params: Mapping[str, Any]) -> dict[str, Any]:
    query, start, end = core.parse_raw_history_query(params)
    deployment_id = core.required_text(
        os.environ.get("DEPLOYMENT_ID"), code="READER_NOT_PROVISIONED"
    )
    cursor_hmac_key = os.environ.get("CURSOR_HMAC_KEY", "")
    if len(cursor_hmac_key.encode("utf-8")) < 32:
        raise core.ContractError("READER_NOT_PROVISIONED", 503)
    query_digest = core.raw_history_query_digest(query, start, end)
    cursor_state = core.decode_history_cursor(
        query["cursor"],
        hmac_key=cursor_hmac_key,
        query_digest=query_digest,
        deployment_id=deployment_id,
    )
    deadline = time.monotonic() + 10
    if query["bucket_seconds"] == 0:
        documents, next_state, truncated = _raw_history_documents(
            query, start, end, cursor_state, deadline=deadline
        )
    else:
        documents, next_state, truncated = _aggregate_history_documents(
            query, start, end, cursor_state, deadline=deadline
        )
    next_cursor = (
        core.encode_history_cursor(
            next_state,
            hmac_key=cursor_hmac_key,
            query_digest=query_digest,
            deployment_id=deployment_id,
        )
        if next_state is not None
        else None
    )
    return {
        "schema_version": "raw-history-query.v1",
        "device_id": query["device_id"],
        "metric": query["metric"],
        "points": core.normalize_history_points(
            documents, int(query["bucket_seconds"])
        ),
        "next_cursor": next_cursor,
        "truncated": truncated,
        "correlation_id": str(uuid.uuid4()),
    }


def _twin_materializer(value: Mapping[str, Any]) -> dict[str, Any]:
    _ensure_seeded_twin_content()
    event = _decode_pubsub_push(value)
    changed = _materialize_twin_projection(event)
    return {
        "schema_version": "twin-materializer-result.v1",
        "accepted": 1,
        "changed": changed,
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
        _publish(
            _route_topic(
                local_provider=os.environ.get("L1_PROVIDER", ""),
                local_topic=os.environ.get("COMMAND_TOPIC", ""),
                remote_topic=os.environ.get("REMOTE_CONTROL_TOPIC", ""),
            ),
            event,
        )
        handled = True
    elif kind in core.OUTCOME_EVENT_TYPES:
        if os.environ.get("HOT_PROVIDER") == "google":
            _store_outcome(event)
        elif _six_layer_eventing():
            raise core.ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        else:
            _publish(os.environ.get("REMOTE_CONTROL_TOPIC", ""), event)
        handled = True
    if _six_layer_eventing() and not handled:
        raise core.ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
    return {
        "schema_version": "domain-consumer-result.v1",
        "accepted": 1,
        "handled": handled,
        "derived": derived,
    }


def _remote_landing(value: Mapping[str, Any]) -> dict[str, Any]:
    event = _decode_pubsub_push(value)
    kind = event["event_type"]
    try:
        configured_event_types = json.loads(
            os.environ.get("REMOTE_EVENT_TYPES_JSON", "[]")
        )
    except json.JSONDecodeError as exc:
        raise core.ContractError("REMOTE_EVENT_POLICY_INVALID", 503) from exc
    if (
        not isinstance(configured_event_types, list)
        or not configured_event_types
        or any(not isinstance(item, str) for item in configured_event_types)
    ):
        raise core.ContractError("REMOTE_EVENT_POLICY_INVALID", 503)
    if (
        event["deployment_id"] != os.environ.get("DEPLOYMENT_ID", "local-poc")
        or kind not in configured_event_types
    ):
        raise core.ContractError("UNEXPECTED_REMOTE_EVENT")
    if (
        os.environ.get("ARCHITECTURE_PROFILE") == "six-layer-eventing@1"
        and os.environ.get("EVENT_LAYER_PROVIDER") == "google"
        and kind
        in {
            core.EVENT_TELEMETRY_RECEIVED,
            core.EVENT_TELEMETRY_PROCESSED,
            core.EVENT_MATCHED,
            core.EVENT_NOTIFICATION_REQUESTED,
            core.EVENT_DEVICE_COMMAND_REQUESTED,
            *core.OUTCOME_EVENT_TYPES,
        }
    ):
        topic = (
            os.environ.get("RECEIVED_TOPIC", "")
            if kind == core.EVENT_TELEMETRY_RECEIVED
            else os.environ.get("PROCESSED_TOPIC", "")
            if kind == core.EVENT_TELEMETRY_PROCESSED
            else os.environ.get("DOMAIN_TOPIC", "")
        )
    elif (
        kind == core.EVENT_TELEMETRY_RECEIVED
        and os.environ.get("L2_PROVIDER") == "google"
    ):
        topic = os.environ.get("RECEIVED_TOPIC", "")
    elif kind == core.EVENT_TELEMETRY_PROCESSED and (
        os.environ.get("HOT_PROVIDER") == "google"
        or os.environ.get("L2_PROVIDER") == "google"
    ):
        if os.environ.get("HOT_PROVIDER") == "google":
            _publish(os.environ.get("PROCESSED_TOPIC", ""), event)
        if os.environ.get("L2_PROVIDER") == "google":
            for matched in core.build_rule_matches(event, _configured_rules()):
                _publish(_domain_output_topic(), matched)
        return {
            "schema_version": "remote-landing-result.v1",
            "accepted": 1,
            "event_type": kind,
        }
    elif (
        kind
        in {
            core.EVENT_MATCHED,
            core.EVENT_NOTIFICATION_REQUESTED,
        }
        and os.environ.get("L2_PROVIDER") == "google"
    ):
        topic = os.environ.get("DOMAIN_TOPIC", "")
    elif (
        kind == core.EVENT_DEVICE_COMMAND_REQUESTED
        and os.environ.get("L1_PROVIDER") == "google"
    ):
        topic = os.environ.get("DOMAIN_TOPIC", "")
    elif (
        kind in core.OUTCOME_EVENT_TYPES and os.environ.get("HOT_PROVIDER") == "google"
    ):
        topic = os.environ.get("DOMAIN_TOPIC", "")
    elif (
        kind
        in {
            core.EVENT_TWIN_STATE_UPSERTED,
            core.EVENT_TWIN_MODEL_UPSERTED,
            core.EVENT_TWIN_RELATIONSHIP_UPSERTED,
            core.EVENT_TWIN_RELATIONSHIP_DELETED,
        }
        and os.environ.get("TWIN_PROVIDER") == "google"
    ):
        topic = os.environ.get("DOMAIN_TOPIC", "")
    else:
        raise core.ContractError("UNEXPECTED_REMOTE_EVENT")
    _publish(topic, event)
    return {
        "schema_version": "remote-landing-result.v1",
        "accepted": 1,
        "event_type": kind,
    }


def _consume_eventing_delivery(role: str, value: Mapping[str, Any]) -> None:
    """Run one inherited L1-L5 responsibility after Event-Layer acceptance."""

    event = core.validate_canonical_event(value)
    if role == "telemetry-processor":
        if (
            event["event_type"] != core.EVENT_TELEMETRY_RECEIVED
            or os.environ.get("L2_PROVIDER") != "google"
        ):
            raise core.ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        processed = core.build_processed_event(
            event,
            _invoke_processor_extension(event),
        )
        _publish(os.environ.get("PROCESSED_TOPIC", ""), processed)
    elif role == "historical-persistence":
        if (
            event["event_type"] != core.EVENT_TELEMETRY_PROCESSED
            or os.environ.get("HOT_PROVIDER") != "google"
        ):
            raise core.ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _persist(event)
    elif role == "twin-state-update":
        if (
            event["event_type"] != core.EVENT_TELEMETRY_PROCESSED
            or os.environ.get("HOT_PROVIDER") != "google"
        ):
            raise core.ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        _project_processed(event)
    elif role == "rule-evaluator":
        if (
            event["event_type"] != core.EVENT_TELEMETRY_PROCESSED
            or os.environ.get("L2_PROVIDER") != "google"
        ):
            raise core.ContractError("EVENTING_CONSUMER_PROVIDER_MISMATCH")
        for matched in core.build_rule_matches(event, _configured_rules()):
            _publish(_domain_output_topic(), matched)
    elif role == "control-router":
        encoded = base64.b64encode(core.canonical_json(event).encode()).decode()
        _domain({"message": {"data": encoded}})
    elif role not in {"audit", "realtime-visualization"}:
        raise core.ContractError("UNSUPPORTED_EVENTING_CONSUMER")


@app.get("/healthz")
def healthz():
    role = os.environ.get("RUNTIME_ROLE")
    if role == "twin-materializer":
        _ensure_seeded_twin_content()
    elif role == "twin-explorer":
        _probe_seeded_twin_content()
    return jsonify(
        {
            "status": "ok",
            "profile": core.PROFILE,
            "role": role or "unset",
        }
    )


@app.get("/")
def twin_explorer():
    if os.environ.get("RUNTIME_ROLE") != "twin-explorer":
        return jsonify({"error": {"code": "RUNTIME_ROLE_NOT_CONFIGURED"}}), 404
    try:
        twins = _list_twin_collection("twins", limit=100)
        models = _list_twin_collection("models", limit=100)
        selected_id = request.args.get("twin_id", "")
        detail = _twin_detail(selected_id) if selected_id else None
        twin_links = (
            "".join(
                '<li><a href="/?twin_id={0}">{1}</a></li>'.format(
                    quote(str(item.get("twin_id", "")), safe=""),
                    html.escape(str(item.get("twin_id", ""))),
                )
                for item in twins
            )
            or "<li>No Twins materialized yet.</li>"
        )
        model_items = (
            "".join(
                f"<li>{html.escape(str(item.get('model_id', '')))}</li>"
                for item in models
            )
            or "<li>No models materialized yet.</li>"
        )
        detail_html = (
            "<p>Select a Twin to inspect current source state and direct relationships.</p>"
            if detail is None
            else f"<pre>{html.escape(json.dumps(detail, indent=2, sort_keys=True))}</pre>"
        )
        body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Twin2MultiCloud Twin Explorer</title><style>
body{{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#182230}}
main{{display:grid;grid-template-columns:minmax(16rem,1fr) 2fr;gap:1.5rem}}section{{border:1px solid #ccd5df;border-radius:12px;padding:1rem}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:1rem;border-radius:8px}}a{{color:#0759b0}}
@media(max-width:720px){{main{{grid-template-columns:1fr}}}}</style></head>
<body><h1>Twin2MultiCloud Twin Explorer</h1><p>Read-only Six-layer v1 semantic state. No scenes or raw telemetry.</p>
<main><section><h2>Twins</h2><ul>{twin_links}</ul><h2>Models</h2><ul>{model_items}</ul></section>
<section><h2>Twin detail</h2>{detail_html}</section></main></body></html>"""
        response = Response(body, content_type="text/html; charset=utf-8")
        response.headers["content-security-policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["cache-control"] = "no-store"
        return response
    except core.ContractError as exc:
        return jsonify({"error": {"code": exc.code}}), exc.status


@app.get("/twin-api/v1/models")
def twin_models():
    if os.environ.get("RUNTIME_ROLE") != "twin-explorer":
        return jsonify({"error": {"code": "RUNTIME_ROLE_NOT_CONFIGURED"}}), 404
    try:
        limit = _bounded_twin_limit(request.args.get("limit"))
        return jsonify(
            {
                "schema_version": "bounded-twin-list.v1",
                "models": _list_twin_collection("models", limit=limit),
            }
        )
    except core.ContractError as exc:
        return jsonify({"error": {"code": exc.code}}), exc.status


@app.get("/twin-api/v1/twins")
def twin_list():
    if os.environ.get("RUNTIME_ROLE") != "twin-explorer":
        return jsonify({"error": {"code": "RUNTIME_ROLE_NOT_CONFIGURED"}}), 404
    try:
        limit = _bounded_twin_limit(request.args.get("limit"))
        return jsonify(
            {
                "schema_version": "bounded-twin-list.v1",
                "twins": _list_twin_collection("twins", limit=limit),
            }
        )
    except core.ContractError as exc:
        return jsonify({"error": {"code": exc.code}}), exc.status


@app.get("/twin-api/v1/models/<path:model_id>")
def twin_model_detail(model_id: str):
    if os.environ.get("RUNTIME_ROLE") != "twin-explorer":
        return jsonify({"error": {"code": "RUNTIME_ROLE_NOT_CONFIGURED"}}), 404
    try:
        return jsonify(_model_detail(model_id))
    except core.ContractError as exc:
        return jsonify({"error": {"code": exc.code}}), exc.status


@app.get("/twin-api/v1/twins/<path:twin_id>")
def twin_detail(twin_id: str):
    if os.environ.get("RUNTIME_ROLE") != "twin-explorer":
        return jsonify({"error": {"code": "RUNTIME_ROLE_NOT_CONFIGURED"}}), 404
    try:
        return jsonify(_twin_detail(twin_id))
    except core.ContractError as exc:
        return jsonify({"error": {"code": exc.code}}), exc.status


@app.get("/raw-history/v1")
def raw_history_reader():
    correlation_id = str(uuid.uuid4())
    if os.environ.get("RUNTIME_ROLE") != "raw-history-reader":
        return jsonify({"error": {"code": "RUNTIME_ROLE_NOT_CONFIGURED"}}), 404
    try:
        _verify_reader_key()
        if any(len(request.args.getlist(key)) != 1 for key in request.args):
            raise core.ContractError("INVALID_QUERY")
        payload = _read_raw_history(request.args.to_dict(flat=True))
        response = jsonify(payload)
        response.headers["cache-control"] = "no-store"
        response.headers["x-content-type-options"] = "nosniff"
        return response, 200
    except core.ContractError as exc:
        response = jsonify(
            {
                "schema_version": "architecture-runtime-error.v1",
                "code": exc.code,
                "correlation_id": correlation_id,
            }
        )
        response.headers["cache-control"] = "no-store"
        return response, exc.status
    except Exception:
        LOGGER.exception("GCP Six-layer v1 raw-history retryable failure")
        response = jsonify(
            {
                "schema_version": "architecture-runtime-error.v1",
                "code": "RUNTIME_RETRYABLE_FAILURE",
                "correlation_id": correlation_id,
            }
        )
        response.headers["cache-control"] = "no-store"
        return response, 503


@app.get("/raw-history-health/v1")
def raw_history_health():
    if os.environ.get("RUNTIME_ROLE") != "raw-history-reader":
        return jsonify({"error": {"code": "RUNTIME_ROLE_NOT_CONFIGURED"}}), 404
    try:
        _verify_reader_key()
        response = jsonify(
            {
                "schema_version": "raw-history-health.v1",
                "status": "ready",
            }
        )
        response.headers["cache-control"] = "no-store"
        return response, 200
    except core.ContractError as exc:
        response = jsonify(
            {
                "schema_version": "architecture-runtime-error.v1",
                "code": exc.code,
            }
        )
        response.headers["cache-control"] = "no-store"
        return response, exc.status


@app.post("/")
def dispatch():
    try:
        role = os.environ.get("RUNTIME_ROLE", "")
        if role == "cross-cloud-bridge":
            from phase8_eventing.gcp.runtime import push_request

            return push_request(request)
        value = _json_object()
        eventing_delivery = value.get("eventing_delivery")
        if eventing_delivery is not None:
            if (
                os.environ.get("EVENTING_DELIVERY_ENDPOINT_ENABLED", "false") != "true"
                or set(value) != {"eventing_delivery"}
                or not isinstance(eventing_delivery, Mapping)
                or set(eventing_delivery) != {"consumer_role", "event"}
                or not isinstance(eventing_delivery.get("consumer_role"), str)
                or not isinstance(eventing_delivery.get("event"), Mapping)
            ):
                raise core.ContractError("INVALID_EVENTING_DELIVERY")
            _consume_eventing_delivery(
                str(eventing_delivery["consumer_role"]),
                eventing_delivery["event"],
            )
            return jsonify(
                {
                    "schema_version": "event-delivery-result.v1",
                    "accepted": 1,
                }
            ), 202
        if role == "event-adapter":
            result = _ingress(value)
        elif role == "processor":
            result = _process(value)
        elif role == "persistence":
            result = _persistence(value)
        elif role == "domain-consumer":
            result = _domain(value)
        elif role == "remote-landing":
            result = _remote_landing(value)
        elif role == "twin-materializer":
            result = _twin_materializer(value)
        elif role == "poc-boundary":
            result = _poc_boundary(value)
        else:
            raise core.ContractError("RUNTIME_ROLE_NOT_CONFIGURED", 503)
        return jsonify(result), 200
    except core.ContractError as exc:
        LOGGER.warning("GCP Six-layer v1 contract failure: %s", exc.code)
        return jsonify({"error": {"code": exc.code}}), exc.status
    except Exception:
        LOGGER.exception("GCP Six-layer v1 retryable runtime failure")
        return jsonify({"error": {"code": "RUNTIME_RETRYABLE_FAILURE"}}), 503
